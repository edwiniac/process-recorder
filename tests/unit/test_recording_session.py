"""
Unit tests for RecordingSession module.

Note: Full recording tests require a display (X server on Linux, GUI on Windows/macOS).
Tests are structured to test what's possible without a display.
"""

import time
import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from process_recorder.recorder.recording_session import (
    RecordingSession, SessionConfig, load_recording
)
from process_recorder.recorder.event_listener import is_pynput_available, get_pynput_error
from process_recorder.models import Recording, RawEvent, Screenshot, EventType


# Skip marker for tests requiring display
requires_display = pytest.mark.skipif(
    not is_pynput_available(),
    reason=f"pynput not available: {get_pynput_error()}"
)


class TestSessionConfig:
    """Tests for SessionConfig - works without display."""
    
    def test_default_values(self):
        """Test default configuration."""
        config = SessionConfig()
        
        assert config.name == "Untitled Recording"
        assert config.screenshot_interval_ms == 500
        assert config.capture_on_click == True
        assert config.max_screenshots == 1000
    
    def test_custom_values(self):
        """Test custom configuration."""
        config = SessionConfig(
            name="My Recording",
            screenshot_interval_ms=250,
            capture_on_click=False
        )
        
        assert config.name == "My Recording"
        assert config.screenshot_interval_ms == 250
        assert config.capture_on_click == False


class TestRecordingSessionBasic:
    """Basic tests for RecordingSession that don't require display."""
    
    def test_create_session(self, temp_dir):
        """Test creating a recording session."""
        config = SessionConfig(
            name="Test Recording",
            output_dir=temp_dir
        )
        session = RecordingSession(config)
        
        assert session.recording_id.startswith("rec_")
        assert session.config.name == "Test Recording"
        assert not session.is_recording
    
    def test_session_has_unique_id(self, temp_dir):
        """Test that each session has a unique ID."""
        config = SessionConfig(output_dir=temp_dir)
        
        session1 = RecordingSession(config)
        session2 = RecordingSession(config)
        
        assert session1.recording_id != session2.recording_id
    
    def test_duration_before_start(self, temp_dir):
        """Test duration is 0 before starting."""
        config = SessionConfig(output_dir=temp_dir)
        session = RecordingSession(config)
        
        assert session.duration_ms == 0
    
    def test_event_count_before_start(self, temp_dir):
        """Test event count is 0 before starting."""
        config = SessionConfig(output_dir=temp_dir)
        session = RecordingSession(config)
        
        assert session.event_count == 0
        assert session.screenshot_count == 0


class TestLoadRecording:
    """Tests for load_recording function - works without display."""
    
    def test_load_recording_from_files(self, temp_dir):
        """Test loading a recording from disk files."""
        # Create a fake recording directory
        session_dir = temp_dir / "rec_test123"
        screenshots_dir = session_dir / "screenshots"
        session_dir.mkdir()
        screenshots_dir.mkdir()
        
        # Create metadata
        metadata = {
            "recording_id": "rec_test123",
            "name": "Test Recording",
            "created_at": "2026-01-29T14:00:00",
            "duration_ms": 5000,
            "event_count": 2,
            "screenshot_count": 3
        }
        with open(session_dir / "metadata.json", "w") as f:
            json.dump(metadata, f)
        
        # Create events
        events = [
            {"timestamp": 1.0, "event_type": "click", "data": {"x": 100, "y": 200}},
            {"timestamp": 2.0, "event_type": "key_type", "data": {"text": "hello"}}
        ]
        with open(session_dir / "events.json", "w") as f:
            json.dump(events, f)
        
        # Create screenshots index
        screenshots = [
            {"screenshot_id": "0001", "timestamp": 1.0, "filepath": str(screenshots_dir / "0001.png"), "width": 1920, "height": 1080},
            {"screenshot_id": "0002", "timestamp": 2.0, "filepath": str(screenshots_dir / "0002.png"), "width": 1920, "height": 1080}
        ]
        with open(session_dir / "screenshots.json", "w") as f:
            json.dump(screenshots, f)
        
        # Load the recording
        recording = load_recording(session_dir)
        
        assert recording.recording_id == "rec_test123"
        assert recording.name == "Test Recording"
        assert recording.duration_ms == 5000
        assert len(recording.events) == 2
        assert len(recording.screenshots) == 2
    
    def test_load_recording_events_deserialized(self, temp_dir):
        """Test that loaded events are properly deserialized."""
        session_dir = temp_dir / "rec_events"
        session_dir.mkdir()
        
        metadata = {
            "recording_id": "rec_events",
            "name": "Event Test",
            "created_at": "2026-01-29T14:00:00",
            "duration_ms": 1000
        }
        with open(session_dir / "metadata.json", "w") as f:
            json.dump(metadata, f)
        
        events = [
            {"timestamp": 1.5, "event_type": "click", "data": {"x": 50, "y": 75, "button": "left"}}
        ]
        with open(session_dir / "events.json", "w") as f:
            json.dump(events, f)
        
        with open(session_dir / "screenshots.json", "w") as f:
            json.dump([], f)
        
        recording = load_recording(session_dir)
        
        assert len(recording.events) == 1
        assert recording.events[0].event_type == EventType.CLICK
        assert recording.events[0].data["x"] == 50
    
    def test_load_recording_missing_events_file(self, temp_dir):
        """Test loading when events.json doesn't exist."""
        session_dir = temp_dir / "rec_noevents"
        session_dir.mkdir()
        
        metadata = {
            "recording_id": "rec_noevents",
            "name": "No Events",
            "created_at": "2026-01-29T14:00:00",
            "duration_ms": 0
        }
        with open(session_dir / "metadata.json", "w") as f:
            json.dump(metadata, f)
        
        # Don't create events.json or screenshots.json
        recording = load_recording(session_dir)
        
        assert recording.recording_id == "rec_noevents"
        assert len(recording.events) == 0
        assert len(recording.screenshots) == 0


@requires_display
class TestRecordingSessionWithDisplay:
    """Tests that require a real display - skipped in headless env."""
    
    def test_start_creates_directories(self, temp_dir):
        """Test that starting creates necessary directories."""
        config = SessionConfig(output_dir=temp_dir)
        session = RecordingSession(config)
        
        session.start()
        
        try:
            assert session.session_dir.exists()
            assert session.screenshots_dir.exists()
            assert (session.session_dir / "metadata.json").exists()
        finally:
            session.stop()
    
    def test_start_sets_recording_flag(self, temp_dir):
        """Test that starting sets is_recording flag."""
        config = SessionConfig(output_dir=temp_dir)
        session = RecordingSession(config)
        
        assert not session.is_recording
        
        session.start()
        assert session.is_recording
        
        session.stop()
        assert not session.is_recording
    
    def test_stop_returns_recording(self, temp_dir):
        """Test that stop returns a Recording object."""
        config = SessionConfig(
            name="Test Recording",
            output_dir=temp_dir
        )
        session = RecordingSession(config)
        
        session.start()
        time.sleep(0.1)
        recording = session.stop()
        
        assert isinstance(recording, Recording)
        assert recording.name == "Test Recording"
        assert recording.recording_id == session.recording_id
    
    def test_context_manager(self, temp_dir):
        """Test using session as context manager."""
        config = SessionConfig(output_dir=temp_dir)
        
        with RecordingSession(config) as session:
            assert session.is_recording
            time.sleep(0.1)
        
        assert not session.is_recording


class TestRecordingSessionMocked:
    """Tests using mocks to avoid display requirement."""
    
    def test_build_recording(self, temp_dir):
        """Test building a Recording from session state."""
        config = SessionConfig(
            name="Built Recording",
            output_dir=temp_dir
        )
        session = RecordingSession(config)
        
        # Manually set internal state
        session._start_time = time.time() - 1.0  # 1 second ago
        session._events = [
            RawEvent(timestamp=1.0, event_type=EventType.CLICK, data={"x": 0})
        ]
        session._screenshots = [
            Screenshot(screenshot_id="0001", timestamp=1.0, filepath="/test.png", width=100, height=100)
        ]
        
        recording = session._build_recording()
        
        assert recording.name == "Built Recording"
        assert len(recording.events) == 1
        assert len(recording.screenshots) == 1
        assert recording.duration_ms >= 900  # ~1 second
    
    def test_session_event_callbacks(self, temp_dir):
        """Test session event callbacks without starting."""
        config = SessionConfig(output_dir=temp_dir)
        session = RecordingSession(config)
        
        events_received = []
        
        def callback(event_type, data):
            events_received.append((event_type, data))
        
        session.on_session_event(callback)
        
        # Manually emit events
        session._emit("test_event", {"foo": "bar"})
        session._emit("another_event", {"baz": 123})
        
        assert len(events_received) == 2
        assert events_received[0][0] == "test_event"
        assert events_received[1][0] == "another_event"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
