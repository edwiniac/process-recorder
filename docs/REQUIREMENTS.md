# ProcessRecorder - Requirements Document

## Version: 0.1.0 (MVP)
## Last Updated: 2026-01-29

---

## 1. Overview

ProcessRecorder is a "Watch Me, Learn, Repeat" desktop automation tool that:
- Records user actions (screenshots + mouse/keyboard events)
- Uses AI vision to understand actions semantically
- Replays workflows on demand

---

## 2. Functional Requirements

### 2.1 Recording (FR-REC)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-REC-01 | Capture screenshots at configurable intervals (default: 500ms) | P0 |
| FR-REC-02 | Capture screenshots on mouse click events | P0 |
| FR-REC-03 | Log mouse click events with coordinates and timestamp | P0 |
| FR-REC-04 | Log keyboard input with timestamp | P0 |
| FR-REC-05 | Start/stop recording via GUI button | P0 |
| FR-REC-06 | Start/stop recording via hotkey (Ctrl+Shift+R) | P1 |
| FR-REC-07 | Visual indicator when recording is active | P0 |
| FR-REC-08 | Save raw recording data to structured format | P0 |

### 2.2 Learning/Processing (FR-LRN)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-LRN-01 | Send screenshots to vision model for analysis | P0 |
| FR-LRN-02 | Support offline model (LLaVA via Ollama) | P0 |
| FR-LRN-03 | Support API model (Claude/GPT-4V) via config | P1 |
| FR-LRN-04 | Convert raw coordinates to semantic actions | P0 |
| FR-LRN-05 | Generate human-readable workflow description | P0 |
| FR-LRN-06 | Allow user to edit/correct learned steps | P1 |
| FR-LRN-07 | Save workflow with user-provided name | P0 |

### 2.3 Replay (FR-RPL)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-RPL-01 | Load saved workflow by name | P0 |
| FR-RPL-02 | Use vision to locate UI elements before clicking | P0 |
| FR-RPL-03 | Execute mouse clicks at located positions | P0 |
| FR-RPL-04 | Execute keyboard input | P0 |
| FR-RPL-05 | Handle element-not-found gracefully | P0 |
| FR-RPL-06 | Pause/resume/stop replay via GUI | P1 |
| FR-RPL-07 | Adjustable replay speed | P2 |

### 2.4 User Interface (FR-GUI)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-GUI-01 | Main window with Record/Stop/Replay buttons | P0 |
| FR-GUI-02 | List of saved workflows | P0 |
| FR-GUI-03 | Workflow preview (show steps) | P1 |
| FR-GUI-04 | Settings panel (model selection, API key) | P0 |
| FR-GUI-05 | Status bar with current state | P0 |
| FR-GUI-06 | System tray icon when minimized | P2 |

---

## 3. Non-Functional Requirements

### 3.1 Performance (NFR-PERF)

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-PERF-01 | Screenshot capture latency | < 100ms |
| NFR-PERF-02 | Recording overhead (CPU) | < 10% |
| NFR-PERF-03 | Replay action execution | < 500ms per step |

### 3.2 Compatibility (NFR-COMP)

| ID | Requirement |
|----|-------------|
| NFR-COMP-01 | Windows 10/11 support |
| NFR-COMP-02 | Python 3.10+ |
| NFR-COMP-03 | Works with Ollama for local inference |

### 3.3 Reliability (NFR-REL)

| ID | Requirement |
|----|-------------|
| NFR-REL-01 | Graceful handling of vision model failures |
| NFR-REL-02 | Recording data saved incrementally (crash recovery) |
| NFR-REL-03 | Replay failure should not corrupt workflow |

---

## 4. Constraints

- MVP targets Windows only (cross-platform later)
- Offline-first (Ollama + LLaVA), API optional
- GUI built with PyQt6 or tkinter
- All recordings stored locally

---

## 5. Acceptance Criteria

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| AC-01 | Record opening Notepad and typing "Hello" | Workflow captured with semantic steps |
| AC-02 | Replay AC-01 workflow | Notepad opens, "Hello" is typed |
| AC-03 | Change API key in settings | Model switches, subsequent recordings use new model |
| AC-04 | Record with Ollama offline | Works without internet |
| AC-05 | Replay fails to find element | User notified, workflow paused |

---

## 6. Out of Scope (v0.1)

- macOS/Linux support
- Cloud sync of workflows
- Sharing workflows with others
- Voice commands
- Multi-monitor support (complex)
