"""
Tests for GUI components.

Tests widget logic without requiring a display server.
Uses PyQt6's QApplication in offscreen mode.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Force offscreen rendering for headless testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

# Create QApplication once for all tests
_app = None

def get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return get_app()


# Import after QApplication setup
from process_recorder.gui.recording_panel import RecordingPanel
from process_recorder.gui.replay_panel import ReplayPanel
from process_recorder.gui.workflow_list import WorkflowListPanel
from process_recorder.gui.settings_dialog import SettingsDialog
from process_recorder.gui.main_window import MainWindow
from process_recorder.models import AppConfig, Workflow, SemanticStep, ActionType


# ── RecordingPanel Tests ─────────────────────────────────────────────

class TestRecordingPanel:
    @pytest.fixture
    def panel(self):
        return RecordingPanel()

    def test_initial_state(self, panel):
        assert panel.is_recording is False

    def test_record_emits_signal(self, panel):
        callback = MagicMock()
        panel.record_requested.connect(callback)
        panel._name_input.setText("Test Recording")
        panel._on_record()
        callback.assert_called_once_with("Test Recording")
        assert panel.is_recording is True

    def test_stop_emits_signal(self, panel):
        callback = MagicMock()
        panel.stop_requested.connect(callback)
        panel._on_record()  # Start first
        panel._on_stop()
        callback.assert_called_once()
        assert panel.is_recording is False

    def test_default_name(self, panel):
        callback = MagicMock()
        panel.record_requested.connect(callback)
        panel._name_input.clear()
        panel._on_record()
        callback.assert_called_once_with("Recording")

    def test_update_stats(self, panel):
        panel.update_stats(events=42, screenshots=15)
        assert "42" in panel._events_label.text()
        assert "15" in panel._screenshots_label.text()

    def test_pause_toggle(self, panel):
        panel._on_record()
        assert not panel._is_paused

        pause_cb = MagicMock()
        resume_cb = MagicMock()
        panel.pause_requested.connect(pause_cb)
        panel.resume_requested.connect(resume_cb)

        panel._on_pause()
        assert panel._is_paused
        pause_cb.assert_called_once()

        panel._on_pause()
        assert not panel._is_paused
        resume_cb.assert_called_once()

    def test_buttons_toggle_on_record(self, panel):
        # Use isHidden() since parent widget isn't shown in tests
        assert not panel._record_btn.isHidden()
        assert panel._stop_btn.isHidden()

        panel._on_record()
        assert panel._record_btn.isHidden()
        assert not panel._stop_btn.isHidden()
        assert not panel._pause_btn.isHidden()

    def test_buttons_toggle_on_stop(self, panel):
        panel._on_record()
        panel._on_stop()
        assert not panel._record_btn.isHidden()
        assert panel._stop_btn.isHidden()

    def test_name_disabled_during_recording(self, panel):
        assert panel._name_input.isEnabled()
        panel._on_record()
        assert not panel._name_input.isEnabled()
        panel._on_stop()
        assert panel._name_input.isEnabled()

    def test_timer_ticks(self, panel):
        panel._on_record()
        panel._tick()
        assert panel._time_label.text() == "00:01"
        panel._tick()
        assert panel._time_label.text() == "00:02"


# ── ReplayPanel Tests ────────────────────────────────────────────────

class TestReplayPanel:
    @pytest.fixture
    def panel(self):
        return ReplayPanel()

    def test_initial_state(self, panel):
        assert not panel._start_btn.isEnabled()
        assert not panel._is_replaying

    def test_set_workflow(self, panel):
        panel.set_workflow("My Workflow", 5)
        assert panel._start_btn.isEnabled()
        assert "My Workflow" in panel._workflow_label.text()
        assert "5" in panel._step_label.text()

    def test_start_emits_signal(self, panel):
        callback = MagicMock()
        panel.replay_start.connect(callback)
        panel.set_workflow("Test", 3)
        panel._on_start()
        callback.assert_called_once()
        assert panel._is_replaying

    def test_stop_emits_signal(self, panel):
        callback = MagicMock()
        panel.replay_stop.connect(callback)
        panel.set_workflow("Test", 3)
        panel._on_start()
        panel._on_stop()
        callback.assert_called_once()

    def test_update_step_progress(self, panel):
        panel.set_workflow("Test", 5)
        panel.update_step(0, "Click Save", success=True)
        assert panel._progress.value() == 1
        assert panel._log_list.count() == 1

    def test_update_step_failure(self, panel):
        panel.set_workflow("Test", 5)
        panel.update_step(0, "Click Missing", success=False)
        assert panel._log_list.count() == 1
        item_text = panel._log_list.item(0).text()
        assert "❌" in item_text

    def test_set_completed(self, panel):
        panel.set_workflow("Test", 3)
        panel.set_completed(completed=3, failed=0, elapsed_ms=5000)
        assert "100%" in panel._result_label.text()
        assert not panel._is_replaying

    def test_set_failed(self, panel):
        panel.set_workflow("Test", 3)
        panel.set_failed(step=1, error="Element not found")
        assert "Failed" in panel._result_label.text()

    def test_error_strategy_default(self, panel):
        assert panel.error_strategy == "stop"

    def test_pause_toggle(self, panel):
        panel.set_workflow("Test", 3)
        panel._on_start()

        pause_cb = MagicMock()
        resume_cb = MagicMock()
        panel.replay_pause.connect(pause_cb)
        panel.replay_resume.connect(resume_cb)

        panel._on_pause()
        assert panel._is_paused
        pause_cb.assert_called_once()

        panel._on_pause()
        assert not panel._is_paused
        resume_cb.assert_called_once()


# ── WorkflowListPanel Tests ──────────────────────────────────────────

class TestWorkflowListPanel:
    @pytest.fixture
    def workflows_dir(self, tmp_path):
        d = tmp_path / "workflows"
        d.mkdir()
        # Create a sample workflow file
        workflow = Workflow(
            workflow_id="wf_test",
            name="Test Workflow",
            description="A test",
            created_at=datetime(2026, 1, 30),
            steps=[
                SemanticStep(
                    step_id=1,
                    action_type=ActionType.CLICK,
                    target_description="Button",
                    target_screenshot_id="sc_001",
                    confidence=0.9,
                ),
            ],
            source_recording_id="rec_001",
            model_used="mock:test",
        )
        (d / "wf_test.json").write_text(
            json.dumps(workflow.to_dict(), default=str)
        )
        return d

    @pytest.fixture
    def panel(self, workflows_dir):
        return WorkflowListPanel(workflows_dir=str(workflows_dir))

    def test_refresh_loads_workflows(self, panel):
        panel.refresh()
        assert panel._list.count() == 1

    def test_refresh_empty_dir(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        panel = WorkflowListPanel(workflows_dir=str(empty_dir))
        panel.refresh()
        assert panel._list.count() == 0

    def test_refresh_nonexistent_dir(self, tmp_path):
        panel = WorkflowListPanel(workflows_dir=str(tmp_path / "nope"))
        panel.refresh()
        assert panel._list.count() == 0

    def test_selection_emits_signal(self, panel):
        callback = MagicMock()
        panel.workflow_selected.connect(callback)
        panel.refresh()
        panel._list.setCurrentRow(0)
        callback.assert_called_once()

    def test_get_selected_workflow(self, panel):
        panel.refresh()
        panel._list.setCurrentRow(0)
        wf = panel.get_selected_workflow()
        assert wf is not None
        assert wf.name == "Test Workflow"

    def test_no_selection_returns_none(self, panel):
        panel.refresh()
        panel._list.clearSelection()
        panel._list.setCurrentRow(-1)
        assert panel.get_selected_workflow() is None

    def test_replay_signal(self, panel):
        callback = MagicMock()
        panel.replay_requested.connect(callback)
        panel.refresh()
        panel._list.setCurrentRow(0)
        panel._on_replay()
        callback.assert_called_once()

    def test_details_update_on_selection(self, panel):
        panel.refresh()
        panel._list.setCurrentRow(0)
        assert "Test Workflow" in panel._detail_name.text()
        assert panel._replay_btn.isEnabled()
        assert panel._delete_btn.isEnabled()


# ── SettingsDialog Tests ─────────────────────────────────────────────

class TestSettingsDialog:
    @pytest.fixture
    def config(self):
        return AppConfig()

    @pytest.fixture
    def dialog(self, config):
        return SettingsDialog(config)

    def test_loads_default_config(self, dialog):
        assert dialog._provider_combo.currentText() == "ollama"
        assert dialog._screenshot_interval.value() == 500
        assert dialog._confidence.value() == 0.7

    def test_provider_toggles_fields(self, dialog):
        dialog._provider_combo.setCurrentText("claude")
        assert not dialog._ollama_model.isEnabled()
        assert dialog._claude_key.isEnabled()

        dialog._provider_combo.setCurrentText("ollama")
        assert dialog._ollama_model.isEnabled()
        assert not dialog._claude_key.isEnabled()

    def test_save_updates_config(self, dialog, config):
        dialog._screenshot_interval.setValue(1000)
        dialog._confidence.setValue(0.85)
        dialog._save_and_accept()

        result = dialog.get_config()
        assert result.recording.screenshot_interval_ms == 1000
        assert result.replay.confidence_threshold == 0.85

    def test_provider_change_saved(self, dialog, config):
        dialog._provider_combo.setCurrentText("claude")
        dialog._save_and_accept()
        assert dialog.get_config().vision.provider == "claude"


# ── MainWindow Tests ─────────────────────────────────────────────────

class TestMainWindow:
    @pytest.fixture
    def window(self, tmp_path):
        config = AppConfig(
            storage=AppConfig.StorageConfig(
                recordings_dir=str(tmp_path / "recordings"),
                workflows_dir=str(tmp_path / "workflows"),
            )
        )
        return MainWindow(config)

    def test_window_creates(self, window):
        assert window.windowTitle().startswith("ProcessRecorder")

    def test_has_all_panels(self, window):
        assert window.recording_panel is not None
        assert window.workflow_list is not None
        assert window.replay_panel is not None

    def test_has_menu_bar(self, window):
        menu_bar = window.menuBar()
        assert menu_bar is not None

    def test_has_status_bar(self, window):
        status = window.statusBar()
        assert status is not None

    def test_config_accessible(self, window):
        assert window.config is not None
        assert isinstance(window.config, AppConfig)

    def test_record_updates_status(self, window):
        window._on_record("My Task")
        assert "My Task" in window.statusBar().currentMessage()

    def test_stop_updates_status(self, window):
        window._on_stop_recording()
        assert "saved" in window.statusBar().currentMessage().lower()
