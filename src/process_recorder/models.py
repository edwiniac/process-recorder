"""
Data models for ProcessRecorder.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class EventType(str, Enum):
    """Types of recorded events."""
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    KEY_PRESS = "key_press"
    KEY_RELEASE = "key_release"
    KEY_TYPE = "key_type"  # Full text typed
    SCROLL = "scroll"
    DRAG = "drag"


class ActionType(str, Enum):
    """Types of semantic actions."""
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    WAIT = "wait"
    DRAG = "drag"
    HOTKEY = "hotkey"


class MouseButton(str, Enum):
    """Mouse button types."""
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


@dataclass
class RawEvent:
    """A single recorded event (mouse/keyboard)."""
    timestamp: float  # Unix timestamp
    event_type: EventType
    data: dict  # Event-specific data
    screenshot_id: Optional[str] = None  # Associated screenshot
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "data": self.data,
            "screenshot_id": self.screenshot_id,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "RawEvent":
        return cls(
            timestamp=d["timestamp"],
            event_type=EventType(d["event_type"]),
            data=d["data"],
            screenshot_id=d.get("screenshot_id"),
        )


@dataclass
class Screenshot:
    """A captured screenshot."""
    screenshot_id: str  # Unique ID
    timestamp: float  # Unix timestamp
    filepath: str  # Path to image file
    width: int
    height: int
    
    def to_dict(self) -> dict:
        return {
            "screenshot_id": self.screenshot_id,
            "timestamp": self.timestamp,
            "filepath": self.filepath,
            "width": self.width,
            "height": self.height,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "Screenshot":
        return cls(**d)


@dataclass
class Recording:
    """A complete recording session."""
    recording_id: str
    name: str
    created_at: datetime
    events: list[RawEvent] = field(default_factory=list)
    screenshots: list[Screenshot] = field(default_factory=list)
    duration_ms: int = 0
    
    def to_dict(self) -> dict:
        return {
            "recording_id": self.recording_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "events": [e.to_dict() for e in self.events],
            "screenshots": [s.to_dict() for s in self.screenshots],
            "duration_ms": self.duration_ms,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "Recording":
        return cls(
            recording_id=d["recording_id"],
            name=d["name"],
            created_at=datetime.fromisoformat(d["created_at"]),
            events=[RawEvent.from_dict(e) for e in d["events"]],
            screenshots=[Screenshot.from_dict(s) for s in d["screenshots"]],
            duration_ms=d.get("duration_ms", 0),
        )


@dataclass
class BoundingBox:
    """A bounding box for UI elements."""
    x: int
    y: int
    width: int
    height: int
    
    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)
    
    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}
    
    @classmethod
    def from_dict(cls, d: dict) -> "BoundingBox":
        return cls(**d)


@dataclass
class SemanticStep:
    """A semantic step in a workflow."""
    step_id: int
    action_type: ActionType
    target_description: str  # Human-readable: "the 'Compose' button"
    target_screenshot_id: str  # Reference screenshot
    target_region: Optional[BoundingBox] = None  # Where in the screenshot
    input_data: Optional[str] = None  # For typing actions
    confidence: float = 0.0  # Model confidence (0-1)
    raw_event_ids: list[int] = field(default_factory=list)  # Source events
    
    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "action_type": self.action_type.value,
            "target_description": self.target_description,
            "target_screenshot_id": self.target_screenshot_id,
            "target_region": self.target_region.to_dict() if self.target_region else None,
            "input_data": self.input_data,
            "confidence": self.confidence,
            "raw_event_ids": self.raw_event_ids,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "SemanticStep":
        return cls(
            step_id=d["step_id"],
            action_type=ActionType(d["action_type"]),
            target_description=d["target_description"],
            target_screenshot_id=d["target_screenshot_id"],
            target_region=BoundingBox.from_dict(d["target_region"]) if d.get("target_region") else None,
            input_data=d.get("input_data"),
            confidence=d.get("confidence", 0.0),
            raw_event_ids=d.get("raw_event_ids", []),
        )


@dataclass
class Workflow:
    """A learned workflow ready for replay."""
    workflow_id: str
    name: str
    description: str
    created_at: datetime
    steps: list[SemanticStep]
    source_recording_id: str
    model_used: str  # "ollama:llava" or "claude:sonnet"
    
    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "steps": [s.to_dict() for s in self.steps],
            "source_recording_id": self.source_recording_id,
            "model_used": self.model_used,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "Workflow":
        return cls(
            workflow_id=d["workflow_id"],
            name=d["name"],
            description=d["description"],
            created_at=datetime.fromisoformat(d["created_at"]),
            steps=[SemanticStep.from_dict(s) for s in d["steps"]],
            source_recording_id=d["source_recording_id"],
            model_used=d["model_used"],
        )


class AppConfig(BaseModel):
    """Application configuration."""
    
    class VisionConfig(BaseModel):
        provider: str = "ollama"  # "ollama" or "claude"
        ollama_model: str = "llava:13b"
        ollama_base_url: str = "http://localhost:11434"
        claude_api_key: Optional[str] = None
        claude_model: str = "claude-3-5-sonnet-20241022"
    
    class RecordingConfig(BaseModel):
        screenshot_interval_ms: int = 500
        capture_on_click: bool = True
        max_screenshots: int = 1000
    
    class ReplayConfig(BaseModel):
        action_delay_ms: int = 500
        element_find_timeout_ms: int = 5000
        confidence_threshold: float = 0.7
    
    class StorageConfig(BaseModel):
        recordings_dir: str = "./recordings"
        workflows_dir: str = "./workflows"
    
    vision: VisionConfig = VisionConfig()
    recording: RecordingConfig = RecordingConfig()
    replay: ReplayConfig = ReplayConfig()
    storage: StorageConfig = StorageConfig()
