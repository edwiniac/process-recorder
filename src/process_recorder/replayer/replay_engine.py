"""
Replay engine — orchestrates workflow execution.

Loads a workflow and executes each step:
1. Find the target element on screen (via vision)
2. Execute the action (click, type, scroll, hotkey)
3. Capture result screenshot
4. Move to next step

Supports pause/resume, step-by-step mode, and error recovery.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from ..models import ActionType, BoundingBox, SemanticStep, Workflow
from ..vision.base import VisionAdapter
from .action_executor import ActionExecutor, ExecutionResult, ExecutionStatus, ExecutorConfig
from .element_finder import ElementFinder, FinderConfig, FindResult

logger = logging.getLogger(__name__)


class ReplayState(str, Enum):
    """Current state of the replay engine."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class ErrorStrategy(str, Enum):
    """How to handle step failures."""
    STOP = "stop"  # Stop replay on first error
    SKIP = "skip"  # Skip failed step, continue
    RETRY = "retry"  # Retry failed step (up to max_retries)
    ASK = "ask"  # Pause and wait for user decision


@dataclass
class StepResult:
    """Result of executing a single workflow step."""
    step: SemanticStep
    find_result: Optional[FindResult] = None
    execution_result: Optional[ExecutionResult] = None
    status: ExecutionStatus = ExecutionStatus.SKIPPED
    error: Optional[str] = None
    elapsed_ms: float = 0.0


@dataclass
class ReplayResult:
    """Result of a complete workflow replay."""
    workflow_id: str
    workflow_name: str
    state: ReplayState
    step_results: list[StepResult] = field(default_factory=list)
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0
    total_elapsed_ms: float = 0.0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return self.completed_steps / self.total_steps

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "state": self.state.value,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "skipped_steps": self.skipped_steps,
            "success_rate": round(self.success_rate, 2),
            "total_elapsed_ms": round(self.total_elapsed_ms, 1),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


@dataclass
class ReplayConfig:
    """Configuration for the replay engine."""
    error_strategy: ErrorStrategy = ErrorStrategy.STOP
    max_retries: int = 3
    finder_config: Optional[FinderConfig] = None
    executor_config: Optional[ExecutorConfig] = None
    capture_screenshots: bool = True  # Capture after each step
    step_callback: Optional[Callable] = None  # Called after each step


class ReplayEngine:
    """
    Executes workflow replays.
    
    Usage:
        engine = ReplayEngine(vision_adapter)
        result = await engine.replay(workflow)
    """

    def __init__(
        self,
        vision: VisionAdapter,
        config: Optional[ReplayConfig] = None,
        capture_fn=None,
    ):
        self._vision = vision
        self._config = config or ReplayConfig()
        self._finder = ElementFinder(
            vision,
            capture_fn=capture_fn,
            config=self._config.finder_config,
        )
        self._executor = ActionExecutor(
            config=self._config.executor_config,
        )
        self._state = ReplayState.IDLE
        self._current_step = 0
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused initially
        self._stop_requested = False

    @property
    def state(self) -> ReplayState:
        return self._state

    @property
    def current_step(self) -> int:
        return self._current_step

    async def replay(
        self,
        workflow: Workflow,
        start_step: int = 0,
    ) -> ReplayResult:
        """
        Execute a full workflow replay.
        
        Args:
            workflow: The workflow to replay.
            start_step: Step index to start from (0-based).
            
        Returns:
            ReplayResult with outcomes for each step.
        """
        self._state = ReplayState.RUNNING
        self._stop_requested = False
        self._current_step = start_step

        result = ReplayResult(
            workflow_id=workflow.workflow_id,
            workflow_name=workflow.name,
            state=ReplayState.RUNNING,
            total_steps=len(workflow.steps),
            started_at=datetime.now(),
        )

        logger.info(
            "Starting replay of '%s' (%d steps, from step %d)",
            workflow.name, len(workflow.steps), start_step,
        )

        start_time = time.monotonic()

        for i in range(start_step, len(workflow.steps)):
            # Check for stop request
            if self._stop_requested:
                self._state = ReplayState.STOPPED
                result.state = ReplayState.STOPPED
                break

            # Wait if paused
            await self._pause_event.wait()

            self._current_step = i
            step = workflow.steps[i]

            logger.info(
                "Step %d/%d: %s",
                i + 1, len(workflow.steps),
                step.target_description,
            )

            step_result = await self._execute_step(step)
            result.step_results.append(step_result)

            if step_result.status == ExecutionStatus.SUCCESS:
                result.completed_steps += 1
            elif step_result.status == ExecutionStatus.FAILED:
                result.failed_steps += 1
                if self._config.error_strategy == ErrorStrategy.STOP:
                    self._state = ReplayState.FAILED
                    result.state = ReplayState.FAILED
                    break
            else:
                result.skipped_steps += 1

            # Notify callback
            if self._config.step_callback:
                try:
                    self._config.step_callback(i, step, step_result)
                except Exception as e:
                    logger.warning("Step callback error: %s", e)

            # Delay between steps
            await self._executor.action_delay()

        # Finalize
        total_ms = (time.monotonic() - start_time) * 1000
        result.total_elapsed_ms = total_ms
        result.finished_at = datetime.now()

        if self._state == ReplayState.RUNNING:
            self._state = ReplayState.COMPLETED
            result.state = ReplayState.COMPLETED

        logger.info(
            "Replay '%s' %s: %d/%d steps succeeded (%.0fms)",
            workflow.name,
            result.state.value,
            result.completed_steps,
            result.total_steps,
            total_ms,
        )

        return result

    async def _execute_step(self, step: SemanticStep) -> StepResult:
        """Execute a single workflow step."""
        start = time.monotonic()
        find_result = None
        exec_result = None

        retries = 0
        max_retries = self._config.max_retries if self._config.error_strategy == ErrorStrategy.RETRY else 1

        while retries < max_retries:
            retries += 1

            try:
                if step.action_type == ActionType.CLICK:
                    step_result = await self._execute_click(step)
                elif step.action_type == ActionType.TYPE:
                    step_result = await self._execute_type(step)
                elif step.action_type == ActionType.HOTKEY:
                    step_result = await self._execute_hotkey(step)
                elif step.action_type == ActionType.SCROLL:
                    step_result = await self._execute_scroll(step)
                elif step.action_type == ActionType.WAIT:
                    step_result = await self._execute_wait(step)
                else:
                    step_result = StepResult(
                        step=step,
                        status=ExecutionStatus.SKIPPED,
                        error=f"Unknown action type: {step.action_type}",
                    )

                if step_result.status == ExecutionStatus.SUCCESS:
                    break

                if self._config.error_strategy != ErrorStrategy.RETRY:
                    break

                logger.info("Retrying step (attempt %d/%d)...", retries + 1, max_retries)

            except Exception as e:
                logger.error("Step execution error: %s", e)
                step_result = StepResult(
                    step=step,
                    status=ExecutionStatus.FAILED,
                    error=str(e),
                )
                if self._config.error_strategy != ErrorStrategy.RETRY:
                    break

        step_result.elapsed_ms = (time.monotonic() - start) * 1000
        return step_result

    async def _execute_click(self, step: SemanticStep) -> StepResult:
        """Execute a click step: find element then click."""
        # First, find the element on screen
        find_result = await self._finder.find(step.target_description)

        if not find_result.found:
            # Fallback: use recorded coordinates if available
            if step.target_region:
                logger.warning(
                    "Element not found by vision, using recorded coordinates"
                )
                cx, cy = step.target_region.center
                exec_result = await self._executor.click(cx, cy)
                return StepResult(
                    step=step,
                    find_result=find_result,
                    execution_result=exec_result,
                    status=exec_result.status,
                )
            return StepResult(
                step=step,
                find_result=find_result,
                status=ExecutionStatus.FAILED,
                error=f"Element not found: {step.target_description}",
            )

        # Click at the found location
        cx, cy = find_result.center
        exec_result = await self._executor.click(cx, cy)

        return StepResult(
            step=step,
            find_result=find_result,
            execution_result=exec_result,
            status=exec_result.status,
        )

    async def _execute_type(self, step: SemanticStep) -> StepResult:
        """Execute a typing step."""
        text = step.input_data or ""
        if not text:
            return StepResult(
                step=step,
                status=ExecutionStatus.SKIPPED,
                error="No text to type",
            )

        exec_result = await self._executor.type_text(text)
        return StepResult(
            step=step,
            execution_result=exec_result,
            status=exec_result.status,
        )

    async def _execute_hotkey(self, step: SemanticStep) -> StepResult:
        """Execute a hotkey step."""
        combo = step.input_data or ""
        if not combo:
            return StepResult(
                step=step,
                status=ExecutionStatus.SKIPPED,
                error="No hotkey combo",
            )

        exec_result = await self._executor.hotkey(combo)
        return StepResult(
            step=step,
            execution_result=exec_result,
            status=exec_result.status,
        )

    async def _execute_scroll(self, step: SemanticStep) -> StepResult:
        """Execute a scroll step."""
        # Extract scroll amount from description or default
        dy = -3  # Default scroll down
        if "up" in step.target_description.lower():
            dy = 3

        exec_result = await self._executor.scroll(dy=dy)
        return StepResult(
            step=step,
            execution_result=exec_result,
            status=exec_result.status,
        )

    async def _execute_wait(self, step: SemanticStep) -> StepResult:
        """Execute a wait step."""
        ms = 1000  # Default 1 second
        exec_result = await self._executor.wait(ms)
        return StepResult(
            step=step,
            execution_result=exec_result,
            status=exec_result.status,
        )

    def pause(self) -> None:
        """Pause the replay."""
        if self._state == ReplayState.RUNNING:
            self._pause_event.clear()
            self._state = ReplayState.PAUSED
            logger.info("Replay paused at step %d", self._current_step)

    def resume(self) -> None:
        """Resume a paused replay."""
        if self._state == ReplayState.PAUSED:
            self._pause_event.set()
            self._state = ReplayState.RUNNING
            logger.info("Replay resumed at step %d", self._current_step)

    def stop(self) -> None:
        """Stop the replay."""
        self._stop_requested = True
        self._pause_event.set()  # Unblock if paused
        logger.info("Replay stop requested")

    async def replay_and_save(
        self,
        workflow: Workflow,
        output_dir: Path,
        start_step: int = 0,
    ) -> ReplayResult:
        """
        Replay a workflow and save the result report.
        
        Args:
            workflow: Workflow to replay.
            output_dir: Directory to save replay report.
            start_step: Step to start from.
            
        Returns:
            ReplayResult.
        """
        result = await self.replay(workflow, start_step)

        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / f"replay_{workflow.workflow_id}_{int(time.time())}.json"
        report_path.write_text(json.dumps(result.to_dict(), indent=2, default=str))
        logger.info("Replay report saved to %s", report_path)

        return result
