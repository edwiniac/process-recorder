# ProcessRecorder - Development Roadmap

## Version: 0.1.0 (MVP)
## Last Updated: 2026-01-29

---

## 🎯 MVP Goal

A working prototype that can:
1. Record a simple desktop task (Notepad/Browser)
2. Process it into semantic steps using LLaVA
3. Replay the workflow reliably

---

## 📅 Sprint Plan

### Sprint 0: Foundation (Day 1) ✅ CURRENT
**Goal:** Project structure, docs, dev environment

- [x] Create project structure
- [x] Write requirements document
- [x] Write architecture document  
- [x] Write test plan
- [x] Write roadmap (this doc)
- [ ] Setup Python environment
- [ ] Install dependencies
- [ ] Verify Ollama + LLaVA working
- [ ] Create initial test harness

**Deliverable:** Ready-to-code environment

---

### Sprint 1: Recording Module (Days 2-4)
**Goal:** Capture screenshots and events reliably

#### Tasks:
1. **Screen Capturer**
   - [ ] Implement `ScreenCapturer` class
   - [ ] Test single screenshot capture
   - [ ] Test rapid capture (10 fps)
   - [ ] Test region capture
   - [ ] Evidence: Screenshots of captured screens

2. **Event Listener**
   - [ ] Implement `EventListener` class
   - [ ] Capture mouse clicks with coordinates
   - [ ] Capture keyboard input
   - [ ] Synchronize events with screenshots
   - [ ] Evidence: JSON log of captured events

3. **Recording Session**
   - [ ] Implement `RecordingSession` class
   - [ ] Start/stop recording
   - [ ] Save to structured format
   - [ ] Evidence: Complete recording folder

**Tests:**
- `test_screen_capturer.py`
- `test_event_listener.py`
- `test_recording_session.py`

**Deliverable:** Can record any desktop task with full data

---

### Sprint 2: Vision Integration (Days 5-7)
**Goal:** Analyze screenshots and extract semantic meaning

#### Tasks:
1. **Vision Adapter Interface**
   - [ ] Define `VisionAdapter` ABC
   - [ ] Implement `OllamaAdapter`
   - [ ] Implement `ClaudeAdapter`
   - [ ] Factory for switching

2. **Screenshot Analysis**
   - [ ] Prompt engineering for UI analysis
   - [ ] Extract clicked element descriptions
   - [ ] Identify UI context (app name, window)
   - [ ] Evidence: Analysis output samples

3. **Semantic Step Generator**
   - [ ] Convert raw events → semantic steps
   - [ ] Handle click, type, scroll actions
   - [ ] Generate workflow description
   - [ ] Evidence: Generated workflow JSON

**Tests:**
- `test_vision_adapter.py`
- `test_semantic_extractor.py`
- `test_workflow_processor.py`

**Deliverable:** Recordings converted to semantic workflows

---

### Sprint 3: Replay Engine (Days 8-10)
**Goal:** Execute workflows by finding and clicking elements

#### Tasks:
1. **Element Finder**
   - [ ] Use vision to locate UI elements
   - [ ] Return coordinates with confidence
   - [ ] Handle element-not-found
   - [ ] Evidence: Screenshots with found element marked

2. **Action Executor**
   - [ ] Execute mouse clicks
   - [ ] Execute keyboard input
   - [ ] Configurable delays
   - [ ] Evidence: Video of actions executing

3. **Replay Engine**
   - [ ] Load workflow
   - [ ] Execute steps sequentially
   - [ ] Error handling and recovery
   - [ ] Evidence: Full replay video

**Tests:**
- `test_element_finder.py`
- `test_action_executor.py`
- `test_replay_engine.py`

**Deliverable:** Workflows replay successfully

---

### Sprint 4: GUI (Days 11-13)
**Goal:** User-friendly interface

#### Tasks:
1. **Main Window**
   - [ ] Record/Stop button
   - [ ] Workflow list panel
   - [ ] Status bar
   - [ ] Evidence: Screenshot of UI

2. **Settings Dialog**
   - [ ] Vision provider selection
   - [ ] API key input
   - [ ] Save/load config
   - [ ] Evidence: Settings screenshot

3. **Replay Controls**
   - [ ] Start replay button
   - [ ] Progress indicator
   - [ ] Stop/pause (if time)
   - [ ] Evidence: Replay in action

**Tests:**
- `test_gui_components.py`
- Manual GUI testing with screenshots

**Deliverable:** Working GUI application

---

### Sprint 5: Integration & Polish (Days 14-15)
**Goal:** End-to-end testing, bug fixes, documentation

#### Tasks:
1. **E2E Testing**
   - [ ] E2E-01: Notepad Hello World
   - [ ] E2E-02: Browser Navigation
   - [ ] E2E-03: Replay Notepad
   - [ ] E2E-04: Offline Mode
   - [ ] Evidence: Videos for all tests

2. **Bug Fixes**
   - [ ] Address issues found in E2E
   - [ ] Performance optimization
   - [ ] Error message improvements

3. **Documentation**
   - [ ] User guide
   - [ ] Installation instructions
   - [ ] Known limitations

**Deliverable:** MVP ready for demo

---

## 📊 Progress Tracking

| Sprint | Status | Completion | Notes |
|--------|--------|------------|-------|
| Sprint 0 | ✅ Complete | 100% | Foundation & docs |
| Sprint 1 | ✅ Complete | 100% | 50 tests passing |
| Sprint 2 | ✅ Complete | 100% | 88 new tests (138 total) |
| Sprint 3 | ✅ Complete | 100% | 68 new tests (220 total) |
| Sprint 4 | ✅ Complete | 100% | 39 new tests (259 total) |
| Sprint 5 | ⚪ Not Started | 0% | |

---

## 🚨 Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLaVA accuracy too low | High | Fall back to Claude API |
| Element finding unreliable | High | Allow user to correct/retry |
| Windows permission issues | Medium | Document required permissions |
| Ollama not installed | Medium | Clear setup instructions |

---

## 📈 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Recording accuracy | 100% | All events captured |
| Learning accuracy | >80% | Semantic steps match actions |
| Replay success rate | >70% | Workflows complete without error |
| User satisfaction | Usable | Can record & replay Notepad task |

---

## 🔄 Self-Correction Protocol

After each sprint:
1. Run all tests
2. Review failures
3. Document learnings in `docs/LEARNINGS.md`
4. Adjust next sprint if needed
5. Update this roadmap
