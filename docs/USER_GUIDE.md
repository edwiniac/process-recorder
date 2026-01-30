# ProcessRecorder — User Guide

## Overview

ProcessRecorder is a desktop automation tool that learns from watching you work. Record a task once, and it creates a replayable workflow.

**How it works:**
1. **Record** — Captures your mouse clicks, keyboard input, and screenshots
2. **Learn** — Uses AI vision (Ollama/LLaVA or Claude) to understand what you did
3. **Replay** — Finds the same UI elements and repeats your actions

---

## Installation

### Prerequisites
- Python 3.10+
- Windows 10/11 (primary), Linux with X11 (supported)
- Ollama with LLaVA model (optional, for local AI)

### Setup

```bash
git clone https://github.com/edwiniac/process-recorder.git
cd process-recorder
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

pip install -e ".[dev]"
```

### Ollama Setup (Optional)

```bash
# Install Ollama: https://ollama.ai
ollama pull llava:13b
ollama serve  # Start in background
```

---

## Quick Start

### Launch the GUI

```bash
process-recorder
# or
python -m process_recorder
```

### Record a Task

1. Type a name for your recording
2. Click **⏺ Record**
3. Perform your task (click, type, scroll, etc.)
4. Click **⏹ Stop** when done

Your recording is saved with all screenshots and events.

### Process into Workflow

After recording, the system automatically:
- Groups your clicks, typing, scrolls, and hotkeys
- Uses AI to identify what UI elements you interacted with
- Creates a named workflow with semantic step descriptions

### Replay a Workflow

1. Select a workflow from the list
2. Choose an error strategy (Stop / Skip / Retry)
3. Click **▶ Start Replay**
4. Watch as it finds elements and repeats your actions

---

## Configuration

Edit `config.yaml` or use **Settings → Preferences** in the GUI.

### Vision Provider

| Setting | Default | Description |
|---------|---------|-------------|
| `provider` | `ollama` | `ollama` (local) or `claude` (API) |
| `ollama_model` | `llava:13b` | Ollama model name |
| `ollama_base_url` | `http://localhost:11434` | Ollama server URL |
| `claude_api_key` | `null` | Anthropic API key |
| `claude_model` | `claude-3-5-sonnet-20241022` | Claude model |

### Recording

| Setting | Default | Description |
|---------|---------|-------------|
| `screenshot_interval_ms` | `500` | Screenshot capture interval |
| `capture_on_click` | `true` | Capture extra screenshot on clicks |
| `max_screenshots` | `1000` | Maximum screenshots per recording |

### Replay

| Setting | Default | Description |
|---------|---------|-------------|
| `action_delay_ms` | `500` | Delay between replay actions |
| `element_find_timeout_ms` | `5000` | How long to search for elements |
| `confidence_threshold` | `0.7` | Minimum confidence for element match |

---

## Error Strategies

During replay, if an element can't be found:

- **Stop** — Halt replay immediately
- **Skip** — Skip the step, continue with next
- **Retry** — Retry finding the element (up to 3 times)

---

## Architecture

```
┌─────────────────────────────────────┐
│           GUI (PyQt6)               │
├─────────────────────────────────────┤
│         App Controller              │
├──────────┬──────────┬───────────────┤
│ Recorder │ Learner  │   Replayer    │
├──────────┴──────────┴───────────────┤
│        Vision Adapter               │
│     (Ollama / Claude)               │
└─────────────────────────────────────┘
```

---

## Troubleshooting

### "No vision provider available"
- Check Ollama is running: `ollama list`
- Or set a Claude API key in settings

### "Element not found during replay"
- The UI may have changed since recording
- Try lowering the confidence threshold (0.5)
- Use "Skip" error strategy to continue past failures

### "Recording captures no events"
- On Linux: requires X11 display server
- On Windows: run as administrator if events aren't captured

---

## Project Structure

```
src/process_recorder/
├── recorder/          # Screen capture + event listening
├── learner/           # Action classification + semantic extraction
├── replayer/          # Element finding + action execution
├── vision/            # Ollama/Claude vision adapters
├── gui/               # PyQt6 interface
├── controller/        # Wires GUI to backend
├── models.py          # Data structures
├── config.py          # Configuration loading
└── main.py            # Entry point
```

---

## License

MIT — Built by Edwin Isac
