"""
Action executor — performs mouse/keyboard actions on the desktop.

Translates semantic workflow steps into real input events:
- Mouse clicks (left, right, double)
- Keyboard typing
- Hotkey combinations
- Scrolling
- Configurable delays between actions
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Status of an action execution."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutionResult:
    """Result of executing a single action."""
    status: ExecutionStatus
    action_type: str
    description: str = ""
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    screenshot_after: Optional[bytes] = None


@dataclass
class ExecutorConfig:
    """Configuration for action execution."""
    action_delay_ms: int = 500  # Delay between actions
    type_interval_ms: int = 50  # Delay between keystrokes
    click_duration_ms: int = 100  # Mouse button hold duration
    move_duration_ms: int = 200  # Mouse move animation duration
    dry_run: bool = False  # If True, log but don't execute


class ActionExecutor:
    """
    Executes mouse and keyboard actions on the desktop.
    
    Wraps pyautogui for cross-platform input simulation.
    Supports dry-run mode for testing without side effects.
    """

    def __init__(
        self,
        config: Optional[ExecutorConfig] = None,
        input_backend=None,
    ):
        """
        Args:
            config: Execution configuration.
            input_backend: Optional backend module (default: pyautogui).
                           Must implement click(), typewrite(), hotkey(), scroll(), moveTo().
        """
        self._config = config or ExecutorConfig()
        self._backend = input_backend
        self._initialized = False

    def _get_backend(self):
        """Lazy-load the input backend."""
        if self._backend is not None:
            return self._backend
        if not self._initialized:
            try:
                import pyautogui
                pyautogui.FAILSAFE = True  # Move mouse to corner to abort
                pyautogui.PAUSE = 0.05  # Small built-in pause
                self._backend = pyautogui
                self._initialized = True
            except ImportError:
                raise ImportError(
                    "pyautogui required for action execution. "
                    "Install with: pip install pyautogui"
                )
        return self._backend

    async def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        clicks: int = 1,
    ) -> ExecutionResult:
        """
        Click at a screen position.
        
        Args:
            x: X pixel coordinate.
            y: Y pixel coordinate.
            button: "left", "right", or "middle".
            clicks: Number of clicks (2 for double-click).
        """
        desc = f"{'Double-c' if clicks == 2 else 'C'}lick ({button}) at ({x}, {y})"
        logger.info("Executing: %s", desc)

        if self._config.dry_run:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                action_type="click",
                description=f"[DRY RUN] {desc}",
            )

        start = time.monotonic()
        try:
            backend = self._get_backend()
            duration = self._config.move_duration_ms / 1000.0
            backend.moveTo(x, y, duration=duration)
            backend.click(
                x=x, y=y,
                button=button,
                clicks=clicks,
                interval=0.1,
            )
            elapsed = (time.monotonic() - start) * 1000
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                action_type="click",
                description=desc,
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.error("Click failed: %s", e)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                action_type="click",
                description=desc,
                elapsed_ms=elapsed,
                error=str(e),
            )

    async def type_text(
        self,
        text: str,
        interval: Optional[float] = None,
    ) -> ExecutionResult:
        """
        Type text using keyboard simulation.
        
        Args:
            text: Text to type.
            interval: Override per-character delay (seconds).
        """
        preview = text[:50] + ("..." if len(text) > 50 else "")
        desc = f"Type: '{preview}'"
        logger.info("Executing: %s", desc)

        if self._config.dry_run:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                action_type="type",
                description=f"[DRY RUN] {desc}",
            )

        start = time.monotonic()
        try:
            backend = self._get_backend()
            char_interval = interval or (self._config.type_interval_ms / 1000.0)

            # pyautogui.typewrite only handles ASCII, use write() for unicode
            if hasattr(backend, "write"):
                backend.write(text, interval=char_interval)
            else:
                backend.typewrite(text, interval=char_interval)

            elapsed = (time.monotonic() - start) * 1000
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                action_type="type",
                description=desc,
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.error("Type failed: %s", e)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                action_type="type",
                description=desc,
                elapsed_ms=elapsed,
                error=str(e),
            )

    async def hotkey(self, combo: str) -> ExecutionResult:
        """
        Press a hotkey combination.
        
        Args:
            combo: Key combination string like "ctrl+s", "alt+tab".
        """
        desc = f"Hotkey: {combo}"
        logger.info("Executing: %s", desc)

        if self._config.dry_run:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                action_type="hotkey",
                description=f"[DRY RUN] {desc}",
            )

        start = time.monotonic()
        try:
            backend = self._get_backend()
            keys = [k.strip() for k in combo.split("+")]
            backend.hotkey(*keys)

            elapsed = (time.monotonic() - start) * 1000
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                action_type="hotkey",
                description=desc,
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.error("Hotkey failed: %s", e)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                action_type="hotkey",
                description=desc,
                elapsed_ms=elapsed,
                error=str(e),
            )

    async def scroll(
        self,
        dx: int = 0,
        dy: int = 0,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> ExecutionResult:
        """
        Scroll the mouse wheel.
        
        Args:
            dx: Horizontal scroll amount (positive = right).
            dy: Vertical scroll amount (positive = up, negative = down).
            x: Optional X position to scroll at.
            y: Optional Y position to scroll at.
        """
        desc = f"Scroll dx={dx} dy={dy}" + (f" at ({x}, {y})" if x is not None else "")
        logger.info("Executing: %s", desc)

        if self._config.dry_run:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                action_type="scroll",
                description=f"[DRY RUN] {desc}",
            )

        start = time.monotonic()
        try:
            backend = self._get_backend()
            if dy != 0:
                backend.scroll(dy, x=x, y=y)
            if dx != 0 and hasattr(backend, "hscroll"):
                backend.hscroll(dx, x=x, y=y)

            elapsed = (time.monotonic() - start) * 1000
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                action_type="scroll",
                description=desc,
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.error("Scroll failed: %s", e)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                action_type="scroll",
                description=desc,
                elapsed_ms=elapsed,
                error=str(e),
            )

    async def wait(self, ms: int) -> ExecutionResult:
        """
        Wait for a specified duration.
        
        Args:
            ms: Milliseconds to wait.
        """
        desc = f"Wait {ms}ms"
        logger.info("Executing: %s", desc)

        if not self._config.dry_run:
            await asyncio.sleep(ms / 1000.0)

        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            action_type="wait",
            description=desc,
            elapsed_ms=float(ms),
        )

    async def action_delay(self) -> None:
        """Apply the configured delay between actions."""
        if not self._config.dry_run and self._config.action_delay_ms > 0:
            await asyncio.sleep(self._config.action_delay_ms / 1000.0)
