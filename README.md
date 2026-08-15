# JARVIS Local Desktop Agent

JARVIS is a local-first Windows desktop assistant powered by Ollama. It combines local language-model tool calling, offline speech recognition, text-to-speech, persistent memory, dynamic application discovery, website and Spotify routing, Git utilities, opt-in Training Mode, and explicit-consent screen automation.

> JARVIS is designed to assist with the user’s computer without silently taking control of the screen or continuously learning in the background.

## Features

| Capability | Description |
|---|---|
| Local LLM | Uses Ollama through the local HTTP API. The default chat model is `qwen2.5:7b`; model names can be changed in `config.py` or through environment variables. |
| GPU acceleration | Requests GPU layers from Ollama and keeps the model warm between requests when supported by the installed hardware and driver. |
| Text mode | `jarvis_text_mode.py` provides a reliable terminal interface for testing commands and tool calling. |
| Voice mode | Uses Vosk for offline speech recognition and pyttsx3 for local text-to-speech. |
| Dynamic app discovery | Finds Windows Start Menu applications and executables available on `PATH` instead of relying on a fixed application list. |
| Website and browser routing | Opens direct URLs, searches ambiguous website requests, and supports a session-scoped browser choice such as Microsoft Edge. |
| Spotify routing | Opens Spotify web search for requests such as “open Spotify and play music.” |
| Memory | Stores conversation turns and remembered facts in a local SQLite database. |
| Training Mode | Explicitly researches a requested topic, plans multiple searches, retrieves public sources, extracts readable content, cross-checks evidence with the local model, and saves a cited Markdown note. |
| Screen automation | Prepares click, typing, key, hotkey, and scroll actions, then waits for a separate `yes` or `confirm` before executing them. |
| Git utilities | Provides local repository inspection and common Git workflow assistance. |

## Requirements

The project is intended for Windows 10 or Windows 11. Install Python 3.10 or newer, [Ollama](https://ollama.com/download/windows), and the Python dependencies from `requirements.txt`.

For voice mode, a working microphone and audio output are required. For GPU acceleration, install a current NVIDIA driver when using an NVIDIA GPU and verify that Ollama recognizes it. The project remains usable on CPU, although response speed may be lower.

## Installation

Open a terminal in the project directory and create an optional virtual environment:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Install and start Ollama, then pull the configured chat model:

```bat
ollama pull qwen2.5:7b
```

If you want to use another local model, edit `OLLAMA_CHAT_MODEL` in `config.py` or set the `JARVIS_CHAT_MODEL` environment variable before starting JARVIS. The code-generation model is controlled by `JARVIS_CODE_MODEL`.

The included Vosk directory is intentionally ignored by Git because speech models are large. Download an English Vosk model from the [Vosk Models page](https://alphacephei.com/vosk/models), extract it beside `config.py`, and ensure the directory name matches `VOSK_MODEL_PATH` in `config.py`.

## Running JARVIS

For terminal testing:

```bat
python jarvis_text_mode.py
```

For normal voice mode:

```bat
python jarvis.py
```

You can also double-click:

```text
start_jarvis.bat
```

The launcher starts text mode from its own directory and keeps the terminal open if an error occurs.

## Example commands

```text
open Notepad
open Visual Studio Code
open https://github.com
use Microsoft Edge
open Spotify web and play music
remember that Yash's phone number is +91XXXXXXXXXX
research the history of the internet
enter training mode and learn about Python virtual environments
```

For a screen action, JARVIS should first describe the pending action. Say `yes` or `confirm` only after checking the exact action. Say `cancel` to discard it.

## Training Mode

Training Mode starts only when the user explicitly asks JARVIS to research, learn about, study, or enter Training Mode. It plans several focused searches, uses fallback public search providers, deduplicates sources, extracts readable page text, sends labeled evidence to the local Ollama model for synthesis, and saves a Markdown note under `data/knowledge/`.

Web content is treated as untrusted information. JARVIS does not execute instructions found in pages, submit forms, log into accounts, continuously monitor the internet, or learn silently in the background. Review generated notes and delete them if they are no longer needed.

## GPU verification

Use these commands while Ollama is running:

```bat
ollama ps
nvidia-smi
```

`ollama ps` should report a GPU processor allocation when the model is loaded on the GPU. `nvidia-smi` may show low utilization when the model is loaded but idle; monitor it during an active response if you want to observe generation utilization.

## Project layout

```text
.
├── config.py                 Central configuration
├── jarvis.py                 Voice-mode assistant and shared command handler
├── jarvis_text_mode.py       Terminal-only runner
├── modules/
│   ├── app_finder.py         Dynamic Windows application discovery
│   ├── automation.py         App, browser, website, Spotify, and OS automation
│   ├── git_manager.py        Git utilities and guarded code modification support
│   ├── llm_engine.py         Ollama client and model settings
│   ├── memory.py             SQLite memory and fact storage
│   ├── screen_control.py     Explicit-consent screen actions
│   ├── tools.py              Tool schemas and dispatch
│   └── training_mode.py      Agentic public-source research
├── data/                     Local runtime data; ignored except for placeholders
├── generated_code/           Generated scripts; ignored by Git
├── requirements.txt          Python dependencies
├── start_jarvis.bat          Windows launcher
└── vosk-model-*/             Local speech model; ignored by Git
```

## Security and privacy

JARVIS can interact with a real Windows desktop and can create or run code. Do not run it with privileges beyond those required for normal desktop use. Screen actions require explicit confirmation, but you should still review every action carefully. Do not store credentials, API keys, private databases, memory files, downloaded models, or personal contact data in Git.

The repository’s `.gitignore` excludes local databases, knowledge notes, backups, generated scripts, caches, model directories, environment files, and operating-system artifacts. Before publishing a change, inspect `git status` and `git diff --cached`.

## Development checks

Run the following before committing changes:

```bat
python -m compileall -q .
python -m pip check
```

For a clean repository state:

```bat
git status --short
git diff --check
```

## License

This project is released under the MIT License. See [`LICENSE`](LICENSE).
