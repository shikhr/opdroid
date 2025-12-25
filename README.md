# opdroid

LLM-controlled Android device automation via ADB. Give natural language commands and watch an AI agent operate your Android device.



https://github.com/user-attachments/assets/89ee92fe-2501-447e-9c8e-9a3d8f0a7994



## How It Works

1. Captures a screenshot from your Android device
2. Overlays a labeled grid (columns A-Z, rows 1-N) on the screenshot
3. Sends the gridded image to an LLM with your objective
4. LLM responds with grid-based actions like `tap(cell="E10")`
5. Actions are converted to device coordinates and executed via ADB
6. Repeat until task is complete

The grid system significantly improves accuracy compared to having the LLM guess raw pixel coordinates.

## Requirements

- Python 3.10+
- Android device with USB debugging enabled
- ADB installed and device connected
- API key for an LLM provider (OpenAI, Anthropic, Groq, Gemini, etc.)

## Installation

```bash
# Install from PyPI
pip install opdroid

# Or clone and install locally
git clone https://github.com/shikhr/opdroid.git
cd opdroid
uv sync
```

## Configuration

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` and set at least one API key:

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=...
```

## Usage

```bash
# Start interactive mode (default)
opdroid

# Specify a different model
opdroid --model "groq/llama-3.3-70b-versatile"
opdroid --model "gemini/gemini-2.0-flash"

# Limit image history (useful for rate-limited providers)
opdroid --max-images 3

# List connected devices
opdroid devices

# Capture a screenshot
opdroid screenshot -o screen.png
```

In interactive mode, type your objectives and the agent will execute them:

```
User > Open YouTube and search for cats
🎯 Objective: Open YouTube and search for cats
─── Iteration 1/50 ───
...
```

### Available Tools

The agent can use these actions:

| Tool | Description |
|------|-------------|
| `tap(cell)` | Tap on a grid cell (e.g., "E10") |
| `swipe(start_cell, end_cell)` | Swipe between cells for scrolling |
| `input_text(text)` | Type text into focused field |
| `press_home()` | Press the home button |
| `press_back()` | Press the back button |
| `press_enter()` | Press enter/submit |
| `launch_app(package)` | Launch app by package name |
| `wait(seconds)` | Wait for content to load |
| `task_complete(summary)` | Mark task as done |
| `task_impossible(reason)` | Mark task as impossible |

## Demo

Capture a screenshot with grid overlay to see what the LLM sees:

```bash
uv run tests/demo_screenshot.py
```

This saves `screenshot_gridded.png` showing the labeled grid overlay.

## Supported Models

Any model supported by [LiteLLM](https://docs.litellm.ai/docs/providers) that has:
- Vision capability (to understand screenshots)
- Function/tool calling (to execute actions)

Tested with:
- `gpt-4o` (OpenAI)
- `claude-sonnet-4-20250514` (Anthropic)
- `gemini/gemini-2.0-flash` (Google)
- `groq/llama-3.3-70b-versatile` (Groq)

## License

MIT
