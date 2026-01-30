"""
Workflow list panel — displays saved workflows and recordings.

Features:
- List of saved workflows with metadata
- Select to view details
- Delete workflows
- Load for replay
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import Workflow


class WorkflowListPanel(QWidget):
    """Panel displaying saved workflows."""

    workflow_selected = pyqtSignal(object)  # Workflow
    replay_requested = pyqtSignal(object)  # Workflow
    delete_requested = pyqtSignal(str)  # workflow_id

    def __init__(self, workflows_dir: str = "./workflows", parent=None):
        super().__init__(parent)
        self._workflows_dir = Path(workflows_dir)
        self._workflows: dict[str, Workflow] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header row
        header_row = QHBoxLayout()
        header = QLabel("📋 Workflows")
        header.setObjectName("heading")
        header_row.addWidget(header)
        header_row.addStretch()

        self._refresh_btn = QPushButton("↻ Refresh")
        self._refresh_btn.setObjectName("secondaryBtn")
        self._refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(self._refresh_btn)

        layout.addLayout(header_row)

        # Workflow list
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list)

        # Details area
        self._details_frame = QFrame()
        self._details_frame.setStyleSheet(
            "QFrame { background-color: #282840; border-radius: 8px; padding: 12px; }"
        )
        details_layout = QVBoxLayout(self._details_frame)
        details_layout.setSpacing(4)

        self._detail_name = QLabel("Select a workflow")
        self._detail_name.setObjectName("heading")
        self._detail_name.setWordWrap(True)

        self._detail_desc = QLabel("")
        self._detail_desc.setObjectName("subheading")
        self._detail_desc.setWordWrap(True)

        self._detail_meta = QLabel("")
        self._detail_meta.setObjectName("statusLabel")

        details_layout.addWidget(self._detail_name)
        details_layout.addWidget(self._detail_desc)
        details_layout.addWidget(self._detail_meta)
        layout.addWidget(self._details_frame)

        # Action buttons
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self._replay_btn = QPushButton("▶  Replay")
        self._replay_btn.setEnabled(False)
        self._replay_btn.clicked.connect(self._on_replay)

        self._delete_btn = QPushButton("🗑  Delete")
        self._delete_btn.setObjectName("dangerBtn")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete)

        action_row.addWidget(self._replay_btn)
        action_row.addWidget(self._delete_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

    def refresh(self):
        """Reload workflows from disk."""
        self._list.clear()
        self._workflows.clear()

        if not self._workflows_dir.exists():
            return

        for filepath in sorted(self._workflows_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(filepath.read_text())
                workflow = Workflow.from_dict(data)
                self._workflows[workflow.workflow_id] = workflow

                item = QListWidgetItem(
                    f"{workflow.name}  ({len(workflow.steps)} steps)"
                )
                item.setData(Qt.ItemDataRole.UserRole, workflow.workflow_id)
                self._list.addItem(item)
            except Exception as e:
                # Skip malformed files
                continue

    def _on_selection_changed(self, current, previous):
        if current is None:
            self._replay_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            self._detail_name.setText("Select a workflow")
            self._detail_desc.setText("")
            self._detail_meta.setText("")
            return

        wf_id = current.data(Qt.ItemDataRole.UserRole)
        workflow = self._workflows.get(wf_id)

        if workflow:
            self._detail_name.setText(workflow.name)
            self._detail_desc.setText(workflow.description[:200])
            self._detail_meta.setText(
                f"Steps: {len(workflow.steps)} · "
                f"Model: {workflow.model_used} · "
                f"Created: {workflow.created_at.strftime('%Y-%m-%d %H:%M')}"
            )
            self._replay_btn.setEnabled(True)
            self._delete_btn.setEnabled(True)
            self.workflow_selected.emit(workflow)

    def _on_replay(self):
        current = self._list.currentItem()
        if current:
            wf_id = current.data(Qt.ItemDataRole.UserRole)
            workflow = self._workflows.get(wf_id)
            if workflow:
                self.replay_requested.emit(workflow)

    def _on_delete(self):
        current = self._list.currentItem()
        if not current:
            return

        wf_id = current.data(Qt.ItemDataRole.UserRole)
        workflow = self._workflows.get(wf_id)
        if not workflow:
            return

        reply = QMessageBox.question(
            self,
            "Delete Workflow",
            f"Delete '{workflow.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Delete file
            filepath = self._workflows_dir / f"{wf_id}.json"
            if filepath.exists():
                filepath.unlink()
            self.delete_requested.emit(wf_id)
            self.refresh()

    def get_selected_workflow(self) -> Optional[Workflow]:
        current = self._list.currentItem()
        if current:
            wf_id = current.data(Qt.ItemDataRole.UserRole)
            return self._workflows.get(wf_id)
        return None
