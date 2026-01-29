"""
Unit tests for ScreenCapturer module.

Note: Screen capture tests may fail in headless environments without 
a display server. Tests are marked appropriately.
"""

import time
import os
import pytest
from pathlib import Path

from process_recorder.recorder.screen_capturer import ScreenCapturer, CaptureConfig


# Check if we have a display
def has_display():
    """Check if a display is available for screen capture."""
    # On Linux, check DISPLAY env var
    if os.name == 'posix':
        display = os.environ.get('DISPLAY')
        if not display:
            return False
    
    # Try to actually capture to verify
    try:
        import mss
        with mss.mss() as sct:
            # Try to grab a small screenshot
            sct.grab(sct.monitors[0])
        return True
    except Exception:
        return False


requires_display = pytest.mark.skipif(
    not has_display(),
    reason="No display available for screen capture"
)


class TestCaptureConfig:
    """Tests for CaptureConfig - works without display."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = CaptureConfig()
        
        assert config.interval_ms == 500
        assert config.capture_on_demand == True
        assert config.max_screenshots == 1000
        assert config.output_dir is None
        assert config.compression_quality == 85
        assert config.monitor == 0
    
    def test_custom_values(self):
        """Test custom configuration."""
        config = CaptureConfig(
            interval_ms=100,
            max_screenshots=50,
            monitor=1,
            compression_quality=90
        )
        
        assert config.interval_ms == 100
        assert config.max_screenshots == 50
        assert config.monitor == 1
        assert config.compression_quality == 90


class TestScreenCapturerBasic:
    """Basic tests that don't require screen capture."""
    
    def test_create_capturer_default_config(self):
        """Test creating capturer with default config."""
        capturer = ScreenCapturer()
        
        assert capturer.config.interval_ms == 500
        assert capturer.config.max_screenshots == 1000
        assert not capturer.is_running
    
    def test_create_capturer_custom_config(self):
        """Test creating capturer with custom config."""
        config = CaptureConfig(
            interval_ms=250,
            max_screenshots=500,
            compression_quality=90
        )
        capturer = ScreenCapturer(config)
        
        assert capturer.config.interval_ms == 250
        assert capturer.config.max_screenshots == 500
    
    def test_capture_without_start_raises(self):
        """Test that capturing without starting raises error."""
        capturer = ScreenCapturer()
        
        with pytest.raises(RuntimeError, match="not started"):
            capturer.capture()
    
    def test_screenshot_count_starts_at_zero(self):
        """Test that screenshot count starts at 0."""
        capturer = ScreenCapturer()
        assert capturer.screenshot_count == 0
    
    def test_is_running_starts_false(self):
        """Test that is_running starts as False."""
        capturer = ScreenCapturer()
        assert not capturer.is_running


@requires_display
class TestScreenCapturerWithDisplay:
    """Tests that require a display - skipped in headless env."""
    
    def test_capture_single_screenshot(self):
        """Test capturing a single screenshot."""
        capturer = ScreenCapturer()
        capturer.start()
        
        try:
            screenshot, img_bytes = capturer.capture()
            
            assert screenshot.screenshot_id == "0001"
            assert screenshot.width > 0
            assert screenshot.height > 0
            assert screenshot.timestamp > 0
            assert len(img_bytes) > 0
            assert capturer.screenshot_count == 1
        finally:
            capturer.stop()
    
    def test_capture_multiple_screenshots(self):
        """Test capturing multiple screenshots."""
        capturer = ScreenCapturer()
        capturer.start()
        
        try:
            ss1, _ = capturer.capture()
            ss2, _ = capturer.capture()
            ss3, _ = capturer.capture()
            
            assert ss1.screenshot_id == "0001"
            assert ss2.screenshot_id == "0002"
            assert ss3.screenshot_id == "0003"
            assert capturer.screenshot_count == 3
        finally:
            capturer.stop()
    
    def test_capture_and_save(self, temp_dir):
        """Test capturing and saving screenshots to disk."""
        config = CaptureConfig(output_dir=temp_dir / "screenshots")
        capturer = ScreenCapturer(config)
        capturer.start()
        
        try:
            screenshot = capturer.capture_and_save()
            
            assert Path(screenshot.filepath).exists()
            assert Path(screenshot.filepath).stat().st_size > 0
        finally:
            capturer.stop()
    
    def test_capture_and_save_without_output_dir_raises(self):
        """Test that capture_and_save without output_dir raises."""
        capturer = ScreenCapturer()  # No output_dir
        capturer.start()
        
        try:
            with pytest.raises(RuntimeError, match="output_dir"):
                capturer.capture_and_save()
        finally:
            capturer.stop()
    
    def test_max_screenshots_exceeded(self):
        """Test that exceeding max screenshots raises error."""
        config = CaptureConfig(max_screenshots=3)
        capturer = ScreenCapturer(config)
        capturer.start()
        
        try:
            capturer.capture()  # 1
            capturer.capture()  # 2
            capturer.capture()  # 3
            
            with pytest.raises(RuntimeError, match="Maximum screenshots"):
                capturer.capture()  # 4 - should fail
        finally:
            capturer.stop()
    
    def test_context_manager(self):
        """Test using capturer as context manager."""
        with ScreenCapturer() as capturer:
            screenshot, img_bytes = capturer.capture()
            assert screenshot.screenshot_id == "0001"
        
        # After exit, should be stopped
        with pytest.raises(RuntimeError):
            capturer.capture()
    
    def test_get_screen_size(self):
        """Test getting screen size."""
        capturer = ScreenCapturer()
        width, height = capturer.get_screen_size()
        
        assert width > 0
        assert height > 0
    
    def test_callback_on_capture(self, temp_dir):
        """Test that callbacks are called on capture."""
        config = CaptureConfig(output_dir=temp_dir / "screenshots")
        capturer = ScreenCapturer(config)
        
        captured = []
        
        def on_capture(screenshot, img_bytes):
            captured.append((screenshot, len(img_bytes)))
        
        capturer.on_capture(on_capture)
        capturer.start()
        
        try:
            capturer.capture_and_save()
            capturer.capture_and_save()
            
            assert len(captured) == 2
            assert captured[0][0].screenshot_id == "0001"
            assert captured[1][0].screenshot_id == "0002"
        finally:
            capturer.stop()
    
    def test_continuous_capture(self, temp_dir):
        """Test continuous capture mode."""
        config = CaptureConfig(
            interval_ms=100,  # Fast for testing
            output_dir=temp_dir / "screenshots"
        )
        capturer = ScreenCapturer(config)
        capturer.start()
        
        try:
            capturer.start_continuous()
            assert capturer.is_running
            
            # Wait for some captures
            time.sleep(0.35)
            
            capturer.stop_continuous()
            assert not capturer.is_running
            
            # Should have captured at least 2-3 screenshots
            assert capturer.screenshot_count >= 2
        finally:
            capturer.stop()
    
    def test_start_stop_idempotent(self):
        """Test that start/stop can be called multiple times."""
        capturer = ScreenCapturer()
        
        capturer.start()
        capturer.start()  # Should be safe
        
        capturer.stop()
        capturer.stop()  # Should be safe


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
