"""
GUI module — PyQt6 user interface for ProcessRecorder.

Components:
- MainWindow: Primary application window
- RecordingPanel: Record/stop controls with live stats
- WorkflowListPanel: Browse and manage saved workflows
- ReplayPanel: Replay controls with progress tracking
- SettingsDialog: Configure vision, recording, and replay settings
"""

from .main_window import MainWindow
from .recording_panel import RecordingPanel
from .replay_panel import ReplayPanel
from .settings_dialog import SettingsDialog
from .workflow_list import WorkflowListPanel

__all__ = [
    "MainWindow",
    "RecordingPanel",
    "ReplayPanel",
    "SettingsDialog",
    "WorkflowListPanel",
]
