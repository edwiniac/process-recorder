# ProcessRecorder

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
