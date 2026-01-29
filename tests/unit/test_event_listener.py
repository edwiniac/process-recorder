"""
Unit tests for EventListener module.

Note: Some tests require a display (X server on Linux, GUI on Windows/macOS).
Tests are skipped in headless environments.
"""

import time
import pytest
from unittest.mock import Mock, patch, MagicMock

from process_recorder.models import RawEvent, EventType

# Import the module parts that don't require pynput
from process_recorder.recorder.event_listener import (
    EventConfig, EventBuffer, EventListener,
    is_pynput_available, get_pynput_error
)


# Skip marker for tests requiring display
requires_display = pytest.mark.skipif(
    not is_pynput_available(),
    reason=f"pynput not available: {get_pynput_error()}"
)


class TestEventBuffer:
    """Tests for EventBuffer - works without display."""
    
    def test_add_and_get_events(self):
        """Test adding and retrieving events."""
        buffer = EventBuffer(max_size=100)
        
        event1 = RawEvent(timestamp=1.0, event_type=EventType.CLICK, data={"x": 0})
        event2 = RawEvent(timestamp=2.0, event_type=EventType.CLICK, data={"x": 1})
        
        buffer.add(event1)
        buffer.add(event2)
        
        assert len(buffer) == 2
        
        events = buffer.get_all()
        
        assert len(events) == 2
        assert len(buffer) == 0  # Buffer cleared
    
    def test_peek_does_not_clear(self):
        """Test that peek doesn't clear the buffer."""
        buffer = EventBuffer()
        
        event = RawEvent(timestamp=1.0, event_type=EventType.CLICK, data={})
        buffer.add(event)
        
        events1 = buffer.peek_all()
        events2 = buffer.peek_all()
        
        assert len(events1) == 1
        assert len(events2) == 1
        assert len(buffer) == 1
    
    def test_max_size_enforced(self):
        """Test that max size is enforced."""
        buffer = EventBuffer(max_size=3)
        
        for i in range(5):
            buffer.add(RawEvent(timestamp=float(i), event_type=EventType.CLICK, data={}))
        
        assert len(buffer) == 3
        
        events = buffer.get_all()
        # Should have the last 3 events
        assert events[0].timestamp == 2.0
        assert events[1].timestamp == 3.0
        assert events[2].timestamp == 4.0


class TestEventConfig:
    """Tests for EventConfig - works without display."""
    
    def test_default_values(self):
        """Test default configuration."""
        config = EventConfig()
        
        assert config.capture_mouse_clicks == True
        assert config.capture_mouse_movement == False
        assert config.capture_keyboard == True
        assert config.capture_scroll == True
        assert config.buffer_size == 10000
    
    def test_custom_values(self):
        """Test custom configuration."""
        config = EventConfig(
            capture_mouse_clicks=False,
            capture_keyboard=False,
            buffer_size=500
        )
        
        assert config.capture_mouse_clicks == False
        assert config.capture_keyboard == False
        assert config.buffer_size == 500


class TestEventListenerBasic:
    """Basic tests for EventListener that don't require display."""
    
    def test_create_listener_default_config(self):
        """Test creating listener with default config."""
        listener = EventListener()
        
        assert listener.config.capture_mouse_clicks == True
        assert not listener.is_running
        assert listener.event_count == 0
    
    def test_create_listener_custom_config(self):
        """Test creating listener with custom config."""
        config = EventConfig(capture_keyboard=False)
        listener = EventListener(config)
        
        assert listener.config.capture_keyboard == False
    
    def test_callback_registration(self):
        """Test registering event callbacks."""
        listener = EventListener()
        
        events_received = []
        
        def callback(event):
            events_received.append(event)
        
        listener.on_event(callback)
        
        # Manually trigger event emission (doesn't require display)
        test_event = RawEvent(timestamp=1.0, event_type=EventType.CLICK, data={"x": 100})
        listener._emit_event(test_event)
        
        assert len(events_received) == 1
        assert events_received[0].event_type == EventType.CLICK
    
    def test_get_events_clears_buffer(self):
        """Test that get_events clears the buffer."""
        listener = EventListener()
        
        # Add events directly to buffer
        listener._buffer.add(RawEvent(timestamp=1.0, event_type=EventType.CLICK, data={}))
        listener._buffer.add(RawEvent(timestamp=2.0, event_type=EventType.CLICK, data={}))
        
        events = listener.get_events()
        assert len(events) == 2
        
        events2 = listener.get_events()
        assert len(events2) == 0
    
    def test_peek_events_does_not_clear(self):
        """Test that peek_events doesn't clear."""
        listener = EventListener()
        
        listener._buffer.add(RawEvent(timestamp=1.0, event_type=EventType.CLICK, data={}))
        
        events1 = listener.peek_events()
        events2 = listener.peek_events()
        
        assert len(events1) == 1
        assert len(events2) == 1
    
    def test_start_without_display_raises(self):
        """Test that starting without display raises appropriate error."""
        if is_pynput_available():
            pytest.skip("Display is available, cannot test error condition")
        
        listener = EventListener()
        
        with pytest.raises(RuntimeError, match="pynput is not available"):
            listener.start()


class TestEventListenerKeyHandling:
    """Tests for keyboard event handling - uses mocking."""
    
    def test_key_to_string_char(self):
        """Test converting character keys to string."""
        listener = EventListener()
        
        # Mock a key with char attribute
        mock_key = Mock()
        mock_key.char = 'a'
        
        result = listener._key_to_string(mock_key)
        assert result == 'a'
    
    def test_key_to_string_special(self):
        """Test converting special keys to string."""
        listener = EventListener()
        
        # Mock a key with name attribute (like Enter, Tab)
        mock_key = Mock(spec=['name'])
        mock_key.char = None
        mock_key.name = 'enter'
        
        result = listener._key_to_string(mock_key)
        assert result == 'enter'
    
    def test_is_printable_true(self):
        """Test detecting printable characters."""
        listener = EventListener()
        
        mock_key = Mock()
        mock_key.char = 'x'
        
        assert listener._is_printable(mock_key) == True
    
    def test_is_printable_false_for_special(self):
        """Test that special keys are not printable."""
        listener = EventListener()
        
        mock_key = Mock(spec=['name'])
        mock_key.char = None
        
        assert listener._is_printable(mock_key) == False


class TestEventListenerMouseHandling:
    """Tests for mouse event handling - simulates without display."""
    
    def test_mouse_click_handler(self):
        """Test mouse click handler creates correct event."""
        listener = EventListener()
        
        # Create mock mouse button
        mock_button = Mock()
        mock_button.name = 'left'
        
        # Patch the mouse module
        with patch.object(listener, '_emit_event') as mock_emit:
            # Simulate what pynput would call
            # We need to mock mouse.Button for comparison
            with patch('process_recorder.recorder.event_listener.mouse') as mock_mouse:
                mock_mouse.Button.left = mock_button
                mock_mouse.Button.right = Mock(name='right')
                mock_mouse.Button.middle = Mock(name='middle')
                
                listener._on_mouse_click(100, 200, mock_button, True)
                
                mock_emit.assert_called_once()
                event = mock_emit.call_args[0][0]
                assert event.event_type == EventType.CLICK
                assert event.data["x"] == 100
                assert event.data["y"] == 200
    
    def test_mouse_release_ignored(self):
        """Test that mouse release is ignored."""
        listener = EventListener()
        
        mock_button = Mock()
        
        with patch.object(listener, '_emit_event') as mock_emit:
            listener._on_mouse_click(100, 200, mock_button, False)  # pressed=False
            
            mock_emit.assert_not_called()
    
    def test_scroll_handler(self):
        """Test scroll handler creates correct event."""
        listener = EventListener()
        
        with patch.object(listener, '_emit_event') as mock_emit:
            listener._on_mouse_scroll(100, 200, 0, -3)
            
            mock_emit.assert_called_once()
            event = mock_emit.call_args[0][0]
            assert event.event_type == EventType.SCROLL
            assert event.data["dy"] == -3


@requires_display
class TestEventListenerWithDisplay:
    """Tests that require a real display - skipped in headless env."""
    
    def test_start_stop(self):
        """Test starting and stopping the listener."""
        listener = EventListener()
        
        listener.start()
        assert listener.is_running
        
        listener.stop()
        assert not listener.is_running
    
    def test_context_manager(self):
        """Test using listener as context manager."""
        with EventListener() as listener:
            assert listener.is_running
        
        assert not listener.is_running


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
