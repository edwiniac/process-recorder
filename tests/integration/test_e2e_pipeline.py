"""
End-to-end integration tests.

Tests the full pipeline: record events → classify → extract → build workflow → replay.
All tests use mocks for vision and input, so they run without a display.
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from process_recorder.learner.action_classifier import classify_events
from process_recorder.learner.semantic_extractor import SemanticExtractor
from process_recorder.learner.workflow_processor import WorkflowProcessor
from process_recorder.models import (
    ActionType,
    EventType,
    RawEvent,
    Recording,
    Screenshot,
    SemanticStep,
    Workflow,
)
from process_recorder.replayer.action_executor import ActionExecutor, ExecutorConfig
from process_recorder.replayer.element_finder import ElementFinder, FinderConfig
from process_recorder.replayer.replay_engine import (
    ErrorStrategy,
    ReplayConfig,
    ReplayEngine,
    ReplayState,
)
from process_recorder.vision.base import AnalysisResult, ElementLocation


# ── Shared Mocks ─────────────────────────────────────────────────────

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


class MockVision:
    """Full mock vision for E2E tests."""

    def __init__(self):
        self.find_element = AsyncMock(
            return_value=ElementLocation(
                found=True, x=100, y=50, width=80, height=30,
                confidence=0.9, description="Found element",
            )
        )
        self.analyze_screenshot = AsyncMock(
            return_value=AnalysisResult(
                description="Test screen",
                ui_elements=[],
                raw_response='{"field": "text input", "confidence": 0.8}',
                model="mock:test",
            )
        )
        self.describe_action = AsyncMock(return_value="Clicked a button")
        self.is_available = AsyncMock(return_value=True)
        self.get_model_name = MagicMock(return_value="mock:test")

    async def get_click_context(self, image_data, click_x, click_y):
        return {
            "element": f"element at ({click_x}, {click_y})",
            "element_type": "button",
            "confidence": 0.85,
        }


class MockBackend:
    """Mock pyautogui backend."""

    def __init__(self):
        self.actions = []

    def moveTo(self, x, y, duration=0):
        self.actions.append(("move", x, y))

    def click(self, x=None, y=None, button="left", clicks=1, interval=0.1):
        self.actions.append(("click", x, y, button))

    def write(self, text, interval=0.05):
        self.actions.append(("write", text))

    def typewrite(self, text, interval=0.05):
        self.actions.append(("typewrite", text))

    def hotkey(self, *keys):
        self.actions.append(("hotkey", keys))

    def scroll(self, amount, x=None, y=None):
        self.actions.append(("scroll", amount))


# ── Fixtures ──────────────────────────────────────────────────────────

def make_notepad_recording() -> Recording:
    """Simulate recording a Notepad 'Hello World' task."""
    return Recording(
        recording_id="rec_notepad_001",
        name="Notepad Hello World",
        created_at=datetime(2026, 1, 30, 12, 0, 0),
        events=[
            # Click on Notepad in taskbar
            RawEvent(1.0, EventType.CLICK,
                     {"x": 500, "y": 750, "button": "left"}, "sc_001"),
            # Click in text area
            RawEvent(3.0, EventType.CLICK,
                     {"x": 400, "y": 300, "button": "left"}, "sc_002"),
            # Type Hello World
            RawEvent(4.0, EventType.KEY_TYPE,
                     {"text": "Hello World"}, "sc_003"),
            # Ctrl+S (Save)
            RawEvent(6.0, EventType.KEY_PRESS,
                     {"key": "ctrl"}, None),
            RawEvent(6.05, EventType.KEY_PRESS,
                     {"key": "s"}, None),
            # Type filename
            RawEvent(8.0, EventType.KEY_TYPE,
                     {"text": "hello.txt"}, "sc_004"),
            # Click Save button
            RawEvent(10.0, EventType.CLICK,
                     {"x": 600, "y": 400, "button": "left"}, "sc_005"),
        ],
        screenshots=[
            Screenshot("sc_001", 1.0, "screenshots/0001.png", 1920, 1080),
            Screenshot("sc_002", 3.0, "screenshots/0002.png", 1920, 1080),
            Screenshot("sc_003", 4.0, "screenshots/0003.png", 1920, 1080),
            Screenshot("sc_004", 8.0, "screenshots/0004.png", 1920, 1080),
            Screenshot("sc_005", 10.0, "screenshots/0005.png", 1920, 1080),
        ],
        duration_ms=10000,
    )


def make_browser_recording() -> Recording:
    """Simulate recording a browser navigation task."""
    return Recording(
        recording_id="rec_browser_001",
        name="Google Search",
        created_at=datetime(2026, 1, 30, 12, 5, 0),
        events=[
            # Click address bar
            RawEvent(1.0, EventType.CLICK,
                     {"x": 400, "y": 50, "button": "left"}, "sc_001"),
            # Type URL
            RawEvent(2.0, EventType.KEY_TYPE,
                     {"text": "https://google.com"}, "sc_002"),
            # Press Enter
            RawEvent(3.0, EventType.KEY_PRESS,
                     {"key": "enter"}, None),
            # Click search box
            RawEvent(5.0, EventType.CLICK,
                     {"x": 500, "y": 400, "button": "left"}, "sc_003"),
            # Type search query
            RawEvent(6.0, EventType.KEY_TYPE,
                     {"text": "ProcessRecorder automation"}, "sc_004"),
            # Press Enter to search
            RawEvent(8.0, EventType.KEY_PRESS,
                     {"key": "enter"}, None),
            # Scroll down results
            RawEvent(10.0, EventType.SCROLL,
                     {"dx": 0, "dy": -5}, "sc_005"),
            RawEvent(10.2, EventType.SCROLL,
                     {"dx": 0, "dy": -5}, None),
            # Click a result
            RawEvent(12.0, EventType.CLICK,
                     {"x": 400, "y": 350, "button": "left"}, "sc_006"),
        ],
        screenshots=[
            Screenshot(f"sc_{i:03d}", float(i * 2), f"screenshots/{i:04d}.png", 1920, 1080)
            for i in range(1, 7)
        ],
        duration_ms=12000,
    )


@pytest.fixture
def screenshot_dir(tmp_path):
    ss_dir = tmp_path / "screenshots"
    ss_dir.mkdir()
    for i in range(1, 10):
        (ss_dir / f"{i:04d}.png").write_bytes(FAKE_PNG)
    return tmp_path


# ── E2E-01: Notepad Hello World Pipeline ─────────────────────────────

class TestE2E_NotepadPipeline:
    """Full pipeline: recording → classify → extract → workflow → replay."""

    @pytest.mark.asyncio
    async def test_full_notepad_pipeline(self, screenshot_dir, tmp_path):
        recording = make_notepad_recording()
        vision = MockVision()

        # Step 1: Classify events
        actions = classify_events(recording.events)
        assert len(actions) >= 4  # Click, Click, Type, Hotkey, Type, Click

        # Step 2: Build workflow
        processor = WorkflowProcessor(vision)
        workflow = await processor.process_and_save(
            recording,
            screenshot_dir=screenshot_dir,
            output_dir=tmp_path / "workflows",
            name="Notepad Hello World",
        )

        assert workflow.name == "Notepad Hello World"
        assert len(workflow.steps) >= 4
        assert workflow.source_recording_id == "rec_notepad_001"

        # Verify step types
        action_types = [s.action_type for s in workflow.steps]
        assert ActionType.CLICK in action_types
        assert ActionType.TYPE in action_types

        # Step 3: Save and load roundtrip
        wf_path = tmp_path / "workflows" / f"{workflow.workflow_id}.json"
        assert wf_path.exists()

        loaded_data = json.loads(wf_path.read_text())
        loaded_wf = Workflow.from_dict(loaded_data)
        assert loaded_wf.name == workflow.name
        assert len(loaded_wf.steps) == len(workflow.steps)

        # Step 4: Replay the workflow
        backend = MockBackend()
        replay_config = ReplayConfig(
            error_strategy=ErrorStrategy.SKIP,
            finder_config=FinderConfig(
                timeout_ms=200, retry_interval_ms=20, max_retries=2,
            ),
            executor_config=ExecutorConfig(action_delay_ms=0),
        )

        engine = ReplayEngine(
            vision, config=replay_config,
            capture_fn=lambda: FAKE_PNG,
        )
        engine._executor._backend = backend
        engine._executor._initialized = True

        result = await engine.replay(loaded_wf)

        assert result.state in (ReplayState.COMPLETED, ReplayState.FAILED)
        assert result.total_steps == len(loaded_wf.steps)
        assert result.completed_steps > 0

        # Verify actions were executed
        assert len(backend.actions) > 0


# ── E2E-02: Browser Navigation Pipeline ──────────────────────────────

class TestE2E_BrowserPipeline:
    @pytest.mark.asyncio
    async def test_full_browser_pipeline(self, screenshot_dir, tmp_path):
        recording = make_browser_recording()
        vision = MockVision()

        # Process recording
        processor = WorkflowProcessor(vision)
        workflow = await processor.process(recording, screenshot_dir)

        assert workflow.name is not None
        assert len(workflow.steps) >= 5  # Clicks + Types + Scrolls

        # Check for scroll step
        assert any(s.action_type == ActionType.SCROLL for s in workflow.steps)

        # Replay
        backend = MockBackend()
        config = ReplayConfig(
            error_strategy=ErrorStrategy.SKIP,
            finder_config=FinderConfig(timeout_ms=200, retry_interval_ms=20, max_retries=2),
            executor_config=ExecutorConfig(action_delay_ms=0),
        )
        engine = ReplayEngine(vision, config=config, capture_fn=lambda: FAKE_PNG)
        engine._executor._backend = backend
        engine._executor._initialized = True

        result = await engine.replay(workflow)
        assert result.completed_steps > 0


# ── E2E-03: Offline Mode (No Vision) ─────────────────────────────────

class TestE2E_OfflineMode:
    @pytest.mark.asyncio
    async def test_pipeline_without_vision(self, tmp_path):
        """Should still produce a workflow with fallback descriptions."""
        recording = make_notepad_recording()

        # Vision that always fails
        class FailingVision(MockVision):
            async def get_click_context(self, *args):
                raise RuntimeError("No model")
            async def analyze_screenshot(self, *args):
                raise RuntimeError("No model")

        vision = FailingVision()
        processor = WorkflowProcessor(vision)
        workflow = await processor.process(recording)

        # Should still produce steps with coordinate-based descriptions
        assert len(workflow.steps) >= 4
        for step in workflow.steps:
            assert step.target_description  # Not empty


# ── E2E-04: Serialization Roundtrip ──────────────────────────────────

class TestE2E_Serialization:
    @pytest.mark.asyncio
    async def test_recording_to_workflow_to_json_roundtrip(self, screenshot_dir, tmp_path):
        recording = make_notepad_recording()
        vision = MockVision()

        processor = WorkflowProcessor(vision)
        workflow = await processor.process_and_save(
            recording,
            screenshot_dir=screenshot_dir,
            output_dir=tmp_path,
        )

        # Save
        data = workflow.to_dict()
        json_str = json.dumps(data, indent=2, default=str)
        assert len(json_str) > 100

        # Load
        loaded = Workflow.from_dict(json.loads(json_str))
        assert loaded.workflow_id == workflow.workflow_id
        assert loaded.name == workflow.name
        assert len(loaded.steps) == len(workflow.steps)

        for orig, loaded_step in zip(workflow.steps, loaded.steps):
            assert orig.step_id == loaded_step.step_id
            assert orig.action_type == loaded_step.action_type
            assert orig.input_data == loaded_step.input_data


# ── E2E-05: Replay Report Saving ─────────────────────────────────────

class TestE2E_ReplayReport:
    @pytest.mark.asyncio
    async def test_replay_saves_report(self, screenshot_dir, tmp_path):
        recording = make_notepad_recording()
        vision = MockVision()

        # Build workflow
        processor = WorkflowProcessor(vision)
        workflow = await processor.process(recording, screenshot_dir)

        # Replay and save
        backend = MockBackend()
        config = ReplayConfig(
            error_strategy=ErrorStrategy.SKIP,
            finder_config=FinderConfig(timeout_ms=200, retry_interval_ms=20, max_retries=2),
            executor_config=ExecutorConfig(action_delay_ms=0),
        )
        engine = ReplayEngine(vision, config=config, capture_fn=lambda: FAKE_PNG)
        engine._executor._backend = backend
        engine._executor._initialized = True

        report_dir = tmp_path / "reports"
        result = await engine.replay_and_save(workflow, output_dir=report_dir)

        # Check report file
        reports = list(report_dir.glob("replay_*.json"))
        assert len(reports) == 1

        report = json.loads(reports[0].read_text())
        assert report["workflow_id"] == workflow.workflow_id
        assert "success_rate" in report
        assert report["total_steps"] == len(workflow.steps)


# ── E2E-06: Controller Integration ───────────────────────────────────

class TestE2E_Controller:
    def test_controller_creates_and_stops(self):
        from process_recorder.controller.app_controller import AppController
        from process_recorder.models import AppConfig

        config = AppConfig()
        controller = AppController(config)
        controller.start()

        assert controller._async_loop is not None
        assert controller._async_loop.is_running()

        controller.stop()
