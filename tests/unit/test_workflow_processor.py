"""
Tests for the workflow processor module.

Verifies the full pipeline: Recording → Workflow.
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

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
from process_recorder.vision.base import AnalysisResult, VisionAdapter


# ── Mock Vision ──────────────────────────────────────────────────────

class MockVision(VisionAdapter):
    """Minimal mock vision for processor tests."""

    async def analyze_screenshot(self, image_data, prompt=None):
        return AnalysisResult(
            description="Test analysis",
            ui_elements=[],
            raw_response='{"name": "Test Workflow", "description": "A test workflow", "application": "Test"}',
            model="mock:test",
        )

    async def find_element(self, image_data, element_description):
        from process_recorder.vision.base import ElementLocation
        return ElementLocation(found=False)

    async def describe_action(self, before_image, after_image, click_x, click_y):
        return "Test action"

    async def get_click_context(self, image_data, click_x, click_y):
        return {
            "element": "test element",
            "element_type": "button",
            "confidence": 0.8,
        }

    async def is_available(self):
        return True

    def get_model_name(self):
        return "mock:test"


# ── Fixtures ──────────────────────────────────────────────────────────

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


@pytest.fixture
def mock_vision():
    return MockVision()


@pytest.fixture
def processor(mock_vision):
    return WorkflowProcessor(mock_vision)


@pytest.fixture
def screenshot_dir(tmp_path):
    ss_dir = tmp_path / "screenshots"
    ss_dir.mkdir()
    (ss_dir / "0001.png").write_bytes(FAKE_PNG)
    (ss_dir / "0002.png").write_bytes(FAKE_PNG)
    return tmp_path


def make_recording(
    events: list[RawEvent] | None = None,
    screenshots: list[Screenshot] | None = None,
) -> Recording:
    return Recording(
        recording_id="rec_test_001",
        name="Test Recording",
        created_at=datetime(2026, 1, 30, 12, 0, 0),
        events=events or [],
        screenshots=screenshots or [],
        duration_ms=5000,
    )


def make_click_event(x: int, y: int, ts: float) -> RawEvent:
    return RawEvent(
        timestamp=ts,
        event_type=EventType.CLICK,
        data={"x": x, "y": y, "button": "left"},
        screenshot_id="sc_001",
    )


def make_type_event(text: str, ts: float) -> RawEvent:
    return RawEvent(
        timestamp=ts,
        event_type=EventType.KEY_TYPE,
        data={"text": text},
        screenshot_id="sc_002",
    )


SCREENSHOTS = [
    Screenshot("sc_001", 1000.0, "screenshots/0001.png", 1920, 1080),
    Screenshot("sc_002", 1001.0, "screenshots/0002.png", 1920, 1080),
]


# ── Basic Processing ─────────────────────────────────────────────────

class TestBasicProcessing:
    @pytest.mark.asyncio
    async def test_empty_recording(self, processor):
        recording = make_recording()
        workflow = await processor.process(recording)

        assert isinstance(workflow, Workflow)
        assert workflow.name == "Empty Workflow"
        assert len(workflow.steps) == 0
        assert workflow.source_recording_id == "rec_test_001"

    @pytest.mark.asyncio
    async def test_single_click(self, processor, screenshot_dir):
        recording = make_recording(
            events=[make_click_event(100, 200, 1000.0)],
            screenshots=SCREENSHOTS,
        )
        workflow = await processor.process(recording, screenshot_dir)

        assert len(workflow.steps) == 1
        assert workflow.steps[0].action_type == ActionType.CLICK
        assert workflow.model_used == "mock:test"

    @pytest.mark.asyncio
    async def test_click_and_type(self, processor, screenshot_dir):
        recording = make_recording(
            events=[
                make_click_event(100, 200, 1.0),
                make_type_event("Hello", 2.0),
            ],
            screenshots=SCREENSHOTS,
        )
        workflow = await processor.process(recording, screenshot_dir)

        assert len(workflow.steps) == 2
        assert workflow.steps[0].action_type == ActionType.CLICK
        assert workflow.steps[1].action_type == ActionType.TYPE
        assert workflow.steps[1].input_data == "Hello"


# ── Workflow Metadata ────────────────────────────────────────────────

class TestWorkflowMetadata:
    @pytest.mark.asyncio
    async def test_workflow_has_id(self, processor):
        recording = make_recording(events=[make_click_event(10, 20, 1.0)])
        workflow = await processor.process(recording)
        assert workflow.workflow_id  # Non-empty

    @pytest.mark.asyncio
    async def test_workflow_has_timestamp(self, processor):
        recording = make_recording(events=[make_click_event(10, 20, 1.0)])
        workflow = await processor.process(recording)
        assert isinstance(workflow.created_at, datetime)

    @pytest.mark.asyncio
    async def test_custom_name(self, processor):
        recording = make_recording(events=[make_click_event(10, 20, 1.0)])
        workflow = await processor.process(recording, name="My Custom Workflow")
        assert workflow.name == "My Custom Workflow"

    @pytest.mark.asyncio
    async def test_source_recording_linked(self, processor):
        recording = make_recording(events=[make_click_event(10, 20, 1.0)])
        workflow = await processor.process(recording)
        assert workflow.source_recording_id == "rec_test_001"


# ── Save to Disk ─────────────────────────────────────────────────────

class TestSaveToDisk:
    @pytest.mark.asyncio
    async def test_process_and_save(self, processor, tmp_path):
        recording = make_recording(
            events=[make_click_event(100, 200, 1.0)],
            screenshots=SCREENSHOTS,
        )
        output_dir = tmp_path / "workflows"

        workflow = await processor.process_and_save(
            recording, output_dir=output_dir, name="Test Save"
        )

        # Check file exists
        filepath = output_dir / f"{workflow.workflow_id}.json"
        assert filepath.exists()

        # Check contents
        data = json.loads(filepath.read_text())
        assert data["name"] == "Test Save"
        assert len(data["steps"]) == 1
        assert data["source_recording_id"] == "rec_test_001"

    @pytest.mark.asyncio
    async def test_save_creates_directory(self, processor, tmp_path):
        recording = make_recording(events=[make_click_event(10, 20, 1.0)])
        output_dir = tmp_path / "new" / "nested" / "dir"

        await processor.process_and_save(recording, output_dir=output_dir)
        assert output_dir.exists()


# ── Serialization Roundtrip ──────────────────────────────────────────

class TestSerialization:
    @pytest.mark.asyncio
    async def test_workflow_roundtrip(self, processor, screenshot_dir):
        recording = make_recording(
            events=[
                make_click_event(100, 200, 1.0),
                make_type_event("Hello World", 2.0),
            ],
            screenshots=SCREENSHOTS,
        )
        workflow = await processor.process(recording, screenshot_dir)

        # Serialize
        data = workflow.to_dict()
        json_str = json.dumps(data, default=str)

        # Deserialize
        restored = Workflow.from_dict(json.loads(json_str))

        assert restored.workflow_id == workflow.workflow_id
        assert restored.name == workflow.name
        assert len(restored.steps) == len(workflow.steps)
        assert restored.steps[0].action_type == workflow.steps[0].action_type
        assert restored.steps[1].input_data == "Hello World"


# ── Complex Workflows ────────────────────────────────────────────────

class TestComplexWorkflows:
    @pytest.mark.asyncio
    async def test_notepad_hello_world(self, processor, screenshot_dir):
        """Simulate: Open Notepad → Type → Save."""
        recording = make_recording(
            events=[
                make_click_event(50, 500, 1.0),        # Click Notepad icon
                make_type_event("Hello World", 3.0),    # Type text
                RawEvent(                               # Ctrl+S
                    timestamp=5.0,
                    event_type=EventType.KEY_PRESS,
                    data={"key": "ctrl"},
                ),
                RawEvent(
                    timestamp=5.05,
                    event_type=EventType.KEY_PRESS,
                    data={"key": "s"},
                ),
                make_type_event("hello.txt", 7.0),     # Type filename
                make_click_event(400, 350, 9.0),       # Click Save
            ],
            screenshots=SCREENSHOTS,
        )

        workflow = await processor.process(
            recording, screenshot_dir, name="Notepad Hello World"
        )

        assert workflow.name == "Notepad Hello World"
        assert len(workflow.steps) >= 4  # Click, Type, Hotkey, Type, Click
        assert any(s.action_type == ActionType.TYPE for s in workflow.steps)
        assert any(s.action_type == ActionType.CLICK for s in workflow.steps)

    @pytest.mark.asyncio
    async def test_many_events(self, processor):
        """Test with a large number of events."""
        events = [make_click_event(i * 10, i * 20, float(i)) for i in range(50)]
        recording = make_recording(events=events)

        workflow = await processor.process(recording)
        assert len(workflow.steps) == 50


# ── Edge Cases ───────────────────────────────────────────────────────

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_recording_with_no_screenshots_dir(self, processor):
        recording = make_recording(
            events=[make_click_event(100, 200, 1.0)],
            screenshots=SCREENSHOTS,
        )
        # No screenshot_dir provided — should use fallback descriptions
        workflow = await processor.process(recording, screenshot_dir=None)
        assert len(workflow.steps) == 1

    @pytest.mark.asyncio
    async def test_missing_screenshot_file(self, processor, tmp_path):
        """Screenshot referenced but file doesn't exist."""
        recording = make_recording(
            events=[make_click_event(100, 200, 1.0)],
            screenshots=SCREENSHOTS,
        )
        # Dir exists but no files
        workflow = await processor.process(recording, screenshot_dir=tmp_path)
        assert len(workflow.steps) == 1  # Should still work with fallback
