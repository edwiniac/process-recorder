"""
Element finder — locates UI elements on the live screen using vision.

During replay, we need to find where UI elements are *now* (not where
they were during recording). This module:
1. Captures the current screen
2. Asks the vision model to locate an element by description
3. Returns coordinates with confidence score
4. Retries with configurable timeout
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..vision.base import ElementLocation, VisionAdapter

logger = logging.getLogger(__name__)


@dataclass
class FinderConfig:
    """Configuration for element finding."""
    timeout_ms: int = 5000  # Max time to search
    retry_interval_ms: int = 500  # Time between retries
    confidence_threshold: float = 0.7  # Minimum acceptable confidence
    max_retries: int = 10  # Maximum retry attempts
    screenshot_region: Optional[tuple[int, int, int, int]] = None  # (x, y, w, h) or full screen


@dataclass
class FindResult:
    """Result of an element search."""
    found: bool
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    confidence: float = 0.0
    description: str = ""
    attempts: int = 0
    elapsed_ms: float = 0.0
    screenshot: Optional[bytes] = None  # Screenshot where element was found

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


class ElementFinder:
    """
    Finds UI elements on the live screen using vision.
    
    Uses a capture function to take screenshots and a vision adapter
    to locate elements within them.
    """

    def __init__(
        self,
        vision: VisionAdapter,
        capture_fn=None,
        config: Optional[FinderConfig] = None,
    ):
        """
        Args:
            vision: Vision adapter for element detection.
            capture_fn: Callable that returns screenshot bytes (PNG).
                        If None, uses mss for screen capture.
            config: Finder configuration.
        """
        self._vision = vision
        self._capture_fn = capture_fn or self._default_capture
        self._config = config or FinderConfig()

    def _default_capture(self) -> bytes:
        """Default screen capture using mss."""
        try:
            import mss
            from PIL import Image
            import io

            with mss.mss() as sct:
                region = self._config.screenshot_region
                if region:
                    monitor = {
                        "left": region[0], "top": region[1],
                        "width": region[2], "height": region[3],
                    }
                else:
                    monitor = sct.monitors[1]  # Primary monitor

                raw = sct.grab(monitor)
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()
        except Exception as e:
            logger.error("Screen capture failed: %s", e)
            raise

    async def find(
        self,
        element_description: str,
        reference_screenshot: Optional[bytes] = None,
    ) -> FindResult:
        """
        Find a UI element on the current screen.
        
        Retries until found (above confidence threshold), timeout, or max retries.
        
        Args:
            element_description: Natural language description of the element.
            reference_screenshot: Optional reference screenshot from recording
                                  (for context, not currently used for matching).
            
        Returns:
            FindResult with location or not-found status.
        """
        start_time = time.monotonic()
        timeout_sec = self._config.timeout_ms / 1000.0
        retry_sec = self._config.retry_interval_ms / 1000.0
        attempts = 0

        logger.info("Searching for element: '%s'", element_description)

        while attempts < self._config.max_retries:
            elapsed = time.monotonic() - start_time
            if elapsed > timeout_sec:
                break

            attempts += 1
            logger.debug("Attempt %d to find '%s'", attempts, element_description)

            try:
                # Capture current screen
                screenshot = self._capture_fn()

                # Ask vision to find the element
                location = await self._vision.find_element(
                    screenshot, element_description
                )

                if location.found and location.confidence >= self._config.confidence_threshold:
                    elapsed_ms = (time.monotonic() - start_time) * 1000
                    logger.info(
                        "Found '%s' at (%d, %d) with confidence %.2f in %dms",
                        element_description,
                        location.x, location.y,
                        location.confidence,
                        elapsed_ms,
                    )
                    return FindResult(
                        found=True,
                        x=location.x,
                        y=location.y,
                        width=location.width,
                        height=location.height,
                        confidence=location.confidence,
                        description=location.description,
                        attempts=attempts,
                        elapsed_ms=elapsed_ms,
                        screenshot=screenshot,
                    )

                if location.found:
                    logger.debug(
                        "Found but low confidence: %.2f < %.2f",
                        location.confidence,
                        self._config.confidence_threshold,
                    )

            except Exception as e:
                logger.warning("Find attempt %d failed: %s", attempts, e)

            # Wait before retrying
            await asyncio.sleep(retry_sec)

        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.warning(
            "Element '%s' not found after %d attempts (%.0fms)",
            element_description, attempts, elapsed_ms,
        )
        return FindResult(
            found=False,
            attempts=attempts,
            elapsed_ms=elapsed_ms,
            description=f"Not found: {element_description}",
        )

    async def verify_element(
        self,
        element_description: str,
        expected_x: int,
        expected_y: int,
        tolerance: int = 50,
    ) -> FindResult:
        """
        Verify an element is where we expect it.
        
        Finds the element and checks if it's within tolerance
        of the expected position.
        
        Args:
            element_description: What to look for.
            expected_x: Expected X position.
            expected_y: Expected Y position.
            tolerance: Pixel tolerance for position match.
            
        Returns:
            FindResult (found=True only if within tolerance).
        """
        result = await self.find(element_description)

        if not result.found:
            return result

        dx = abs(result.center[0] - expected_x)
        dy = abs(result.center[1] - expected_y)

        if dx <= tolerance and dy <= tolerance:
            return result

        logger.warning(
            "Element '%s' found at (%d, %d) but expected near (%d, %d) "
            "(distance: %d, %d > tolerance %d)",
            element_description,
            result.center[0], result.center[1],
            expected_x, expected_y,
            dx, dy, tolerance,
        )
        return FindResult(
            found=False,
            x=result.x,
            y=result.y,
            width=result.width,
            height=result.height,
            confidence=result.confidence,
            attempts=result.attempts,
            elapsed_ms=result.elapsed_ms,
            description=f"Found but too far from expected position ({dx}, {dy} > {tolerance})",
        )
