"""
Recording panel — controls for starting/stopping recordings.

Displays:
- Record / Stop button
- Recording name input
- Live status (duration, event count, screenshot count)
- Recording indicator (pulsing dot)
"""

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class RecordingPanel(QWidget):
    """Panel with recording controls and live status."""

    # Signals
    record_requested = pyqtSignal(str)  # name
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    resume_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_recording = False
        self._is_paused = False
        self._elapsed_seconds = 0
        self._event_count = 0
        self._screenshot_count = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QLabel("⏺ Recording")
        header.setObjectName("heading")
        layout.addWidget(header)

        # Recording name input
        name_row = QHBoxLayout()
        name_label = QLabel("Name:")
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("My Task Recording")
        self._name_input.setText("Recording")
        name_row.addWidget(name_label)
        name_row.addWidget(self._name_input, 1)
        layout.addLayout(name_row)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._record_btn = QPushButton("⏺  Record")
        self._record_btn.setMinimumHeight(40)
        self._record_btn.clicked.connect(self._on_record)

        self._pause_btn = QPushButton("⏸  Pause")
        self._pause_btn.setObjectName("secondaryBtn")
        self._pause_btn.setMinimumHeight(40)
        self._pause_btn.setVisible(False)
        self._pause_btn.clicked.connect(self._on_pause)

        self._stop_btn = QPushButton("⏹  Stop")
        self._stop_btn.setObjectName("dangerBtn")
        self._stop_btn.setMinimumHeight(40)
        self._stop_btn.setVisible(False)
        self._stop_btn.clicked.connect(self._on_stop)

        btn_row.addWidget(self._record_btn)
        btn_row.addWidget(self._pause_btn)
        btn_row.addWidget(self._stop_btn)
        layout.addLayout(btn_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3f3f5c;")
        layout.addWidget(sep)

        # Live stats
        stats_row = QHBoxLayout()
        stats_row.setSpacing(24)

        self._time_label = QLabel("00:00")
        self._time_label.setFont(QFont("monospace", 24, QFont.Weight.Bold))
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._events_label = QLabel("Events: 0")
        self._events_label.setObjectName("subheading")

        self._screenshots_label = QLabel("Screenshots: 0")
        self._screenshots_label.setObjectName("subheading")

        stats_row.addWidget(self._time_label)
        stats_row.addStretch()
        stats_row.addWidget(self._events_label)
        stats_row.addWidget(self._screenshots_label)
        layout.addLayout(stats_row)

        # Status message
        self._status_label = QLabel("Ready to record")
        self._status_label.setObjectName("statusLabel")
        layout.addWidget(self._status_label)

        layout.addStretch()

    def _on_record(self):
        name = self._name_input.text().strip() or "Recording"
        self._set_recording(True)
        self.record_requested.emit(name)

    def _on_stop(self):
        self._set_recording(False)
        self.stop_requested.emit()

    def _on_pause(self):
        if self._is_paused:
            self._is_paused = False
            self._pause_btn.setText("⏸  Pause")
            self._status_label.setText("Recording...")
            self._timer.start(1000)
            self.resume_requested.emit()
        else:
            self._is_paused = True
            self._pause_btn.setText("▶  Resume")
            self._status_label.setText("Paused")
            self._timer.stop()
            self.pause_requested.emit()

    def _set_recording(self, recording: bool):
        self._is_recording = recording
        self._is_paused = False

        if recording:
            self._elapsed_seconds = 0
            self._event_count = 0
            self._screenshot_count = 0
            self._record_btn.setVisible(False)
            self._pause_btn.setVisible(True)
            self._stop_btn.setVisible(True)
            self._name_input.setEnabled(False)
            self._status_label.setText("Recording...")
            self._timer.start(1000)
        else:
            self._record_btn.setVisible(True)
            self._pause_btn.setVisible(False)
            self._stop_btn.setVisible(False)
            self._name_input.setEnabled(True)
            self._status_label.setText("Recording saved")
            self._timer.stop()

    def _tick(self):
        self._elapsed_seconds += 1
        mins = self._elapsed_seconds // 60
        secs = self._elapsed_seconds % 60
        self._time_label.setText(f"{mins:02d}:{secs:02d}")

    def update_stats(self, events: int, screenshots: int):
        """Update live stats from the recording session."""
        self._event_count = events
        self._screenshot_count = screenshots
        self._events_label.setText(f"Events: {events}")
        self._screenshots_label.setText(f"Screenshots: {screenshots}")

    @property
    def is_recording(self) -> bool:
        return self._is_recording
