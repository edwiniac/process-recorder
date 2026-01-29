# ProcessRecorder - Test Plan

## Version: 0.1.0
## Last Updated: 2026-01-29

---

## 1. Testing Philosophy

**Every feature must have:**
1. Unit tests (automated)
2. Integration tests (automated)
3. Visual proof (screenshots/video)
4. Documented test results

**Self-Correction Loop:**
```
Write Test → Run Test → FAIL? → Fix Code → Re-run → PASS? → Document Proof
                ↓                              ↓
            Document Failure              Next Test
```

---

## 2. Test Categories

### 2.1 Unit Tests (`tests/unit/`)

| Module | Test File | Coverage Target |
|--------|-----------|-----------------|
| Screen Capturer | `test_screen_capturer.py` | 90% |
| Event Listener | `test_event_listener.py` | 85% |
| Recording Data | `test_recording_data.py` | 95% |
| Vision Adapter | `test_vision_adapter.py` | 80% |
| Workflow Processor | `test_workflow_processor.py` | 85% |
| Storage | `test_storage.py` | 90% |

### 2.2 Integration Tests (`tests/integration/`)

| Test | Description |
|------|-------------|
| `test_recording_flow.py` | Record → Store → Retrieve |
| `test_learning_flow.py` | Recording → Vision → Workflow |
| `test_replay_flow.py` | Workflow → Find → Execute |
| `test_config_switch.py` | Switch vision provider |

### 2.3 End-to-End Tests (`tests/e2e/`)

| Test ID | Scenario | Steps | Evidence |
|---------|----------|-------|----------|
| E2E-01 | Notepad Hello World | Record: Open Notepad, type "Hello", save | Video |
| E2E-02 | Browser Navigation | Record: Open Chrome, go to google.com | Video |
| E2E-03 | Replay Notepad | Replay E2E-01 workflow | Video |
| E2E-04 | Offline Mode | All of above with Ollama only | Video |

---

## 3. Test Evidence Requirements

### 3.1 Screenshot Evidence

For each test phase, capture:
- **Before:** Initial state
- **During:** Action being performed
- **After:** Result state

Storage: `tests/evidence/{test_id}/{timestamp}/`

### 3.2 Video Evidence

For E2E tests:
- Use OBS or ffmpeg to record screen
- Store as MP4 in `tests/evidence/videos/`
- Max 2 minutes per test
- Include test ID in filename

### 3.3 Test Report Format

```json
{
  "test_id": "E2E-01",
  "name": "Notepad Hello World",
  "timestamp": "2026-01-29T14:30:00Z",
  "status": "PASS|FAIL",
  "duration_ms": 5000,
  "steps": [
    {
      "step": 1,
      "action": "Start recording",
      "result": "Recording started",
      "screenshot": "step_01.png"
    }
  ],
  "evidence": {
    "video": "E2E-01_2026-01-29.mp4",
    "screenshots": ["step_01.png", "step_02.png"]
  },
  "errors": [],
  "notes": ""
}
```

---

## 4. Test Execution Plan

### Phase 1: Core Module Tests (Sprint 1)

```
Day 1-2: Screen Capturer
  - [ ] test_capture_single_screenshot
  - [ ] test_capture_multiple_rapid
  - [ ] test_capture_region
  - [ ] test_capture_error_handling

Day 3-4: Event Listener
  - [ ] test_mouse_click_capture
  - [ ] test_keyboard_capture
  - [ ] test_event_timing
  - [ ] test_listener_start_stop

Day 5: Storage
  - [ ] test_save_recording
  - [ ] test_load_recording
  - [ ] test_save_workflow
  - [ ] test_config_persistence
```

### Phase 2: Integration Tests (Sprint 2)

```
Day 1-2: Recording Integration
  - [ ] test_full_recording_session
  - [ ] test_recording_with_screenshots
  - [ ] test_recording_recovery

Day 3-4: Vision Integration
  - [ ] test_ollama_connection
  - [ ] test_screenshot_analysis
  - [ ] test_element_finding
  - [ ] test_api_fallback

Day 5: Replay Integration
  - [ ] test_workflow_load_execute
  - [ ] test_element_not_found_handling
```

### Phase 3: E2E Tests (Sprint 3)

```
Day 1: E2E-01 Notepad Test
Day 2: E2E-02 Browser Test  
Day 3: E2E-03 Replay Test
Day 4: E2E-04 Offline Test
Day 5: Bug fixes from E2E findings
```

---

## 5. Automated Test Runner

**Command:** `pytest tests/ -v --html=reports/test_report.html`

**CI Checks:**
- All unit tests must pass
- Integration tests must pass
- Coverage >= 80%

**Evidence Collection Script:**
```bash
#!/bin/bash
# tests/collect_evidence.sh

TEST_ID=$1
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
EVIDENCE_DIR="tests/evidence/${TEST_ID}/${TIMESTAMP}"

mkdir -p "$EVIDENCE_DIR"

# Start screen recording
ffmpeg -f gdigrab -i desktop -t 120 "${EVIDENCE_DIR}/recording.mp4" &
FFMPEG_PID=$!

# Run the test
pytest "tests/e2e/test_${TEST_ID}.py" -v --json-report --json-report-file="${EVIDENCE_DIR}/report.json"

# Stop recording
kill $FFMPEG_PID

echo "Evidence saved to $EVIDENCE_DIR"
```

---

## 6. Bug Tracking

| Bug ID | Test | Description | Status | Fix |
|--------|------|-------------|--------|-----|
| (Template) | | | | |

---

## 7. Sign-Off Criteria

**MVP Release Checklist:**
- [ ] All P0 requirements tested
- [ ] All unit tests passing (>80% coverage)
- [ ] All integration tests passing
- [ ] E2E-01 through E2E-04 passing with video proof
- [ ] No critical bugs open
- [ ] Test report generated and reviewed
