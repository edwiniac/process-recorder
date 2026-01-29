"""
Unit tests for data models.
"""

import pytest
from datetime import datetime

from process_recorder.models import (
    RawEvent, EventType, Screenshot, Recording,
    SemanticStep, ActionType, BoundingBox, Workflow,
    AppConfig
)


class TestRawEvent:
    """Tests for RawEvent model."""
    
    def test_create_click_event(self):
        """Test creating a mouse click event."""
        event = RawEvent(
            timestamp=1234567890.123,
            event_type=EventType.CLICK,
            data={"x": 100, "y": 200, "button": "left"},
            screenshot_id="0001"
        )
        
        assert event.timestamp == 1234567890.123
        assert event.event_type == EventType.CLICK
        assert event.data["x"] == 100
        assert event.screenshot_id == "0001"
    
    def test_event_to_dict(self):
        """Test serializing event to dict."""
        event = RawEvent(
            timestamp=1234567890.0,
            event_type=EventType.KEY_PRESS,
            data={"key": "a"},
        )
        
        d = event.to_dict()
        
        assert d["timestamp"] == 1234567890.0
        assert d["event_type"] == "key_press"
        assert d["data"]["key"] == "a"
        assert d["screenshot_id"] is None
    
    def test_event_from_dict(self):
        """Test deserializing event from dict."""
        d = {
            "timestamp": 1234567890.0,
            "event_type": "click",
            "data": {"x": 50, "y": 75},
            "screenshot_id": "0002"
        }
        
        event = RawEvent.from_dict(d)
        
        assert event.timestamp == 1234567890.0
        assert event.event_type == EventType.CLICK
        assert event.data["x"] == 50
        assert event.screenshot_id == "0002"


class TestScreenshot:
    """Tests for Screenshot model."""
    
    def test_create_screenshot(self):
        """Test creating a screenshot record."""
        ss = Screenshot(
            screenshot_id="0001",
            timestamp=1234567890.0,
            filepath="/recordings/test/screenshots/0001.png",
            width=1920,
            height=1080
        )
        
        assert ss.screenshot_id == "0001"
        assert ss.width == 1920
    
    def test_screenshot_roundtrip(self):
        """Test serialization roundtrip."""
        original = Screenshot(
            screenshot_id="0002",
            timestamp=1234567890.5,
            filepath="/path/to/file.png",
            width=1280,
            height=720
        )
        
        d = original.to_dict()
        restored = Screenshot.from_dict(d)
        
        assert restored.screenshot_id == original.screenshot_id
        assert restored.timestamp == original.timestamp
        assert restored.filepath == original.filepath


class TestRecording:
    """Tests for Recording model."""
    
    def test_create_empty_recording(self):
        """Test creating an empty recording."""
        rec = Recording(
            recording_id="rec_001",
            name="Test Recording",
            created_at=datetime.now(),
        )
        
        assert rec.recording_id == "rec_001"
        assert len(rec.events) == 0
        assert len(rec.screenshots) == 0
    
    def test_recording_with_events(self):
        """Test recording with events."""
        event1 = RawEvent(
            timestamp=1.0,
            event_type=EventType.CLICK,
            data={"x": 100, "y": 100}
        )
        event2 = RawEvent(
            timestamp=2.0,
            event_type=EventType.KEY_TYPE,
            data={"text": "hello"}
        )
        
        rec = Recording(
            recording_id="rec_002",
            name="Test with Events",
            created_at=datetime.now(),
            events=[event1, event2],
            duration_ms=1000
        )
        
        assert len(rec.events) == 2
        assert rec.events[0].event_type == EventType.CLICK
        assert rec.duration_ms == 1000


class TestBoundingBox:
    """Tests for BoundingBox model."""
    
    def test_bounding_box_center(self):
        """Test calculating center point."""
        box = BoundingBox(x=100, y=200, width=50, height=30)
        
        center = box.center
        
        assert center == (125, 215)
    
    def test_bounding_box_roundtrip(self):
        """Test serialization roundtrip."""
        original = BoundingBox(x=10, y=20, width=100, height=50)
        
        d = original.to_dict()
        restored = BoundingBox.from_dict(d)
        
        assert restored.x == original.x
        assert restored.center == original.center


class TestSemanticStep:
    """Tests for SemanticStep model."""
    
    def test_create_click_step(self):
        """Test creating a click step."""
        step = SemanticStep(
            step_id=1,
            action_type=ActionType.CLICK,
            target_description="the 'Submit' button",
            target_screenshot_id="0005",
            target_region=BoundingBox(x=200, y=300, width=80, height=30),
            confidence=0.95
        )
        
        assert step.step_id == 1
        assert step.action_type == ActionType.CLICK
        assert step.target_description == "the 'Submit' button"
        assert step.confidence == 0.95
    
    def test_create_type_step(self):
        """Test creating a type step."""
        step = SemanticStep(
            step_id=2,
            action_type=ActionType.TYPE,
            target_description="the search input field",
            target_screenshot_id="0006",
            input_data="hello world",
            confidence=0.88
        )
        
        assert step.action_type == ActionType.TYPE
        assert step.input_data == "hello world"


class TestWorkflow:
    """Tests for Workflow model."""
    
    def test_create_workflow(self):
        """Test creating a workflow."""
        steps = [
            SemanticStep(
                step_id=1,
                action_type=ActionType.CLICK,
                target_description="Start menu",
                target_screenshot_id="0001",
                confidence=0.9
            ),
            SemanticStep(
                step_id=2,
                action_type=ActionType.TYPE,
                target_description="Search box",
                target_screenshot_id="0002",
                input_data="notepad",
                confidence=0.85
            ),
        ]
        
        workflow = Workflow(
            workflow_id="wf_001",
            name="Open Notepad",
            description="Opens Notepad via Start menu",
            created_at=datetime.now(),
            steps=steps,
            source_recording_id="rec_001",
            model_used="ollama:llava:13b"
        )
        
        assert workflow.name == "Open Notepad"
        assert len(workflow.steps) == 2
        assert workflow.steps[1].input_data == "notepad"


class TestAppConfig:
    """Tests for AppConfig model."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = AppConfig()
        
        assert config.vision.provider == "ollama"
        assert config.recording.screenshot_interval_ms == 500
        assert config.replay.confidence_threshold == 0.7
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = AppConfig(
            vision=AppConfig.VisionConfig(
                provider="claude",
                claude_api_key="test-key"
            ),
            recording=AppConfig.RecordingConfig(
                screenshot_interval_ms=250
            )
        )
        
        assert config.vision.provider == "claude"
        assert config.vision.claude_api_key == "test-key"
        assert config.recording.screenshot_interval_ms == 250


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
