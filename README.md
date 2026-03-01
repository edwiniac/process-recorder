# ProcessRecorder

[![CI](https://github.com/edwiniac/process-recorder/actions/workflows/ci.yml/badge.svg)](https://github.com/edwiniac/process-recorder/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-265%20passed-brightgreen.svg)](#-test-coverage)

**Watch Me, Learn, Repeat** — Desktop automation through demonstration.

Record a task once. AI understands what you did. Replay it anytime.

---

## ✨ Features

- **🎥 Record** — Captures mouse clicks, keyboard input, screenshots
- **🧠 Learn** — AI vision identifies UI elements and builds semantic workflows
- **▶️ Replay** — Finds elements on the live screen and repeats your actions
- **🎨 GUI** — Dark-themed PyQt6 interface with live stats and progress
- **🔄 Dual Vision** — Ollama/LLaVA (local, free) or Claude (API, high accuracy)
- **⚡ Error Recovery** — Stop, skip, or retry failed steps during replay

## 🏗 Architecture

```
┌─────────────────────────────────────┐
│           GUI (PyQt6)               │
├─────────────────────────────────────┤
│         App Controller              │
├──────────┬──────────┬───────────────┤
│ Recorder │ Learner  │   Replayer    │
├──────────┴──────────┴───────────────┤
│      Vision Adapter (ABC)           │
│    Ollama/LLaVA  ↔  Claude API     │
└─────────────────────────────────────┘
```

## 🚀 Quick Start

```bash
# Clone and setup
git clone https://github.com/edwiniac/process-recorder.git
cd process-recorder
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

# Optional: Install Ollama for local AI
ollama pull llava:13b

# Launch
process-recorder
```

## 📊 Test Coverage

```
265 tests passing | 5 modules | ~5,500 lines of code

Sprint 1: Recording Module     — 50 tests  ✅
Sprint 2: Vision Integration   — 88 tests  ✅
Sprint 3: Replay Engine        — 68 tests  ✅
Sprint 4: GUI Components       — 39 tests  ✅
Sprint 5: E2E Integration      —  7 tests  ✅
```

## 📁 Project Structure

```
src/process_recorder/
├── recorder/          # Screen capture + event listening
│   ├── screen_capturer.py
│   ├── event_listener.py
│   └── recording_session.py
├── vision/            # AI vision adapters
│   ├── base.py        # Abstract interface
│   ├── ollama_adapter.py
│   ├── claude_adapter.py
│   ├── factory.py     # Auto-detect + fallback
│   └── prompts.py     # Engineered prompts
├── learner/           # Recording → Workflow
│   ├── action_classifier.py
│   ├── semantic_extractor.py
│   └── workflow_processor.py
├── replayer/          # Workflow → Actions
│   ├── element_finder.py
│   ├── action_executor.py
│   └── replay_engine.py
├── gui/               # PyQt6 interface
│   ├── main_window.py
│   ├── recording_panel.py
│   ├── workflow_list.py
│   ├── replay_panel.py
│   ├── settings_dialog.py
│   └── styles.py
├── controller/        # Wires GUI ↔ backend
├── models.py          # Data structures
├── config.py          # YAML config
└── main.py            # Entry point
```

## ⚙️ Configuration

Edit `config.yaml`:

```yaml
vision:
  provider: "ollama"        # or "claude"
  ollama_model: "llava:13b"

recording:
  screenshot_interval_ms: 500
  capture_on_click: true

replay:
  action_delay_ms: 500
  confidence_threshold: 0.7
```

## ⚠️ Known Limitations

### Vision Accuracy
- **LLaVA (local)** provides decent but imperfect UI element detection. Pixel-level coordinate accuracy varies.
- **Claude (API)** is significantly more accurate but incurs cost per API call.
- Neither model achieves 100% reliability for element location on arbitrary UIs.

### Replay Fragility
- **UI changes break replays** — if buttons move, resize, change color, or the window layout shifts, the vision model may fail to locate elements.
- **Dynamic content** — loading spinners, popups, toast notifications, and animations can interfere with element finding. No smart "wait for element" logic yet.
- **Speed** — each replay step requires a vision API call (2–10s per step depending on model), so replays are not instantaneous.

### Platform & Environment
- **Multi-monitor / DPI scaling** — not tested; may cause coordinate mismatches on high-DPI or multi-display setups.
- **Privileged applications** — Windows apps running as administrator (Task Manager, UAC prompts) may block input simulation for security reasons.
- **Linux** — requires X11 display server for screen capture and input events. Wayland is not supported.

### Architectural
- **No accessibility tree** — purely vision-based element detection. Does not use OS-level UI Automation APIs (win32, AT-SPI), so it's essentially "looking at pixels."
- **No template matching fallback** — relies solely on LLM vision; no OpenCV-style image template matching for faster/cheaper element finding.

### Future Improvements (Roadmap)
- Hybrid element finding (vision + OS accessibility APIs)
- Smart waits for UI state changes
- OpenCV template matching as a fast fallback
- Workflow editing and step modification
- Conditional branching and loops in workflows

## 🛠 Development

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=process_recorder

# Type checking
mypy src/

# Format
black src/ tests/
```

## 📝 License

MIT — Built by Edwin Isac
