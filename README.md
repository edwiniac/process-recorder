# ProcessRecorder 🎬

**Watch Me, Learn, Repeat** — Desktop automation through demonstration.

Record yourself doing a task, let AI understand it semantically, replay on demand.

## 🎯 What It Does

```
1. You: Click "Record"
2. You: Do the task manually (AI watches screenshots)
3. You: Click "Stop"
4. AI: "I learned: Open Chrome → Go to Gmail → Click Compose..."
5. Later: "Hey AI, do that email thing" → It replays
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Windows 10/11
- Ollama (for local AI): [ollama.com](https://ollama.com)

### Installation

```bash
# Clone the repo
git clone https://github.com/your-username/process-recorder.git
cd process-recorder

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev]"

# Pull the vision model (one-time)
ollama pull llava:13b
```

### Running

```bash
process-recorder
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                       GUI Layer                          │
├─────────────────────────────────────────────────────────┤
│                    Controller Layer                      │
├──────────────┬──────────────┬──────────────┬────────────┤
│   Recorder   │   Learner    │   Replayer   │  Storage   │
├──────────────┴──────────────┴──────────────┴────────────┤
│                    Vision Adapter                        │
│              (Ollama/LLaVA ↔ Claude API)                │
└─────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
process-recorder/
├── src/process_recorder/
│   ├── recorder/     # Screen + event capture
│   ├── learner/      # Vision → semantic steps
│   ├── replayer/     # Execute workflows
│   ├── vision/       # AI model adapters
│   ├── storage/      # Persistence
│   ├── gui/          # PyQt6 interface
│   └── controller/   # Business logic
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/
│   ├── REQUIREMENTS.md
│   ├── ARCHITECTURE.md
│   ├── TEST_PLAN.md
│   └── ROADMAP.md
├── recordings/       # Raw recordings
├── workflows/        # Processed workflows
└── config.yaml       # Configuration
```

## ⚙️ Configuration

Edit `config.yaml`:

```yaml
vision:
  provider: "ollama"  # or "claude"
  ollama_model: "llava:13b"
  claude_api_key: null  # Set env ANTHROPIC_API_KEY

recording:
  screenshot_interval_ms: 500
  capture_on_click: true

replay:
  action_delay_ms: 500
  confidence_threshold: 0.7
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/process_recorder --cov-report=html

# Run E2E tests with evidence collection
./tests/collect_evidence.sh E2E-01
```

## 📊 Development Status

| Sprint | Status | Description |
|--------|--------|-------------|
| Sprint 0 | ✅ | Foundation & docs |
| Sprint 1 | 🔄 | Recording module |
| Sprint 2 | ⏳ | Vision integration |
| Sprint 3 | ⏳ | Replay engine |
| Sprint 4 | ⏳ | GUI |
| Sprint 5 | ⏳ | Integration & polish |

## 🤝 Contributing

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

Built with ❤️ by Edwin Isac
