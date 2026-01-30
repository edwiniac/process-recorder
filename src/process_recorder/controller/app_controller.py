"""
Application controller — wires the GUI to backend modules.

Connects:
- RecordingPanel signals → RecordingSession
- WorkflowListPanel signals → WorkflowProcessor
- ReplayPanel signals → ReplayEngine
"""

import asyncio
import logging
import threading
from pathlib import Path
from typing import Optional

from ..config import load_config, save_config
from ..learner import WorkflowProcessor
from ..models import AppConfig, Workflow
from ..recorder.recording_session import RecordingSession, SessionConfig
from ..replayer import (
    ErrorStrategy,
    ExecutorConfig,
    ReplayConfig,
    ReplayEngine,
    ReplayState,
)
from ..replayer.element_finder import FinderConfig
from ..vision import create_vision_adapter

logger = logging.getLogger(__name__)


class AppController:
    """
    Central controller connecting GUI panels to backend logic.
    
    Runs async operations in a background thread to keep the GUI responsive.
    """

    def __init__(self, config: AppConfig):
        self._config = config
        self._recording_session: Optional[RecordingSession] = None
        self._replay_engine: Optional[ReplayEngine] = None
        self._current_workflow: Optional[Workflow] = None
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_thread: Optional[threading.Thread] = None

    def start(self):
        """Start the background async event loop."""
        self._async_loop = asyncio.new_event_loop()
        self._async_thread = threading.Thread(
            target=self._run_async_loop, daemon=True
        )
        self._async_thread.start()
        logger.info("Controller started with background async loop")

    def stop(self):
        """Stop the background event loop."""
        if self._async_loop and self._async_loop.is_running():
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
        if self._async_thread:
            self._async_thread.join(timeout=5)
        logger.info("Controller stopped")

    def _run_async_loop(self):
        asyncio.set_event_loop(self._async_loop)
        self._async_loop.run_forever()

    def _run_async(self, coro):
        """Schedule an async coroutine on the background loop."""
        if self._async_loop and self._async_loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, self._async_loop)
        return None

    # ── Recording ─────────────────────────────────────────────────────

    def start_recording(
        self,
        name: str,
        on_event=None,
        on_screenshot=None,
    ):
        """Start a new recording session."""
        output_dir = Path(self._config.storage.recordings_dir)
        session_config = SessionConfig(
            name=name,
            output_dir=output_dir,
            screenshot_interval_ms=self._config.recording.screenshot_interval_ms,
            capture_on_click=self._config.recording.capture_on_click,
            max_screenshots=self._config.recording.max_screenshots,
        )

        try:
            self._recording_session = RecordingSession(session_config)
            self._recording_session.start()
            logger.info("Recording started: %s", name)
        except Exception as e:
            logger.error("Failed to start recording: %s", e)
            raise

    def stop_recording(self) -> Optional[Path]:
        """Stop the current recording and return the output path."""
        if not self._recording_session:
            return None

        try:
            self._recording_session.stop()
            output = self._recording_session.output_dir
            logger.info("Recording saved to %s", output)
            self._recording_session = None
            return output
        except Exception as e:
            logger.error("Failed to stop recording: %s", e)
            self._recording_session = None
            return None

    def pause_recording(self):
        if self._recording_session:
            self._recording_session.pause()

    def resume_recording(self):
        if self._recording_session:
            self._recording_session.resume()

    def get_recording_stats(self) -> tuple[int, int]:
        """Get (event_count, screenshot_count) from active recording."""
        if self._recording_session:
            return (
                self._recording_session.event_count,
                self._recording_session.screenshot_count,
            )
        return (0, 0)

    # ── Workflow Processing ───────────────────────────────────────────

    def process_recording(self, recording_path: Path, callback=None):
        """Process a recording into a workflow (async)."""
        async def _process():
            try:
                vision = create_vision_adapter(self._config)
                processor = WorkflowProcessor(vision)

                from ..recorder.recording_session import load_recording
                recording = load_recording(recording_path)

                workflow = await processor.process_and_save(
                    recording,
                    screenshot_dir=recording_path,
                    output_dir=Path(self._config.storage.workflows_dir),
                )

                if callback:
                    callback(workflow, None)
                return workflow

            except Exception as e:
                logger.error("Processing failed: %s", e)
                if callback:
                    callback(None, e)

        self._run_async(_process())

    # ── Replay ────────────────────────────────────────────────────────

    def start_replay(
        self,
        workflow: Workflow,
        error_strategy: str = "stop",
        step_callback=None,
        done_callback=None,
    ):
        """Start replaying a workflow (async)."""
        self._current_workflow = workflow

        strategy_map = {
            "stop": ErrorStrategy.STOP,
            "skip": ErrorStrategy.SKIP,
            "retry": ErrorStrategy.RETRY,
        }

        config = ReplayConfig(
            error_strategy=strategy_map.get(error_strategy, ErrorStrategy.STOP),
            finder_config=FinderConfig(
                timeout_ms=self._config.replay.element_find_timeout_ms,
                confidence_threshold=self._config.replay.confidence_threshold,
            ),
            executor_config=ExecutorConfig(
                action_delay_ms=self._config.replay.action_delay_ms,
            ),
            step_callback=step_callback,
        )

        async def _replay():
            try:
                vision = create_vision_adapter(self._config)
                self._replay_engine = ReplayEngine(vision, config=config)
                result = await self._replay_engine.replay(workflow)

                if done_callback:
                    done_callback(result, None)
                return result

            except Exception as e:
                logger.error("Replay failed: %s", e)
                if done_callback:
                    done_callback(None, e)

        self._run_async(_replay())

    def pause_replay(self):
        if self._replay_engine:
            self._replay_engine.pause()

    def resume_replay(self):
        if self._replay_engine:
            self._replay_engine.resume()

    def stop_replay(self):
        if self._replay_engine:
            self._replay_engine.stop()

    @property
    def config(self) -> AppConfig:
        return self._config

    @config.setter
    def config(self, value: AppConfig):
        self._config = value
