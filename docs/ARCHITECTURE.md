# ProcessRecorder - Architecture Document

## Version: 0.1.0
## Last Updated: 2026-01-29

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                          GUI Layer                           │
│                    (PyQt6 / tkinter)                        │
├─────────────────────────────────────────────────────────────┤
│                     Controller Layer                         │
│              (Orchestrates all operations)                   │
├──────────────┬──────────────┬──────────────┬────────────────┤
│   Recorder   │   Learner    │   Replayer   │    Storage     │
│   Module     │   Module     │   Module     │    Module      │
├──────────────┴──────────────┴──────────────┴────────────────┤
│                      Vision Adapter                          │
│           (Ollama/LLaVA ↔ Claude API abstraction)           │
├─────────────────────────────────────────────────────────────┤
│                    Platform Layer                            │
│         (Screen capture, mouse/keyboard, OS utils)          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Module Descriptions

### 2.1 GUI Layer (`src/gui/`)

**Responsibility:** User interface and interaction

**Components:**
- `main_window.py` - Main application window
- `recording_panel.py` - Record/Stop controls
- `workflow_list.py` - List and manage saved workflows
- `settings_dialog.py` - Configuration UI
- `replay_overlay.py` - Visual feedback during replay

### 2.2 Controller Layer (`src/controller/`)

**Responsibility:** Business logic and orchestration

**Components:**
- `app_controller.py` - Main application controller
- `recording_session.py` - Manages active recording
- `replay_session.py` - Manages active replay

### 2.3 Recorder Module (`src/recorder/`)

**Responsibility:** Capture user actions

**Components:**
- `screen_capturer.py` - Screenshot capture (using mss)
- `event_listener.py` - Mouse/keyboard event capture (pynput)
- `recording_data.py` - Data structures for raw recordings

**Data Flow:**
```
User Action → Event Listener → Recording Session
                    ↓
            Screen Capturer → Screenshot Buffer
                    ↓
            Synchronized Recording Data
```

### 2.4 Learner Module (`src/learner/`)

**Responsibility:** Convert raw data to semantic workflows

**Components:**
- `workflow_processor.py` - Orchestrates learning pipeline
- `action_classifier.py` - Classifies action types
- `semantic_extractor.py` - Extracts semantic meaning from screenshots

**Data Flow:**
```
Raw Recording → Screenshot Analysis → Action Classification
                      ↓
              Semantic Step Generation
                      ↓
              Workflow Object
```

### 2.5 Replayer Module (`src/replayer/`)

**Responsibility:** Execute saved workflows

**Components:**
- `element_finder.py` - Locate UI elements using vision
- `action_executor.py` - Execute mouse/keyboard actions
- `replay_engine.py` - Orchestrates replay flow

**Data Flow:**
```
Workflow → For Each Step:
              → Find Element (Vision)
              → Verify Found
              → Execute Action
              → Capture Result
              → Next Step
```

### 2.6 Vision Adapter (`src/vision/`)

**Responsibility:** Abstract vision model differences

**Components:**
- `vision_adapter.py` - Interface definition
- `ollama_adapter.py` - Ollama/LLaVA implementation
- `claude_adapter.py` - Claude API implementation
- `vision_factory.py` - Factory for creating adapters

**Interface:**
```python
class VisionAdapter(ABC):
    @abstractmethod
    def analyze_screenshot(self, image: bytes, prompt: str) -> str:
        """Analyze a screenshot and return description."""
        pass
    
    @abstractmethod
    def find_element(self, image: bytes, element_desc: str) -> tuple[int, int] | None:
        """Find element in screenshot, return coordinates or None."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the model is available."""
        pass
```

### 2.7 Storage Module (`src/storage/`)

**Responsibility:** Persist recordings and workflows

**Components:**
- `recording_store.py` - Save/load raw recordings
- `workflow_store.py` - Save/load processed workflows
- `config_store.py` - Application configuration

**Storage Format:**
```
recordings/
  {recording_id}/
    metadata.json       # Recording metadata
    events.jsonl        # Mouse/keyboard events
    screenshots/        # PNG screenshots
      0001.png
      0002.png

workflows/
  {workflow_name}.json  # Processed workflow
```

---

## 3. Data Structures

### 3.1 RawEvent
```python
@dataclass
class RawEvent:
    timestamp: float
    event_type: str  # "click", "key", "scroll"
    data: dict       # Event-specific data
    screenshot_id: str | None
```

### 3.2 SemanticStep
```python
@dataclass
class SemanticStep:
    step_id: int
    action_type: str      # "click", "type", "scroll", "wait"
    target_description: str  # "the 'Compose' button"
    target_screenshot: str   # Reference screenshot path
    target_region: tuple     # (x, y, w, h) bounding box
    input_data: str | None   # For typing actions
    confidence: float        # Model confidence
```

### 3.3 Workflow
```python
@dataclass
class Workflow:
    name: str
    description: str
    created_at: datetime
    steps: list[SemanticStep]
    source_recording_id: str
    model_used: str
```

---

## 4. Configuration

**File:** `config.yaml`

```yaml
vision:
  provider: "ollama"  # or "claude"
  ollama:
    model: "llava:13b"
    base_url: "http://localhost:11434"
  claude:
    api_key: "${ANTHROPIC_API_KEY}"  # From env or direct
    model: "claude-3-5-sonnet-20241022"

recording:
  screenshot_interval_ms: 500
  capture_on_click: true
  max_screenshots: 1000

replay:
  action_delay_ms: 500
  element_find_timeout_ms: 5000
  confidence_threshold: 0.7

storage:
  recordings_dir: "./recordings"
  workflows_dir: "./workflows"
```

---

## 5. Error Handling Strategy

| Error Type | Handling |
|------------|----------|
| Vision model unavailable | Fall back to basic coordinate replay, warn user |
| Element not found during replay | Pause, show last screenshot, ask user |
| Screenshot capture fails | Retry 3x, then fail recording |
| Recording storage full | Warn user, pause recording |

---

## 6. Testing Strategy

### Unit Tests
- Each module tested in isolation
- Mock dependencies (especially vision model)

### Integration Tests  
- Recorder → Storage → Learner flow
- Full replay cycle with mocked screen

### End-to-End Tests
- Record actual task → Process → Replay
- Capture video proof

### Test Evidence
- Screenshots at each test step
- Video recording of E2E tests
- JSON test reports
