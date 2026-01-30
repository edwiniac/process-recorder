"""
Tests for the semantic extractor module.

Verifies that classified actions are enriched with vision context
and converted into meaningful semantic steps.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from process_recorder.learner.action_classifier import ClassifiedAction
from process_recorder.learner.semantic_extractor import SemanticExtractor
from process_recorder.models import ActionType, Screenshot
from process_recorder.vision.base import AnalysisResult, ElementLocation, VisionAdapter


# ── Mock Vision Adapter ──────────────────────────────────────────────

class MockVisionAdapter(VisionAdapter):
    """A mock vision adapter for testing."""

    def __init__(self):
        self.analyze_calls = []
        self.find_calls = []
        self._click_context = {
            "element": "Save button",
            "element_type": "button",
            "confidence": 0.9,
        }

    async def analyze_screenshot(self, image_data, prompt=None):
        self.analyze_calls.append((image_data, prompt))
        return AnalysisResult(
            description="A text editor window",
            ui_elements=[{"type": "button", "label": "Save"}],
            active_window="Notepad",
            raw_response='{"field": "filename input", "confidence": 0.85}',
            model="mock:test",
        )

    async def find_element(self, image_data, element_description):
        self.find_calls.append((image_data, element_description))
        return ElementLocation(
            found=True, x=100, y=50,
            width=80, height=30,
            confidence=0.95,
            description="Found element",
        )

    async def describe_action(self, before_image, after_image, click_x, click_y):
        return "Clicked the Save button"

    async def get_click_context(self, image_data, click_x, click_y):
        return self._click_context

    async def is_available(self):
        return True

    def get_model_name(self):
        return "mock:test"


# ── Fixtures ──────────────────────────────────────────────────────────

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


@pytest.fixture
def mock_vision():
    return MockVisionAdapter()


@pytest.fixture
def extractor(mock_vision):
    return SemanticExtractor(mock_vision)


@pytest.fixture
def screenshots():
    return {
        "sc_001": Screenshot(
            screenshot_id="sc_001",
            timestamp=1000.0,
            filepath="screenshots/0001.png",
            width=1920,
            height=1080,
        ),
        "sc_002": Screenshot(
            screenshot_id="sc_002",
            timestamp=1001.0,
            filepath="screenshots/0002.png",
            width=1920,
            height=1080,
        ),
    }


@pytest.fixture
def screenshot_dir(tmp_path):
    """Create a temp dir with fake screenshots."""
    ss_dir = tmp_path / "screenshots"
    ss_dir.mkdir()
    (ss_dir / "0001.png").write_bytes(FAKE_PNG)
    (ss_dir / "0002.png").write_bytes(FAKE_PNG)
    return tmp_path  # Return parent since filepath includes "screenshots/"


def make_action(
    action_type: ActionType,
    screenshot_id: str = "sc_001",
    **kwargs,
) -> ClassifiedAction:
    return ClassifiedAction(
        action_type=action_type,
        timestamp=1000.0,
        end_timestamp=1000.0,
        screenshot_id=screenshot_id,
        **kwargs,
    )


# ── Click Step Extraction ────────────────────────────────────────────

class TestClickExtraction:
    @pytest.mark.asyncio
    async def test_click_step_with_vision(self, extractor, screenshots, screenshot_dir):
        action = make_action(ActionType.CLICK, click_x=100, click_y=200)
        step = await extractor.extract_step(
            action, step_id=1,
            screenshots=screenshots,
            screenshot_dir=screenshot_dir,
        )

        assert step.step_id == 1
        assert step.action_type == ActionType.CLICK
        assert "Save button" in step.target_description
        assert step.confidence > 0
        assert step.target_region is not None
        assert step.input_data is None

    @pytest.mark.asyncio
    async def test_click_without_screenshot(self, extractor):
        action = make_action(ActionType.CLICK, screenshot_id="", click_x=100, click_y=200)
        step = await extractor.extract_step(
            action, step_id=1,
            screenshots={},
            screenshot_dir=None,
        )

        # Should fallback to coordinate-based description
        assert "100" in step.target_description
        assert "200" in step.target_description
        assert step.confidence == 0.3  # Low confidence fallback

    @pytest.mark.asyncio
    async def test_right_click_description(self, extractor, screenshots, screenshot_dir):
        action = make_action(ActionType.CLICK, click_x=100, click_y=200, button="right")
        step = await extractor.extract_step(
            action, step_id=1,
            screenshots=screenshots,
            screenshot_dir=screenshot_dir,
        )
        assert "Right-click" in step.target_description


# ── Typing Step Extraction ───────────────────────────────────────────

class TestTypingExtraction:
    @pytest.mark.asyncio
    async def test_type_step_with_vision(self, extractor, screenshots, screenshot_dir):
        action = make_action(ActionType.TYPE, typed_text="Hello World")
        step = await extractor.extract_step(
            action, step_id=2,
            screenshots=screenshots,
            screenshot_dir=screenshot_dir,
        )

        assert step.action_type == ActionType.TYPE
        assert step.input_data == "Hello World"
        assert "Type" in step.target_description

    @pytest.mark.asyncio
    async def test_type_step_without_vision(self, extractor):
        action = make_action(ActionType.TYPE, screenshot_id="", typed_text="test")
        step = await extractor.extract_step(
            action, step_id=1,
            screenshots={},
        )

        assert step.input_data == "test"
        assert "Type" in step.target_description

    @pytest.mark.asyncio
    async def test_long_text_truncated_in_description(self, extractor):
        long_text = "A" * 100
        action = make_action(ActionType.TYPE, screenshot_id="", typed_text=long_text)
        step = await extractor.extract_step(
            action, step_id=1,
            screenshots={},
        )

        # Description should not contain the full 100-char text
        assert len(step.target_description) < len(long_text) + 20
        assert step.input_data == long_text  # Full text preserved in input_data


# ── Scroll Step Extraction ───────────────────────────────────────────

class TestScrollExtraction:
    @pytest.mark.asyncio
    async def test_scroll_down(self, extractor, screenshots, screenshot_dir):
        action = make_action(ActionType.SCROLL, scroll_dy=-5)
        step = await extractor.extract_step(
            action, step_id=3,
            screenshots=screenshots,
            screenshot_dir=screenshot_dir,
        )

        assert step.action_type == ActionType.SCROLL
        assert "down" in step.target_description.lower()

    @pytest.mark.asyncio
    async def test_scroll_up(self, extractor):
        action = make_action(ActionType.SCROLL, screenshot_id="", scroll_dy=5)
        step = await extractor.extract_step(action, step_id=1, screenshots={})
        assert "up" in step.target_description.lower()

    @pytest.mark.asyncio
    async def test_scroll_horizontal(self, extractor):
        action = make_action(ActionType.SCROLL, screenshot_id="", scroll_dx=5, scroll_dy=-3)
        step = await extractor.extract_step(action, step_id=1, screenshots={})
        assert "right" in step.target_description.lower() or "down" in step.target_description.lower()


# ── Hotkey Step Extraction ───────────────────────────────────────────

class TestHotkeyExtraction:
    @pytest.mark.asyncio
    async def test_ctrl_s(self, extractor, screenshots, screenshot_dir):
        action = make_action(ActionType.HOTKEY, hotkey_combo="ctrl+s")
        step = await extractor.extract_step(
            action, step_id=4,
            screenshots=screenshots,
            screenshot_dir=screenshot_dir,
        )

        assert step.action_type == ActionType.HOTKEY
        assert step.input_data == "ctrl+s"
        assert "Save" in step.target_description

    @pytest.mark.asyncio
    async def test_ctrl_c(self, extractor):
        action = make_action(ActionType.HOTKEY, screenshot_id="", hotkey_combo="ctrl+c")
        step = await extractor.extract_step(action, step_id=1, screenshots={})
        assert "Copy" in step.target_description

    @pytest.mark.asyncio
    async def test_unknown_hotkey(self, extractor):
        action = make_action(ActionType.HOTKEY, screenshot_id="", hotkey_combo="ctrl+shift+k")
        step = await extractor.extract_step(action, step_id=1, screenshots={})
        assert "ctrl+shift+k" in step.target_description


# ── Batch Extraction ─────────────────────────────────────────────────

class TestBatchExtraction:
    @pytest.mark.asyncio
    async def test_extract_multiple_steps(self, extractor, screenshots, screenshot_dir):
        actions = [
            make_action(ActionType.CLICK, click_x=100, click_y=200),
            make_action(ActionType.TYPE, typed_text="Hello", screenshot_id="sc_002"),
            make_action(ActionType.HOTKEY, hotkey_combo="ctrl+s", screenshot_id=""),
        ]

        steps = await extractor.extract_steps(
            actions, screenshots, screenshot_dir
        )

        assert len(steps) == 3
        assert steps[0].step_id == 1
        assert steps[1].step_id == 2
        assert steps[2].step_id == 3

    @pytest.mark.asyncio
    async def test_extract_empty_list(self, extractor):
        steps = await extractor.extract_steps([], {})
        assert steps == []


# ── Vision Failure Handling ──────────────────────────────────────────

class TestVisionFailure:
    @pytest.mark.asyncio
    async def test_graceful_fallback_on_vision_error(self, screenshots, screenshot_dir):
        """If vision fails, should fall back to data-based description."""

        class FailingVision(MockVisionAdapter):
            async def get_click_context(self, image_data, click_x, click_y):
                raise RuntimeError("Model crashed")

            async def analyze_screenshot(self, image_data, prompt=None):
                raise RuntimeError("Model crashed")

        extractor = SemanticExtractor(FailingVision())
        action = make_action(ActionType.CLICK, click_x=100, click_y=200)

        step = await extractor.extract_step(
            action, step_id=1,
            screenshots=screenshots,
            screenshot_dir=screenshot_dir,
        )

        # Should still produce a step with fallback description
        assert step.step_id == 1
        assert step.action_type == ActionType.CLICK
        assert "100" in step.target_description  # Coordinate fallback
