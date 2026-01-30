"""
Settings dialog — configure vision provider, recording, and replay.
"""

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QCheckBox,
)

from ..models import AppConfig


class SettingsDialog(QDialog):
    """Settings dialog for configuring ProcessRecorder."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # ── Vision Provider ──
        vision_group = QGroupBox("Vision Provider")
        vision_layout = QFormLayout(vision_group)

        self._provider_combo = QComboBox()
        self._provider_combo.addItems(["ollama", "claude"])
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        vision_layout.addRow("Provider:", self._provider_combo)

        # Ollama settings
        self._ollama_model = QLineEdit()
        self._ollama_model.setPlaceholderText("llava:13b")
        vision_layout.addRow("Ollama Model:", self._ollama_model)

        self._ollama_url = QLineEdit()
        self._ollama_url.setPlaceholderText("http://localhost:11434")
        vision_layout.addRow("Ollama URL:", self._ollama_url)

        # Claude settings
        self._claude_key = QLineEdit()
        self._claude_key.setPlaceholderText("sk-ant-...")
        self._claude_key.setEchoMode(QLineEdit.EchoMode.Password)
        vision_layout.addRow("Claude API Key:", self._claude_key)

        self._claude_model = QLineEdit()
        self._claude_model.setPlaceholderText("claude-3-5-sonnet-20241022")
        vision_layout.addRow("Claude Model:", self._claude_model)

        layout.addWidget(vision_group)

        # ── Recording Settings ──
        recording_group = QGroupBox("Recording")
        recording_layout = QFormLayout(recording_group)

        self._screenshot_interval = QSpinBox()
        self._screenshot_interval.setRange(100, 5000)
        self._screenshot_interval.setSuffix(" ms")
        self._screenshot_interval.setSingleStep(100)
        recording_layout.addRow("Screenshot Interval:", self._screenshot_interval)

        self._capture_on_click = QCheckBox("Capture screenshot on every click")
        recording_layout.addRow("", self._capture_on_click)

        self._max_screenshots = QSpinBox()
        self._max_screenshots.setRange(100, 10000)
        self._max_screenshots.setSingleStep(100)
        recording_layout.addRow("Max Screenshots:", self._max_screenshots)

        layout.addWidget(recording_group)

        # ── Replay Settings ──
        replay_group = QGroupBox("Replay")
        replay_layout = QFormLayout(replay_group)

        self._action_delay = QSpinBox()
        self._action_delay.setRange(0, 5000)
        self._action_delay.setSuffix(" ms")
        self._action_delay.setSingleStep(100)
        replay_layout.addRow("Action Delay:", self._action_delay)

        self._find_timeout = QSpinBox()
        self._find_timeout.setRange(1000, 30000)
        self._find_timeout.setSuffix(" ms")
        self._find_timeout.setSingleStep(1000)
        replay_layout.addRow("Find Timeout:", self._find_timeout)

        self._confidence = QDoubleSpinBox()
        self._confidence.setRange(0.1, 1.0)
        self._confidence.setSingleStep(0.05)
        self._confidence.setDecimals(2)
        replay_layout.addRow("Confidence Threshold:", self._confidence)

        layout.addWidget(replay_group)

        # ── Storage Settings ──
        storage_group = QGroupBox("Storage")
        storage_layout = QFormLayout(storage_group)

        self._recordings_dir = QLineEdit()
        storage_layout.addRow("Recordings Dir:", self._recordings_dir)

        self._workflows_dir = QLineEdit()
        storage_layout.addRow("Workflows Dir:", self._workflows_dir)

        layout.addWidget(storage_group)

        # ── Dialog Buttons ──
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_config(self):
        """Populate fields from config."""
        v = self._config.vision
        self._provider_combo.setCurrentText(v.provider)
        self._ollama_model.setText(v.ollama_model)
        self._ollama_url.setText(v.ollama_base_url)
        self._claude_key.setText(v.claude_api_key or "")
        self._claude_model.setText(v.claude_model)

        r = self._config.recording
        self._screenshot_interval.setValue(r.screenshot_interval_ms)
        self._capture_on_click.setChecked(r.capture_on_click)
        self._max_screenshots.setValue(r.max_screenshots)

        rp = self._config.replay
        self._action_delay.setValue(rp.action_delay_ms)
        self._find_timeout.setValue(rp.element_find_timeout_ms)
        self._confidence.setValue(rp.confidence_threshold)

        s = self._config.storage
        self._recordings_dir.setText(s.recordings_dir)
        self._workflows_dir.setText(s.workflows_dir)

        self._on_provider_changed(v.provider)

    def _on_provider_changed(self, provider: str):
        """Toggle visibility of provider-specific fields."""
        is_ollama = provider == "ollama"
        self._ollama_model.setEnabled(is_ollama)
        self._ollama_url.setEnabled(is_ollama)
        self._claude_key.setEnabled(not is_ollama)
        self._claude_model.setEnabled(not is_ollama)

    def _save_and_accept(self):
        """Save settings to config and close."""
        self._config.vision.provider = self._provider_combo.currentText()
        self._config.vision.ollama_model = self._ollama_model.text()
        self._config.vision.ollama_base_url = self._ollama_url.text()
        self._config.vision.claude_api_key = self._claude_key.text() or None
        self._config.vision.claude_model = self._claude_model.text()

        self._config.recording.screenshot_interval_ms = self._screenshot_interval.value()
        self._config.recording.capture_on_click = self._capture_on_click.isChecked()
        self._config.recording.max_screenshots = self._max_screenshots.value()

        self._config.replay.action_delay_ms = self._action_delay.value()
        self._config.replay.element_find_timeout_ms = self._find_timeout.value()
        self._config.replay.confidence_threshold = self._confidence.value()

        self._config.storage.recordings_dir = self._recordings_dir.text()
        self._config.storage.workflows_dir = self._workflows_dir.text()

        self.accept()

    def get_config(self) -> AppConfig:
        """Return the (possibly modified) config."""
        return self._config
