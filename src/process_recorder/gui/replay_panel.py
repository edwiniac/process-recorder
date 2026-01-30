"""
Replay panel — controls and progress for workflow replay.

Features:
- Start/stop replay
- Progress bar with step counter
- Step-by-step log
- Error strategy selection
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ReplayPanel(QWidget):
    """Panel with replay controls and progress."""

    replay_start = pyqtSignal()
    replay_stop = pyqtSignal()
    replay_pause = pyqtSignal()
    replay_resume = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_replaying = False
        self._is_paused = False
        self._workflow_name = ""
        self._total_steps = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QLabel("▶ Replay")
        header.setObjectName("heading")
        layout.addWidget(header)

        # Workflow info
        self._workflow_label = QLabel("No workflow loaded")
        self._workflow_label.setObjectName("subheading")
        layout.addWidget(self._workflow_label)

        # Error strategy
        strategy_row = QHBoxLayout()
        strategy_row.addWidget(QLabel("On error:"))
        self._strategy_combo = QComboBox()
        self._strategy_combo.addItems(["Stop", "Skip", "Retry"])
        self._strategy_combo.setCurrentText("Stop")
        strategy_row.addWidget(self._strategy_combo)
        strategy_row.addStretch()
        layout.addLayout(strategy_row)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setMinimum(0)
        self._progress.setMaximum(100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        layout.addWidget(self._progress)

        # Step counter
        self._step_label = QLabel("Step 0 / 0")
        self._step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._step_label.setFont(QFont("monospace", 14))
        layout.addWidget(self._step_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._start_btn = QPushButton("▶  Start Replay")
        self._start_btn.setMinimumHeight(40)
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start)

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

        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._pause_btn)
        btn_row.addWidget(self._stop_btn)
        layout.addLayout(btn_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3f3f5c;")
        layout.addWidget(sep)

        # Step log
        log_label = QLabel("Step Log")
        log_label.setObjectName("subheading")
        layout.addWidget(log_label)

        self._log_list = QListWidget()
        self._log_list.setMaximumHeight(200)
        layout.addWidget(self._log_list)

        # Result summary
        self._result_label = QLabel("")
        self._result_label.setObjectName("statusLabel")
        layout.addWidget(self._result_label)

        layout.addStretch()

    def set_workflow(self, name: str, total_steps: int):
        """Set the workflow to replay."""
        self._workflow_name = name
        self._total_steps = total_steps
        self._workflow_label.setText(f"Workflow: {name} ({total_steps} steps)")
        self._start_btn.setEnabled(True)
        self._progress.setMaximum(total_steps)
        self._progress.setValue(0)
        self._step_label.setText(f"Step 0 / {total_steps}")
        self._log_list.clear()
        self._result_label.setText("")

    def _on_start(self):
        self._is_replaying = True
        self._start_btn.setVisible(False)
        self._pause_btn.setVisible(True)
        self._stop_btn.setVisible(True)
        self._strategy_combo.setEnabled(False)
        self._log_list.clear()
        self._result_label.setText("")
        self.replay_start.emit()

    def _on_pause(self):
        if self._is_paused:
            self._is_paused = False
            self._pause_btn.setText("⏸  Pause")
            self.replay_resume.emit()
        else:
            self._is_paused = True
            self._pause_btn.setText("▶  Resume")
            self.replay_pause.emit()

    def _on_stop(self):
        self._finish_replay("Stopped")
        self.replay_stop.emit()

    def _finish_replay(self, status: str = ""):
        self._is_replaying = False
        self._is_paused = False
        self._start_btn.setVisible(True)
        self._start_btn.setEnabled(True)
        self._pause_btn.setVisible(False)
        self._stop_btn.setVisible(False)
        self._strategy_combo.setEnabled(True)
        if status:
            self._result_label.setText(status)

    def update_step(self, step_index: int, description: str, success: bool):
        """Update progress after a step completes."""
        self._progress.setValue(step_index + 1)
        self._step_label.setText(f"Step {step_index + 1} / {self._total_steps}")

        icon = "✅" if success else "❌"
        item = QListWidgetItem(f"{icon} Step {step_index + 1}: {description}")
        if not success:
            item.setForeground(QColor("#ef4444"))
        self._log_list.addItem(item)
        self._log_list.scrollToBottom()

    def set_completed(self, completed: int, failed: int, elapsed_ms: float):
        """Show final replay result."""
        total = self._total_steps
        rate = (completed / total * 100) if total > 0 else 0
        secs = elapsed_ms / 1000

        status = (
            f"✅ Completed: {completed}/{total} steps ({rate:.0f}%) · "
            f"Failed: {failed} · Time: {secs:.1f}s"
        )
        self._finish_replay(status)

    def set_failed(self, step: int, error: str):
        """Show failure result."""
        self._finish_replay(f"❌ Failed at step {step + 1}: {error}")

    @property
    def error_strategy(self) -> str:
        return self._strategy_combo.currentText().lower()
