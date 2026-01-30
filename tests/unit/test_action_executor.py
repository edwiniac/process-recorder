"""
Tests for the action executor module.

Verifies mouse/keyboard action execution with mock backends,
dry-run mode, and error handling.
"""

import pytest

from process_recorder.replayer.action_executor import (
    ActionExecutor,
    ExecutionResult,
    ExecutionStatus,
    ExecutorConfig,
)


# ── Mock Backend ─────────────────────────────────────────────────────

class MockBackend:
    """Mock pyautogui-like backend for testing."""

    def __init__(self):
        self.calls = []
        self.fail_on = None  # Set to action name to simulate failure

    def moveTo(self, x, y, duration=0):
        self.calls.append(("moveTo", x, y, duration))

    def click(self, x=None, y=None, button="left", clicks=1, interval=0.1):
        if self.fail_on == "click":
            raise RuntimeError("Click failed!")
        self.calls.append(("click", x, y, button, clicks))

    def write(self, text, interval=0.05):
        if self.fail_on == "type":
            raise RuntimeError("Type failed!")
        self.calls.append(("write", text, interval))

    def typewrite(self, text, interval=0.05):
        self.write(text, interval)

    def hotkey(self, *keys):
        if self.fail_on == "hotkey":
            raise RuntimeError("Hotkey failed!")
        self.calls.append(("hotkey", keys))

    def scroll(self, amount, x=None, y=None):
        if self.fail_on == "scroll":
            raise RuntimeError("Scroll failed!")
        self.calls.append(("scroll", amount, x, y))

    def hscroll(self, amount, x=None, y=None):
        self.calls.append(("hscroll", amount, x, y))


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def backend():
    return MockBackend()


@pytest.fixture
def executor(backend):
    config = ExecutorConfig(
        action_delay_ms=0,
        type_interval_ms=10,
        click_duration_ms=50,
        move_duration_ms=0,
    )
    return ActionExecutor(config=config, input_backend=backend)


@pytest.fixture
def dry_executor(backend):
    config = ExecutorConfig(dry_run=True)
    return ActionExecutor(config=config, input_backend=backend)


# ── Click Tests ──────────────────────────────────────────────────────

class TestClick:
    @pytest.mark.asyncio
    async def test_left_click(self, executor, backend):
        result = await executor.click(100, 200)
        assert result.status == ExecutionStatus.SUCCESS
        assert result.action_type == "click"
        assert ("click", 100, 200, "left", 1) in backend.calls

    @pytest.mark.asyncio
    async def test_right_click(self, executor, backend):
        result = await executor.click(100, 200, button="right")
        assert result.status == ExecutionStatus.SUCCESS
        assert ("click", 100, 200, "right", 1) in backend.calls

    @pytest.mark.asyncio
    async def test_double_click(self, executor, backend):
        result = await executor.click(100, 200, clicks=2)
        assert result.status == ExecutionStatus.SUCCESS
        assert ("click", 100, 200, "left", 2) in backend.calls

    @pytest.mark.asyncio
    async def test_click_moves_first(self, executor, backend):
        await executor.click(300, 400)
        # moveTo should be called before click
        move_idx = next(i for i, c in enumerate(backend.calls) if c[0] == "moveTo")
        click_idx = next(i for i, c in enumerate(backend.calls) if c[0] == "click")
        assert move_idx < click_idx

    @pytest.mark.asyncio
    async def test_click_failure(self, executor, backend):
        backend.fail_on = "click"
        result = await executor.click(100, 200)
        assert result.status == ExecutionStatus.FAILED
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_click_elapsed_time(self, executor):
        result = await executor.click(100, 200)
        assert result.elapsed_ms >= 0


# ── Type Tests ───────────────────────────────────────────────────────

class TestType:
    @pytest.mark.asyncio
    async def test_type_text(self, executor, backend):
        result = await executor.type_text("Hello World")
        assert result.status == ExecutionStatus.SUCCESS
        assert result.action_type == "type"
        assert any(c[0] == "write" and c[1] == "Hello World" for c in backend.calls)

    @pytest.mark.asyncio
    async def test_type_empty_string(self, executor, backend):
        result = await executor.type_text("")
        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_type_long_text(self, executor, backend):
        long_text = "A" * 200
        result = await executor.type_text(long_text)
        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_type_failure(self, executor, backend):
        backend.fail_on = "type"
        result = await executor.type_text("fail")
        assert result.status == ExecutionStatus.FAILED

    @pytest.mark.asyncio
    async def test_type_description_truncated(self, executor):
        long_text = "A" * 100
        result = await executor.type_text(long_text)
        assert "..." in result.description


# ── Hotkey Tests ─────────────────────────────────────────────────────

class TestHotkey:
    @pytest.mark.asyncio
    async def test_ctrl_s(self, executor, backend):
        result = await executor.hotkey("ctrl+s")
        assert result.status == ExecutionStatus.SUCCESS
        assert ("hotkey", ("ctrl", "s")) in backend.calls

    @pytest.mark.asyncio
    async def test_alt_tab(self, executor, backend):
        result = await executor.hotkey("alt+tab")
        assert result.status == ExecutionStatus.SUCCESS
        assert ("hotkey", ("alt", "tab")) in backend.calls

    @pytest.mark.asyncio
    async def test_three_key_combo(self, executor, backend):
        result = await executor.hotkey("ctrl+shift+s")
        assert result.status == ExecutionStatus.SUCCESS
        assert ("hotkey", ("ctrl", "shift", "s")) in backend.calls

    @pytest.mark.asyncio
    async def test_hotkey_failure(self, executor, backend):
        backend.fail_on = "hotkey"
        result = await executor.hotkey("ctrl+q")
        assert result.status == ExecutionStatus.FAILED


# ── Scroll Tests ─────────────────────────────────────────────────────

class TestScroll:
    @pytest.mark.asyncio
    async def test_scroll_down(self, executor, backend):
        result = await executor.scroll(dy=-3)
        assert result.status == ExecutionStatus.SUCCESS
        assert ("scroll", -3, None, None) in backend.calls

    @pytest.mark.asyncio
    async def test_scroll_up(self, executor, backend):
        result = await executor.scroll(dy=5)
        assert result.status == ExecutionStatus.SUCCESS
        assert ("scroll", 5, None, None) in backend.calls

    @pytest.mark.asyncio
    async def test_scroll_at_position(self, executor, backend):
        result = await executor.scroll(dy=-3, x=100, y=200)
        assert result.status == ExecutionStatus.SUCCESS
        assert ("scroll", -3, 100, 200) in backend.calls

    @pytest.mark.asyncio
    async def test_horizontal_scroll(self, executor, backend):
        result = await executor.scroll(dx=5)
        assert result.status == ExecutionStatus.SUCCESS
        assert ("hscroll", 5, None, None) in backend.calls

    @pytest.mark.asyncio
    async def test_scroll_failure(self, executor, backend):
        backend.fail_on = "scroll"
        result = await executor.scroll(dy=-3)
        assert result.status == ExecutionStatus.FAILED


# ── Wait Tests ───────────────────────────────────────────────────────

class TestWait:
    @pytest.mark.asyncio
    async def test_wait(self, executor):
        result = await executor.wait(100)
        assert result.status == ExecutionStatus.SUCCESS
        assert result.action_type == "wait"
        assert result.elapsed_ms == 100.0


# ── Dry Run Mode ─────────────────────────────────────────────────────

class TestDryRun:
    @pytest.mark.asyncio
    async def test_dry_click(self, dry_executor, backend):
        result = await dry_executor.click(100, 200)
        assert result.status == ExecutionStatus.SUCCESS
        assert "[DRY RUN]" in result.description
        assert len(backend.calls) == 0  # Nothing actually executed

    @pytest.mark.asyncio
    async def test_dry_type(self, dry_executor, backend):
        result = await dry_executor.type_text("Hello")
        assert result.status == ExecutionStatus.SUCCESS
        assert "[DRY RUN]" in result.description
        assert len(backend.calls) == 0

    @pytest.mark.asyncio
    async def test_dry_hotkey(self, dry_executor, backend):
        result = await dry_executor.hotkey("ctrl+s")
        assert result.status == ExecutionStatus.SUCCESS
        assert "[DRY RUN]" in result.description
        assert len(backend.calls) == 0

    @pytest.mark.asyncio
    async def test_dry_scroll(self, dry_executor, backend):
        result = await dry_executor.scroll(dy=-3)
        assert result.status == ExecutionStatus.SUCCESS
        assert "[DRY RUN]" in result.description
        assert len(backend.calls) == 0


# ── ExecutionResult ──────────────────────────────────────────────────

class TestExecutionResult:
    def test_success_result(self):
        r = ExecutionResult(status=ExecutionStatus.SUCCESS, action_type="click")
        assert r.error is None

    def test_failed_result(self):
        r = ExecutionResult(
            status=ExecutionStatus.FAILED,
            action_type="click",
            error="Something broke",
        )
        assert r.error == "Something broke"
