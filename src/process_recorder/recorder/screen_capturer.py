"""
Screen capture module for ProcessRecorder.

Captures screenshots at intervals or on-demand.
"""

import time
import threading
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
import io

import mss
import mss.tools
from PIL import Image

from ..models import Screenshot


@dataclass
class CaptureConfig:
    """Configuration for screen capture."""
    interval_ms: int = 500  # Capture interval in milliseconds
    capture_on_demand: bool = True  # Allow manual captures
    max_screenshots: int = 1000  # Maximum screenshots per session
    output_dir: Optional[Path] = None  # Where to save screenshots
    compression_quality: int = 85  # JPEG quality (1-100)
    monitor: int = 0  # Which monitor to capture (0 = all)


class ScreenCapturer:
    """
    Captures screenshots from the screen.
    
    Can run in continuous mode (interval-based) or on-demand.
    Thread-safe for use with event listeners.
    """
    
    def __init__(self, config: Optional[CaptureConfig] = None):
        self.config = config or CaptureConfig()
        self._sct: Optional[mss.mss] = None
        self._running = False
        self._capture_thread: Optional[threading.Thread] = None
        self._screenshot_count = 0
        self._lock = threading.Lock()
        self._callbacks: list[Callable[[Screenshot, bytes], None]] = []
        self._last_capture_time: float = 0
    
    def start(self) -> None:
        """Start the screen capturer (initializes mss context)."""
        if self._sct is not None:
            return
        self._sct = mss.mss()
        self._screenshot_count = 0
    
    def stop(self) -> None:
        """Stop the screen capturer and clean up."""
        self.stop_continuous()
        if self._sct is not None:
            self._sct.close()
            self._sct = None
    
    def capture(self) -> tuple[Screenshot, bytes]:
        """
        Capture a single screenshot.
        
        Returns:
            Tuple of (Screenshot metadata, PNG bytes)
        
        Raises:
            RuntimeError: If capturer not started
            RuntimeError: If max screenshots exceeded
        """
        if self._sct is None:
            raise RuntimeError("Screen capturer not started. Call start() first.")
        
        with self._lock:
            if self._screenshot_count >= self.config.max_screenshots:
                raise RuntimeError(f"Maximum screenshots ({self.config.max_screenshots}) exceeded")
            
            # Capture the screen
            timestamp = time.time()
            monitor = self._sct.monitors[self.config.monitor]
            sct_img = self._sct.grab(monitor)
            
            # Convert to PIL Image for processing
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            # Create screenshot ID
            self._screenshot_count += 1
            screenshot_id = f"{self._screenshot_count:04d}"
            
            # Convert to PNG bytes
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG", optimize=True)
            img_bytes = img_bytes.getvalue()
            
            # Determine filepath if output_dir is set
            filepath = ""
            if self.config.output_dir:
                filepath = str(self.config.output_dir / f"{screenshot_id}.png")
            
            # Create Screenshot metadata
            screenshot = Screenshot(
                screenshot_id=screenshot_id,
                timestamp=timestamp,
                filepath=filepath,
                width=sct_img.width,
                height=sct_img.height
            )
            
            self._last_capture_time = timestamp
            
            return screenshot, img_bytes
    
    def capture_and_save(self) -> Screenshot:
        """
        Capture a screenshot and save it to disk.
        
        Returns:
            Screenshot metadata with filepath set
        
        Raises:
            RuntimeError: If output_dir not configured
        """
        if not self.config.output_dir:
            raise RuntimeError("output_dir must be configured to save screenshots")
        
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        
        screenshot, img_bytes = self.capture()
        
        # Save to disk
        with open(screenshot.filepath, "wb") as f:
            f.write(img_bytes)
        
        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(screenshot, img_bytes)
            except Exception:
                pass  # Don't let callback errors break capture
        
        return screenshot
    
    def start_continuous(self, interval_ms: Optional[int] = None) -> None:
        """
        Start continuous screenshot capture in a background thread.
        
        Args:
            interval_ms: Override capture interval (uses config default if None)
        """
        if self._running:
            return
        
        if self._sct is None:
            self.start()
        
        interval = interval_ms or self.config.interval_ms
        self._running = True
        
        def capture_loop():
            while self._running:
                try:
                    if self.config.output_dir:
                        self.capture_and_save()
                    else:
                        screenshot, img_bytes = self.capture()
                        for callback in self._callbacks:
                            try:
                                callback(screenshot, img_bytes)
                            except Exception:
                                pass
                except RuntimeError:
                    # Max screenshots reached
                    self._running = False
                    break
                
                time.sleep(interval / 1000.0)
        
        self._capture_thread = threading.Thread(target=capture_loop, daemon=True)
        self._capture_thread.start()
    
    def stop_continuous(self) -> None:
        """Stop continuous capture."""
        self._running = False
        if self._capture_thread is not None:
            self._capture_thread.join(timeout=2.0)
            self._capture_thread = None
    
    def on_capture(self, callback: Callable[[Screenshot, bytes], None]) -> None:
        """
        Register a callback for when screenshots are captured.
        
        Args:
            callback: Function(screenshot, image_bytes) called on each capture
        """
        self._callbacks.append(callback)
    
    def get_screen_size(self) -> tuple[int, int]:
        """Get the size of the primary monitor."""
        if self._sct is None:
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                return monitor["width"], monitor["height"]
        else:
            monitor = self._sct.monitors[1]
            return monitor["width"], monitor["height"]
    
    @property
    def screenshot_count(self) -> int:
        """Number of screenshots captured in this session."""
        return self._screenshot_count
    
    @property
    def is_running(self) -> bool:
        """Whether continuous capture is running."""
        return self._running
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
