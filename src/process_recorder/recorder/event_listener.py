"""
Event listener module for ProcessRecorder.

Captures mouse clicks, keyboard input, and other user events.
"""

import time
import threading
from typing import Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from collections import deque

from ..models import RawEvent, EventType, MouseButton

# Lazy import pynput to avoid errors in headless environments
# pynput requires X display on Linux
_pynput_available = False
_pynput_error = None

try:
    from pynput import mouse, keyboard
    _pynput_available = True
except ImportError as e:
    _pynput_error = str(e)
    mouse = None  # type: ignore
    keyboard = None  # type: ignore


def is_pynput_available() -> bool:
    """Check if pynput is available (requires display)."""
    return _pynput_available


def get_pynput_error() -> Optional[str]:
    """Get the pynput import error message if unavailable."""
    return _pynput_error


@dataclass
class EventConfig:
    """Configuration for event listening."""
    capture_mouse_clicks: bool = True
    capture_mouse_movement: bool = False  # Usually too noisy
    capture_keyboard: bool = True
    capture_scroll: bool = True
    buffer_size: int = 10000  # Max events in buffer
    key_combo_timeout_ms: int = 50  # Time to wait for modifier+key combos


class EventBuffer:
    """Thread-safe buffer for captured events."""
    
    def __init__(self, max_size: int = 10000):
        self._buffer: deque[RawEvent] = deque(maxlen=max_size)
        self._lock = threading.Lock()
    
    def add(self, event: RawEvent) -> None:
        """Add an event to the buffer."""
        with self._lock:
            self._buffer.append(event)
    
    def get_all(self) -> list[RawEvent]:
        """Get all events and clear the buffer."""
        with self._lock:
            events = list(self._buffer)
            self._buffer.clear()
            return events
    
    def peek_all(self) -> list[RawEvent]:
        """Get all events without clearing."""
        with self._lock:
            return list(self._buffer)
    
    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)


class EventListener:
    """
    Listens for mouse and keyboard events.
    
    Thread-safe and can run alongside screen capture.
    """
    
    def __init__(self, config: Optional[EventConfig] = None):
        self.config = config or EventConfig()
        self._buffer = EventBuffer(self.config.buffer_size)
        self._mouse_listener = None  # mouse.Listener when available
        self._keyboard_listener = None  # keyboard.Listener when available
        self._running = False
        self._callbacks: list[Callable[[RawEvent], None]] = []
        self._typed_text = ""  # Buffer for accumulating typed text
        self._last_key_time: float = 0
        self._pressed_modifiers: set[str] = set()
    
    def start(self) -> None:
        """Start listening for events."""
        if self._running:
            return
        
        if not _pynput_available:
            raise RuntimeError(
                f"pynput is not available in this environment: {_pynput_error}\n"
                "This typically means no display server is available."
            )
        
        self._running = True
        
        # Start mouse listener
        if self.config.capture_mouse_clicks or self.config.capture_scroll:
            self._mouse_listener = mouse.Listener(
                on_click=self._on_mouse_click if self.config.capture_mouse_clicks else None,
                on_scroll=self._on_mouse_scroll if self.config.capture_scroll else None,
            )
            self._mouse_listener.start()
        
        # Start keyboard listener
        if self.config.capture_keyboard:
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )
            self._keyboard_listener.start()
    
    def stop(self) -> None:
        """Stop listening for events."""
        self._running = False
        
        # Flush any remaining typed text
        self._flush_typed_text()
        
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None
        
        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
    
    def _on_mouse_click(self, x: int, y: int, button, pressed: bool) -> None:
        """Handle mouse click events."""
        if not pressed:  # Only capture press, not release
            return
        
        # Determine button type by name (works with mock objects too)
        button_name = getattr(button, 'name', str(button))
        
        # Map button name to our enum
        button_type = MouseButton.LEFT  # default
        if 'right' in button_name.lower():
            button_type = MouseButton.RIGHT
        elif 'middle' in button_name.lower():
            button_type = MouseButton.MIDDLE
        
        # Determine event type
        event_type = EventType.CLICK
        if button_type == MouseButton.RIGHT:
            event_type = EventType.RIGHT_CLICK
        
        event = RawEvent(
            timestamp=time.time(),
            event_type=event_type,
            data={
                "x": x,
                "y": y,
                "button": button_type.value,
            }
        )
        
        self._emit_event(event)
    
    def _on_mouse_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        """Handle mouse scroll events."""
        event = RawEvent(
            timestamp=time.time(),
            event_type=EventType.SCROLL,
            data={
                "x": x,
                "y": y,
                "dx": dx,
                "dy": dy,
            }
        )
        
        self._emit_event(event)
    
    def _on_key_press(self, key) -> None:
        """Handle key press events."""
        timestamp = time.time()
        
        # Track modifiers
        if self._is_modifier(key):
            self._pressed_modifiers.add(self._key_to_string(key))
            return
        
        # Get key string
        key_str = self._key_to_string(key)
        
        # Check if this is a printable character
        if self._is_printable(key):
            # Accumulate typed text
            if timestamp - self._last_key_time > (self.config.key_combo_timeout_ms / 1000.0):
                self._flush_typed_text()
            
            self._typed_text += key_str
            self._last_key_time = timestamp
        else:
            # Non-printable key (Enter, Tab, etc.)
            self._flush_typed_text()
            
            event = RawEvent(
                timestamp=timestamp,
                event_type=EventType.KEY_PRESS,
                data={
                    "key": key_str,
                    "modifiers": list(self._pressed_modifiers),
                }
            )
            self._emit_event(event)
    
    def _on_key_release(self, key) -> None:
        """Handle key release events."""
        if self._is_modifier(key):
            self._pressed_modifiers.discard(self._key_to_string(key))
    
    def _flush_typed_text(self) -> None:
        """Flush accumulated typed text as a single event."""
        if self._typed_text:
            event = RawEvent(
                timestamp=self._last_key_time,
                event_type=EventType.KEY_TYPE,
                data={
                    "text": self._typed_text,
                }
            )
            self._emit_event(event)
            self._typed_text = ""
    
    def _emit_event(self, event: RawEvent) -> None:
        """Add event to buffer and notify callbacks."""
        self._buffer.add(event)
        
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception:
                pass  # Don't let callback errors break listener
    
    def _key_to_string(self, key) -> str:
        """Convert pynput key to string representation."""
        if hasattr(key, 'char') and key.char is not None:
            return key.char
        elif hasattr(key, 'name'):
            return key.name
        else:
            return str(key)
    
    def _is_printable(self, key) -> bool:
        """Check if key produces a printable character."""
        if hasattr(key, 'char') and key.char is not None:
            return len(key.char) == 1 and key.char.isprintable()
        return False
    
    def _is_modifier(self, key) -> bool:
        """Check if key is a modifier (Ctrl, Alt, Shift, etc.)."""
        # Check by key name to avoid direct keyboard.Key references
        modifier_names = {
            'ctrl', 'ctrl_l', 'ctrl_r',
            'alt', 'alt_l', 'alt_r', 'alt_gr',
            'shift', 'shift_l', 'shift_r',
            'cmd', 'cmd_l', 'cmd_r',
        }
        
        # Get key name
        key_name = getattr(key, 'name', None)
        if key_name:
            return key_name.lower() in modifier_names
        
        # Fallback: check against keyboard.Key if available
        if _pynput_available and keyboard:
            modifier_keys = {
                keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
                keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr,
                keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r,
                keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r,
            }
            return key in modifier_keys
        
        return False
    
    def get_events(self) -> list[RawEvent]:
        """Get all captured events and clear the buffer."""
        self._flush_typed_text()
        return self._buffer.get_all()
    
    def peek_events(self) -> list[RawEvent]:
        """Get all captured events without clearing."""
        return self._buffer.peek_all()
    
    def on_event(self, callback: Callable[[RawEvent], None]) -> None:
        """
        Register a callback for when events are captured.
        
        Args:
            callback: Function(event) called on each event
        """
        self._callbacks.append(callback)
    
    @property
    def event_count(self) -> int:
        """Number of events in the buffer."""
        return len(self._buffer)
    
    @property
    def is_running(self) -> bool:
        """Whether the listener is running."""
        return self._running
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
