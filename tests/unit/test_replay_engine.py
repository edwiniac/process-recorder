"""
Tests for the replay engine module.

Verifies full workflow replay, step execution, pause/resume,
stop, error strategies, and report saving.
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from process_recorder.models import (
    ActionType,
    BoundingBox,
    SemanticStep,
    Workflow,
)
from process_recorder.replayer.action_executor import ExecutorConfig
from process_recorder.replayer.element_finder import FinderConfig
from process_recorder.replayer.replay_engine import (
    ErrorStrategy,
    ReplayConfig,
    ReplayEngine,
    ReplayResult,
    ReplayState,
    StepResult,
)
from process_recorder.vision.base import ElementLocation


# ── Mock Vision ──────────────────────────────────────────────────────

class MockVision:
    def __init__(self, always_find=True):
        self._always_find = always_find
        self.find_element = AsyncMock()
        self.analyze_screenshot = AsyncMock()
        self.describe_action = AsyncMock(return_value="test action")
        self.is_available = AsyncMock(return_value=True)
        self.get_model_name = MagicMock(return_value="mock:test")

        if always_find:
            self.find_element.return_value = ElementLocation(
                found=True, x=100, y=50, width=80, height=30,
                confidence=0.9, description="Found",
            )
        else:
            self.find_element.return_value = ElementLocation(found=False)


# ── Mock Backend ─────────────────────────────────────────────────────

class MockBackend:
    def __init__(self):
        self.calls = []

    def moveTo(self, x, y, duration=0):
        self.calls.append(("moveTo", x, y))

    def click(self, x=None, y=None, button="left", clicks=1, interval=0.1):
        self.calls.append(("click", x, y, button))

    def write(self, text, interval=0.05):
        self.calls.append(("write", text))

    def typewrite(self, text, interval=0.05):
        self.calls.append(("typewrite", text))

    def hotkey(self, *keys):
        self.calls.append(("hotkey", keys))

    def scroll(self, amount, x=None, y=None):
        self.calls.append(("scroll", amount))


# ── Fixtures ──────────────────────────────────────────────────────────

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


@pytest.fixture
def mock_vision():
    return MockVision(always_find=True)


@pytest.fixture
def capture_fn():
    return MagicMock(return_value=FAKE_PNG)


@pytest.fixture
def fast_config():
    return ReplayConfig(
        error_strategy=ErrorStrategy.STOP,
        finder_config=FinderConfig(
            timeout_ms=200, retry_interval_ms=20,
            max_retries=3, confidence_threshold=0.5,
        ),
        executor_config=ExecutorConfig(
            action_delay_ms=0, move_duration_ms=0,
        ),
    )


@pytest.fixture
def engine(mock_vision, capture_fn, fast_config):
    e = ReplayEngine(mock_vision, config=fast_config, capture_fn=capture_fn)
    # Inject mock backend directly
    e._executor._backend = MockBackend()
    e._executor._initialized = True
    return e


def make_workflow(steps: list[SemanticStep] | None = None) -> Workflow:
    if steps is None:
        steps = [
            SemanticStep(
                step_id=1,
                action_type=ActionType.CLICK,
                target_description="Save button",
                target_screenshot_id="sc_001",
                target_region=BoundingBox(x=100, y=50, width=80, height=30),
                confidence=0.9,
            ),
        ]
    return Workflow(
        workflow_id="wf_test_001",
        name="Test Workflow",
        description="A test workflow",
        created_at=datetime(2026, 1, 30),
        steps=steps,
        source_recording_id="rec_001",
        model_used="mock:test",
    )


def make_step(
    action_type: ActionType,
    desc: str = "test element",
    input_data: str | None = None,
    step_id: int = 1,
) -> SemanticStep:
    return SemanticStep(
        step_id=step_id,
        action_type=action_type,
        target_description=desc,
        target_screenshot_id="sc_001",
        target_region=BoundingBox(x=100, y=50, width=80, height=30),
        input_data=input_data,
        confidence=0.9,
    )


# ── Basic Replay ─────────────────────────────────────────────────────

class TestBasicReplay:
    @pytest.mark.asyncio
    async def test_empty_workflow(self, engine):
        workflow = make_workflow(steps=[])
        result = await engine.replay(workflow)

        assert result.state == ReplayState.COMPLETED
        assert result.total_steps == 0
        assert result.completed_steps == 0

    @pytest.mark.asyncio
    async def test_single_click_step(self, engine):
        workflow = make_workflow()
        result = await engine.replay(workflow)

        assert result.state == ReplayState.COMPLETED
        assert result.total_steps == 1
        assert result.completed_steps == 1
        assert result.failed_steps == 0

    @pytest.mark.asyncio
    async def test_multiple_steps(self, engine):
        steps = [
            make_step(ActionType.CLICK, "Button 1", step_id=1),
            make_step(ActionType.TYPE, "Text field", input_data="Hello", step_id=2),
            make_step(ActionType.HOTKEY, "Save shortcut", input_data="ctrl+s", step_id=3),
        ]
        workflow = make_workflow(steps=steps)
        result = await engine.replay(workflow)

        assert result.state == ReplayState.COMPLETED
        assert result.total_steps == 3
        assert result.completed_steps == 3

    @pytest.mark.asyncio
    async def test_type_step(self, engine):
        steps = [make_step(ActionType.TYPE, "Name field", input_data="Edwin")]
        workflow = make_workflow(steps=steps)
        result = await engine.replay(workflow)

        assert result.completed_steps == 1
        backend = engine._executor._backend
        assert any(c[0] == "write" and c[1] == "Edwin" for c in backend.calls)

    @pytest.mark.asyncio
    async def test_hotkey_step(self, engine):
        steps = [make_step(ActionType.HOTKEY, "Save", input_data="ctrl+s")]
        workflow = make_workflow(steps=steps)
        result = await engine.replay(workflow)

        assert result.completed_steps == 1
        backend = engine._executor._backend
        assert any(c[0] == "hotkey" for c in backend.calls)

    @pytest.mark.asyncio
    async def test_scroll_step(self, engine):
        steps = [make_step(ActionType.SCROLL, "Scroll down")]
        workflow = make_workflow(steps=steps)
        result = await engine.replay(workflow)

        assert result.completed_steps == 1


# ── Replay Metadata ──────────────────────────────────────────────────

class TestReplayMetadata:
    @pytest.mark.asyncio
    async def test_has_timestamps(self, engine):
        result = await engine.replay(make_workflow())
        assert result.started_at is not None
        assert result.finished_at is not None
        assert result.finished_at >= result.started_at

    @pytest.mark.asyncio
    async def test_elapsed_time(self, engine):
        result = await engine.replay(make_workflow())
        assert result.total_elapsed_ms >= 0

    @pytest.mark.asyncio
    async def test_workflow_id_preserved(self, engine):
        result = await engine.replay(make_workflow())
        assert result.workflow_id == "wf_test_001"
        assert result.workflow_name == "Test Workflow"

    @pytest.mark.asyncio
    async def test_success_rate(self, engine):
        result = await engine.replay(make_workflow())
        assert result.success_rate == 1.0

    @pytest.mark.asyncio
    async def test_result_to_dict(self, engine):
        result = await engine.replay(make_workflow())
        d = result.to_dict()
        assert d["workflow_id"] == "wf_test_001"
        assert d["state"] == "completed"
        assert d["success_rate"] == 1.0


# ── Error Handling ───────────────────────────────────────────────────

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_stop_on_error(self, capture_fn):
        """With STOP strategy, replay halts on first failure."""
        vision = MockVision(always_find=False)
        config = ReplayConfig(
            error_strategy=ErrorStrategy.STOP,
            finder_config=FinderConfig(timeout_ms=100, retry_interval_ms=20, max_retries=2),
            executor_config=ExecutorConfig(action_delay_ms=0),
        )
        engine = ReplayEngine(vision, config=config, capture_fn=capture_fn)
        engine._executor._backend = MockBackend()
        engine._executor._initialized = True

        steps = [
            make_step(ActionType.CLICK, "Missing", step_id=1),
            make_step(ActionType.CLICK, "Also missing", step_id=2),
        ]
        # Remove target_region so no fallback
        steps[0].target_region = None
        steps[1].target_region = None

        result = await engine.replay(make_workflow(steps=steps))
        assert result.state == ReplayState.FAILED
        assert result.failed_steps == 1
        assert len(result.step_results) == 1  # Stopped after first

    @pytest.mark.asyncio
    async def test_skip_on_error(self, capture_fn):
        """With SKIP strategy, replay continues past failures."""
        vision = MockVision(always_find=False)
        config = ReplayConfig(
            error_strategy=ErrorStrategy.SKIP,
            finder_config=FinderConfig(timeout_ms=100, retry_interval_ms=20, max_retries=2),
            executor_config=ExecutorConfig(action_delay_ms=0),
        )
        engine = ReplayEngine(vision, config=config, capture_fn=capture_fn)
        engine._executor._backend = MockBackend()
        engine._executor._initialized = True

        steps = [
            make_step(ActionType.CLICK, "Missing", step_id=1),
            make_step(ActionType.TYPE, "Field", input_data="Hello", step_id=2),
        ]
        steps[0].target_region = None

        result = await engine.replay(make_workflow(steps=steps))
        assert result.state == ReplayState.COMPLETED
        assert result.failed_steps == 1
        assert result.completed_steps == 1
        assert len(result.step_results) == 2

    @pytest.mark.asyncio
    async def test_fallback_to_recorded_coordinates(self, capture_fn):
        """When vision can't find element, uses recorded coords."""
        vision = MockVision(always_find=False)
        config = ReplayConfig(
            error_strategy=ErrorStrategy.STOP,
            finder_config=FinderConfig(timeout_ms=100, retry_interval_ms=20, max_retries=2),
            executor_config=ExecutorConfig(action_delay_ms=0),
        )
        engine = ReplayEngine(vision, config=config, capture_fn=capture_fn)
        engine._executor._backend = MockBackend()
        engine._executor._initialized = True

        # Step has target_region, so fallback should work
        steps = [make_step(ActionType.CLICK, "Hidden button")]
        result = await engine.replay(make_workflow(steps=steps))

        assert result.completed_steps == 1  # Used recorded coords


# ── Pause / Resume / Stop ────────────────────────────────────────────

class TestReplayControl:
    @pytest.mark.asyncio
    async def test_initial_state(self, engine):
        assert engine.state == ReplayState.IDLE

    @pytest.mark.asyncio
    async def test_running_state(self, engine):
        # We'll check state via callback
        states_seen = []

        config = ReplayConfig(
            finder_config=FinderConfig(timeout_ms=200, retry_interval_ms=20, max_retries=3),
            executor_config=ExecutorConfig(action_delay_ms=0),
            step_callback=lambda i, step, result: states_seen.append(engine.state),
        )
        engine._config = config

        await engine.replay(make_workflow())
        assert ReplayState.RUNNING in states_seen or engine.state == ReplayState.COMPLETED

    @pytest.mark.asyncio
    async def test_stop_request(self, engine):
        """Stop should prevent further steps."""
        import asyncio

        steps = [make_step(ActionType.CLICK, f"Button {i}", step_id=i) for i in range(10)]
        workflow = make_workflow(steps=steps)

        # Stop after 2 steps
        call_count = 0
        def on_step(i, step, result):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                engine.stop()

        engine._config.step_callback = on_step
        result = await engine.replay(workflow)

        assert result.state == ReplayState.STOPPED
        assert len(result.step_results) < 10


# ── Save Report ──────────────────────────────────────────────────────

class TestSaveReport:
    @pytest.mark.asyncio
    async def test_replay_and_save(self, engine, tmp_path):
        workflow = make_workflow()
        result = await engine.replay_and_save(workflow, output_dir=tmp_path)

        assert result.state == ReplayState.COMPLETED

        # Check report file exists
        files = list(tmp_path.glob("replay_*.json"))
        assert len(files) == 1

        data = json.loads(files[0].read_text())
        assert data["workflow_id"] == "wf_test_001"
        assert data["state"] == "completed"

    @pytest.mark.asyncio
    async def test_save_creates_directory(self, engine, tmp_path):
        output_dir = tmp_path / "new" / "dir"
        await engine.replay_and_save(make_workflow(), output_dir=output_dir)
        assert output_dir.exists()


# ── Start Step ───────────────────────────────────────────────────────

class TestStartStep:
    @pytest.mark.asyncio
    async def test_start_from_step(self, engine):
        steps = [
            make_step(ActionType.CLICK, "Button 1", step_id=1),
            make_step(ActionType.CLICK, "Button 2", step_id=2),
            make_step(ActionType.CLICK, "Button 3", step_id=3),
        ]
        workflow = make_workflow(steps=steps)
        result = await engine.replay(workflow, start_step=1)

        # Should only execute steps 2 and 3
        assert result.total_steps == 3
        assert result.completed_steps == 2
        assert len(result.step_results) == 2


# ── Edge Cases ───────────────────────────────────────────────────────

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_type_without_text(self, engine):
        steps = [make_step(ActionType.TYPE, "Empty field", input_data="")]
        result = await engine.replay(make_workflow(steps=steps))
        assert result.skipped_steps == 1

    @pytest.mark.asyncio
    async def test_hotkey_without_combo(self, engine):
        steps = [make_step(ActionType.HOTKEY, "No combo", input_data="")]
        result = await engine.replay(make_workflow(steps=steps))
        assert result.skipped_steps == 1

    @pytest.mark.asyncio
    async def test_replay_result_empty_success_rate(self):
        result = ReplayResult(
            workflow_id="test", workflow_name="test",
            state=ReplayState.COMPLETED,
        )
        assert result.success_rate == 0.0
