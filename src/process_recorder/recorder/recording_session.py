"""
Recording session module for ProcessRecorder.

Orchestrates screen capture and event listening into a cohesive recording.
"""

import time
import uuid
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable
from dataclasses import dataclass

from ..models import Recording, RawEvent, Screenshot, EventType
from .screen_capturer import ScreenCapturer, CaptureConfig
from .event_listener import EventListener, EventConfig


@dataclass
class SessionConfig:
    """Configuration for a recording session."""
    name: str = "Untitled Recording"
    output_dir: Path = Path("./recordings")
    screenshot_interval_ms: int = 500
    capture_on_click: bool = True
    max_screenshots: int = 1000
    auto_save_interval_ms: int = 5000  # Save progress every N ms


class RecordingSession:
    """
    Manages a complete recording session.
    
    Coordinates screen capture and event listening, saves data incrementally.
    """
    
    def __init__(self, config: Optional[SessionConfig] = None):
        self.config = config or SessionConfig()
        
        # Generate unique ID
        self.recording_id = f"rec_{uuid.uuid4().hex[:8]}"
        
        # Setup paths
        self.session_dir = self.config.output_dir / self.recording_id
        self.screenshots_dir = self.session_dir / "screenshots"
        
        # Initialize components
        self._capturer = ScreenCapturer(CaptureConfig(
            interval_ms=self.config.screenshot_interval_ms,
            max_screenshots=self.config.max_screenshots,
            output_dir=self.screenshots_dir,
        ))
        
        self._listener = EventListener(EventConfig(
            capture_mouse_clicks=True,
            capture_keyboard=True,
            capture_scroll=True,
        ))
        
        # State
        self._recording = False
        self._paused = False
        self._start_time: Optional[float] = None
        self._events: list[RawEvent] = []
        self._screenshots: list[Screenshot] = []
        self._lock = threading.Lock()
        self._auto_save_thread: Optional[threading.Thread] = None
        self._callbacks: list[Callable[[str, any], None]] = []  # (event_type, data)
        
        # Link events to screenshots
        self._pending_screenshot: Optional[str] = None
    
    def start(self) -> None:
        """Start recording."""
        if self._recording:
            return
        
        # Create directories
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Save initial metadata
        self._save_metadata()
        
        # Setup event callback to capture on click
        if self.config.capture_on_click:
            self._listener.on_event(self._on_event)
        
        # Setup screenshot callback
        self._capturer.on_capture(self._on_screenshot)
        
        # Start components
        self._capturer.start()
        self._listener.start()
        
        # Start continuous capture
        self._capturer.start_continuous()
        
        # Start auto-save
        self._start_auto_save()
        
        self._recording = True
        self._start_time = time.time()
        
        self._emit("started", {"recording_id": self.recording_id})
    
    def stop(self) -> Recording:
        """
        Stop recording and return the completed Recording.
        
        Returns:
            Recording object with all captured data
        """
        if not self._recording:
            return self._build_recording()
        
        self._recording = False
        
        # Stop auto-save
        self._stop_auto_save()
        
        # Stop components
        self._capturer.stop()
        self._listener.stop()
        
        # Get final events
        with self._lock:
            final_events = self._listener.get_events()
            self._events.extend(final_events)
        
        # Build and save final recording
        recording = self._build_recording()
        self._save_recording(recording)
        
        self._emit("stopped", {"recording_id": self.recording_id, "duration_ms": recording.duration_ms})
        
        return recording
    
    def pause(self) -> None:
        """Pause recording (stops capture but keeps session open)."""
        if not self._recording or self._paused:
            return
        
        self._paused = True
        self._capturer.stop_continuous()
        self._emit("paused", {})
    
    def resume(self) -> None:
        """Resume a paused recording."""
        if not self._recording or not self._paused:
            return
        
        self._paused = False
        self._capturer.start_continuous()
        self._emit("resumed", {})
    
    def _on_event(self, event: RawEvent) -> None:
        """Handle captured events."""
        with self._lock:
            # Associate with latest screenshot
            if self._screenshots:
                event.screenshot_id = self._screenshots[-1].screenshot_id
            
            self._events.append(event)
        
        # Capture screenshot on click
        if self.config.capture_on_click and event.event_type in (
            EventType.CLICK, EventType.RIGHT_CLICK, EventType.DOUBLE_CLICK
        ):
            try:
                self._capturer.capture_and_save()
            except RuntimeError:
                pass  # Max screenshots reached
        
        self._emit("event", event.to_dict())
    
    def _on_screenshot(self, screenshot: Screenshot, img_bytes: bytes) -> None:
        """Handle captured screenshots."""
        with self._lock:
            self._screenshots.append(screenshot)
        
        self._emit("screenshot", {"id": screenshot.screenshot_id, "timestamp": screenshot.timestamp})
    
    def _build_recording(self) -> Recording:
        """Build a Recording object from current state."""
        with self._lock:
            duration_ms = 0
            if self._start_time:
                duration_ms = int((time.time() - self._start_time) * 1000)
            
            return Recording(
                recording_id=self.recording_id,
                name=self.config.name,
                created_at=datetime.now(),
                events=list(self._events),
                screenshots=list(self._screenshots),
                duration_ms=duration_ms,
            )
    
    def _save_metadata(self) -> None:
        """Save session metadata."""
        metadata = {
            "recording_id": self.recording_id,
            "name": self.config.name,
            "created_at": datetime.now().isoformat(),
            "config": {
                "screenshot_interval_ms": self.config.screenshot_interval_ms,
                "capture_on_click": self.config.capture_on_click,
            }
        }
        
        with open(self.session_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
    
    def _save_recording(self, recording: Recording) -> None:
        """Save the complete recording."""
        # Save events
        with open(self.session_dir / "events.json", "w") as f:
            json.dump([e.to_dict() for e in recording.events], f, indent=2)
        
        # Save screenshot index
        with open(self.session_dir / "screenshots.json", "w") as f:
            json.dump([s.to_dict() for s in recording.screenshots], f, indent=2)
        
        # Update metadata with final info
        metadata = {
            "recording_id": recording.recording_id,
            "name": recording.name,
            "created_at": recording.created_at.isoformat(),
            "duration_ms": recording.duration_ms,
            "event_count": len(recording.events),
            "screenshot_count": len(recording.screenshots),
        }
        
        with open(self.session_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
    
    def _start_auto_save(self) -> None:
        """Start auto-save thread."""
        def auto_save_loop():
            while self._recording:
                time.sleep(self.config.auto_save_interval_ms / 1000.0)
                if self._recording:
                    recording = self._build_recording()
                    self._save_recording(recording)
        
        self._auto_save_thread = threading.Thread(target=auto_save_loop, daemon=True)
        self._auto_save_thread.start()
    
    def _stop_auto_save(self) -> None:
        """Stop auto-save thread."""
        if self._auto_save_thread:
            self._auto_save_thread.join(timeout=2.0)
            self._auto_save_thread = None
    
    def _emit(self, event_type: str, data: any) -> None:
        """Emit an event to callbacks."""
        for callback in self._callbacks:
            try:
                callback(event_type, data)
            except Exception:
                pass
    
    def on_session_event(self, callback: Callable[[str, any], None]) -> None:
        """
        Register a callback for session events.
        
        Events: started, stopped, paused, resumed, event, screenshot
        """
        self._callbacks.append(callback)
    
    @property
    def is_recording(self) -> bool:
        """Whether recording is in progress."""
        return self._recording
    
    @property
    def is_paused(self) -> bool:
        """Whether recording is paused."""
        return self._paused
    
    @property
    def duration_ms(self) -> int:
        """Current recording duration in milliseconds."""
        if self._start_time is None:
            return 0
        return int((time.time() - self._start_time) * 1000)
    
    @property
    def event_count(self) -> int:
        """Number of events captured."""
        with self._lock:
            return len(self._events)
    
    @property
    def screenshot_count(self) -> int:
        """Number of screenshots captured."""
        with self._lock:
            return len(self._screenshots)
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


def load_recording(session_dir: Path) -> Recording:
    """
    Load a recording from disk.
    
    Args:
        session_dir: Path to the recording directory
    
    Returns:
        Recording object
    """
    # Load metadata
    with open(session_dir / "metadata.json") as f:
        metadata = json.load(f)
    
    # Load events
    events_path = session_dir / "events.json"
    events = []
    if events_path.exists():
        with open(events_path) as f:
            events = [RawEvent.from_dict(e) for e in json.load(f)]
    
    # Load screenshots
    screenshots_path = session_dir / "screenshots.json"
    screenshots = []
    if screenshots_path.exists():
        with open(screenshots_path) as f:
            screenshots = [Screenshot.from_dict(s) for s in json.load(f)]
    
    return Recording(
        recording_id=metadata["recording_id"],
        name=metadata["name"],
        created_at=datetime.fromisoformat(metadata["created_at"]),
        events=events,
        screenshots=screenshots,
        duration_ms=metadata.get("duration_ms", 0),
    )
