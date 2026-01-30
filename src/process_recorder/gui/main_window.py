"""
Main application window — assembles all GUI panels.

Layout:
┌─────────────────────────────────────────────────┐
│  Menu Bar (File, Settings, Help)                │
├─────────────────────┬───────────────────────────┤
│                     │                           │
│  Recording Panel    │   Workflow List            │
│                     │                           │
│                     ├───────────────────────────┤
│                     │                           │
│                     │   Replay Panel            │
│                     │                           │
├─────────────────────┴───────────────────────────┤
│  Status Bar                                     │
└─────────────────────────────────────────────────┘
"""

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMenuBar,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from ..models import AppConfig
from ..config import load_config, save_config
from .recording_panel import RecordingPanel
from .replay_panel import ReplayPanel
from .settings_dialog import SettingsDialog
from .styles import MAIN_STYLESHEET
from .workflow_list import WorkflowListPanel


class MainWindow(QMainWindow):
    """Main ProcessRecorder application window."""

    APP_NAME = "ProcessRecorder"
    VERSION = "0.1.0"

    def __init__(self, config: AppConfig | None = None):
        super().__init__()
        self._config = config or load_config()
        self._setup_window()
        self._setup_menu()
        self._setup_panels()
        self._setup_status_bar()
        self._connect_signals()
        self.setStyleSheet(MAIN_STYLESHEET)

        # Load initial data
        self._workflow_list.refresh()

    def _setup_window(self):
        self.setWindowTitle(f"{self.APP_NAME} v{self.VERSION}")
        self.setMinimumSize(QSize(960, 680))
        self.resize(1100, 750)

    def _setup_menu(self):
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        refresh_action = QAction("&Refresh Workflows", self)
        refresh_action.setShortcut("Ctrl+R")
        refresh_action.triggered.connect(lambda: self._workflow_list.refresh())
        file_menu.addAction(refresh_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Settings menu
        settings_menu = menu_bar.addMenu("&Settings")

        open_settings = QAction("⚙ &Preferences...", self)
        open_settings.setShortcut("Ctrl+,")
        open_settings.triggered.connect(self._open_settings)
        settings_menu.addAction(open_settings)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_panels(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Main splitter: left (recording) | right (workflows + replay)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Recording panel
        self._recording_panel = RecordingPanel()
        splitter.addWidget(self._recording_panel)

        # Right: vertical split — workflows on top, replay on bottom
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        self._workflow_list = WorkflowListPanel(
            workflows_dir=self._config.storage.workflows_dir
        )
        right_splitter.addWidget(self._workflow_list)

        self._replay_panel = ReplayPanel()
        right_splitter.addWidget(self._replay_panel)

        right_splitter.setSizes([400, 300])
        splitter.addWidget(right_splitter)

        splitter.setSizes([380, 700])
        main_layout.addWidget(splitter)

    def _setup_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage(f"{self.APP_NAME} ready")

    def _connect_signals(self):
        # Recording
        self._recording_panel.record_requested.connect(self._on_record)
        self._recording_panel.stop_requested.connect(self._on_stop_recording)

        # Workflow list
        self._workflow_list.replay_requested.connect(self._on_replay_workflow)

        # Replay
        self._replay_panel.replay_start.connect(self._on_start_replay)
        self._replay_panel.replay_stop.connect(self._on_stop_replay)

    # ── Handlers ──────────────────────────────────────────────────────

    def _on_record(self, name: str):
        self._status_bar.showMessage(f"Recording: {name}...")

    def _on_stop_recording(self):
        self._status_bar.showMessage("Recording saved")
        self._workflow_list.refresh()

    def _on_replay_workflow(self, workflow):
        self._replay_panel.set_workflow(workflow.name, len(workflow.steps))
        self._status_bar.showMessage(f"Loaded workflow: {workflow.name}")

    def _on_start_replay(self):
        self._status_bar.showMessage("Replaying...")

    def _on_stop_replay(self):
        self._status_bar.showMessage("Replay stopped")

    def _open_settings(self):
        dialog = SettingsDialog(self._config, parent=self)
        if dialog.exec():
            self._config = dialog.get_config()
            try:
                from pathlib import Path
                save_config(self._config, Path("config.yaml"))
                self._status_bar.showMessage("Settings saved")
            except Exception as e:
                self._status_bar.showMessage(f"Failed to save settings: {e}")

    def _show_about(self):
        QMessageBox.about(
            self,
            f"About {self.APP_NAME}",
            f"<h2>{self.APP_NAME} v{self.VERSION}</h2>"
            f"<p>Watch Me, Learn, Repeat</p>"
            f"<p>Desktop automation through demonstration.</p>"
            f"<p>Built by Edwin Isac</p>"
        )

    # ── Public API (for controller integration) ───────────────────────

    @property
    def recording_panel(self) -> RecordingPanel:
        return self._recording_panel

    @property
    def workflow_list(self) -> WorkflowListPanel:
        return self._workflow_list

    @property
    def replay_panel(self) -> ReplayPanel:
        return self._replay_panel

    @property
    def config(self) -> AppConfig:
        return self._config
