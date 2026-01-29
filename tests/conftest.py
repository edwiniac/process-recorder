"""
Pytest configuration and shared fixtures.
"""

import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from process_recorder.models import (
    RawEvent, EventType, Screenshot, Recording,
    SemanticStep, ActionType, BoundingBox, Workflow,
    AppConfig
)


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config():
    """Provide a sample configuration."""
    return AppConfig(
        vision=AppConfig.VisionConfig(provider="ollama"),
        recording=AppConfig.RecordingConfig(screenshot_interval_ms=100),
        storage=AppConfig.StorageConfig(
            recordings_dir="./test_recordings",
            workflows_dir="./test_workflows"
        )
    )


@pytest.fixture
def sample_events():
    """Provide sample events for testing."""
    return [
        RawEvent(
            timestamp=1.0,
            event_type=EventType.CLICK,
            data={"x": 100, "y": 200, "button": "left"},
            screenshot_id="0001"
        ),
        RawEvent(
            timestamp=1.5,
            event_type=EventType.KEY_TYPE,
            data={"text": "hello"},
            screenshot_id="0002"
        ),
        RawEvent(
            timestamp=2.0,
            event_type=EventType.CLICK,
            data={"x": 300, "y": 400, "button": "left"},
            screenshot_id="0003"
        ),
    ]


@pytest.fixture
def sample_screenshots():
    """Provide sample screenshot records for testing."""
    return [
        Screenshot(
            screenshot_id="0001",
            timestamp=1.0,
            filepath="/test/screenshots/0001.png",
            width=1920,
            height=1080
        ),
        Screenshot(
            screenshot_id="0002",
            timestamp=1.5,
            filepath="/test/screenshots/0002.png",
            width=1920,
            height=1080
        ),
        Screenshot(
            screenshot_id="0003",
            timestamp=2.0,
            filepath="/test/screenshots/0003.png",
            width=1920,
            height=1080
        ),
    ]


@pytest.fixture
def sample_recording(sample_events, sample_screenshots):
    """Provide a sample recording for testing."""
    return Recording(
        recording_id="test_rec_001",
        name="Test Recording",
        created_at=datetime.now(),
        events=sample_events,
        screenshots=sample_screenshots,
        duration_ms=2000
    )


@pytest.fixture
def sample_steps():
    """Provide sample semantic steps for testing."""
    return [
        SemanticStep(
            step_id=1,
            action_type=ActionType.CLICK,
            target_description="the 'Start' button in the taskbar",
            target_screenshot_id="0001",
            target_region=BoundingBox(x=0, y=1050, width=50, height=30),
            confidence=0.92
        ),
        SemanticStep(
            step_id=2,
            action_type=ActionType.TYPE,
            target_description="the search box in Start menu",
            target_screenshot_id="0002",
            input_data="notepad",
            confidence=0.88
        ),
        SemanticStep(
            step_id=3,
            action_type=ActionType.CLICK,
            target_description="the 'Notepad' app result",
            target_screenshot_id="0003",
            target_region=BoundingBox(x=100, y=200, width=200, height=40),
            confidence=0.85
        ),
    ]


@pytest.fixture
def sample_workflow(sample_steps):
    """Provide a sample workflow for testing."""
    return Workflow(
        workflow_id="test_wf_001",
        name="Open Notepad",
        description="Opens Notepad via Start menu search",
        created_at=datetime.now(),
        steps=sample_steps,
        source_recording_id="test_rec_001",
        model_used="ollama:llava:13b"
    )


# Test evidence helpers

class TestEvidence:
    """Helper class for collecting test evidence."""
    
    def __init__(self, test_id: str, evidence_dir: Path):
        self.test_id = test_id
        self.evidence_dir = evidence_dir / test_id
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.steps = []
    
    def log_step(self, step_num: int, action: str, result: str, screenshot_path: str = None):
        """Log a test step."""
        step = {
            "step": step_num,
            "action": action,
            "result": result,
            "screenshot": screenshot_path
        }
        self.steps.append(step)
    
    def save_screenshot(self, name: str, image_bytes: bytes) -> str:
        """Save a screenshot and return path."""
        path = self.evidence_dir / f"{name}.png"
        with open(path, "wb") as f:
            f.write(image_bytes)
        return str(path)
    
    def get_report(self) -> dict:
        """Get the evidence report."""
        return {
            "test_id": self.test_id,
            "steps": self.steps,
            "evidence_dir": str(self.evidence_dir)
        }


@pytest.fixture
def evidence(temp_dir, request):
    """Provide evidence collection for a test."""
    test_name = request.node.name
    return TestEvidence(test_name, temp_dir / "evidence")
