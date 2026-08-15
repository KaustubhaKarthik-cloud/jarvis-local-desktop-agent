# JARVIS Local Desktop Agent

JARVIS is a local-first Windows desktop assistant powered by Ollama. It combines local language-model tool calling, offline speech recognition, a butler-grade offline voice, persistent memory, dynamic application discovery, website and Spotify routing, system telemetry and device control, timers and reminders, file and window management, Git utilities, opt-in Training Mode, and explicit-consent screen automation â€” with an optional Iron Man style HUD.

> JARVIS is designed to assist with the userâ€™s computer without silently taking control of the screen or continuously learning in the background.

## Features

| Capability | Description |
|---|---|
| Local LLM | Uses Ollama through the local HTTP API. The default chat model is `qwen2.5:7b`; model names can be changed in `config.py` or through environment variables. |
| GPU acceleration | Requests GPU layers from Ollama and keeps the model warm between requests when supported by the installed hardware and driver. |
| HUD interface | `jarvis_gui.py` â€” a dark arc-reactor dashboard with animated power core, mission log, text input, and a mic toggle. |
| Text mode | `jarvis_text_mode.py` provides a reliable terminal interface for testing commands and tool calling. |
| Voice mode | Uses faster-whisper for offline speech recognition; wake phrases are â€œJarvisâ€, â€œHey Jarvisâ€, or â€œWake up Jarvisâ€. |
| Jarvis voice | Offline TTS that automatically prefers a British male Windows voice, or a Piper `en_GB` model for a cinematic butler voice. No API keys. |
| System command | CPU, memory, disk, battery, and uptime diagnostics; volume, brightness, media keys, screenshots, and clipboard control. |
| Daily butler | Time and date, timers and reminders, local notes, exact arithmetic, and dry tech humor. |
| Files and windows | File search, opening folders and files, window listing, minimize/maximize/focus, and confirmation-gated window closing. |
| Dynamic app discovery | Finds Windows Start Menu applications and executables available on `PATH` instead of relying on a fixed application list. |
| Website and browser routing | Opens direct URLs, searches ambiguous website requests, and supports a session-scoped browser choice such as Microsoft Edge. |
| Spotify routing | Opens Spotify web search for requests such as â€œopen Spotify and play music.â€ |
| Memory | Stores conversation turns and remembered facts in a local SQLite database. |
| Training Mode | Explicitly researches a requested topic, plans multiple searches, retrieves public sources, extracts readable content, cross-checks evidence with the local model, and saves a cited Markdown note. |
| Screen automation | Prepares click, typing, key, hotkey, and scroll actions, then waits for a separate `yes` or `confirm` before executing them. |
| Git utilities | Provides local repository inspection and common Git workflow assistance. |

## Requirements

The project is intended for Windows 10 or Windows 11. On Windows, the requirements pin Piper TTS 1.6.1 because it provides a native Windows wheel; the older Piper 1.2.0 dependency chain does not provide the required Windows phonemization wheel. Install Python 3.10 or newer, [Ollama](https://ollama.com/download/windows), and the Python dependencies from `requirements.txt`.

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

Whisper models are downloaded by faster-whisper on first use. The selected model is `base`, with CPU `int8` settings by default. Piper downloads the British `en_GB-alan-medium` voice into `voices/` automatically on first TTS use.

## Running JARVIS

For the Iron Man style HUD (arc reactor, mission log, mic toggle):

```bat
python jarvis_gui.py
```

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
start_jarvis_gui.bat    (HUD)
start_jarvis.bat        (text mode)
```

The launchers start from their own directory and keep the terminal open if an error occurs.

## The Jarvis voice

Everything is offline â€” no API keys, no cloud voices.

- **Default**: pyttsx3 wraps the Windows SAPI5 voices and automatically picks the most butler-like British male voice installed (George, Ryan, Guy, Andrew, Brianâ€¦). Run `python -m modules.tts_engine` to list voices and pin one with `TTS_VOICE_INDEX` in `config.py`.
- **Cinematic (recommended)**: install Piper (`pip install piper-tts`) and download a British voice model such as `en_GB-alan-medium.onnx` from the [Piper samples page](https://rhasspy.github.io/piper-samples/) into `voices/`. JARVIS auto-detects it on next start and uses it for a much closer film-style voice.

## Example commands

```text
open Notepad
open Visual Studio Code
open https://github.com
use Microsoft Edge
open Spotify web and play music
status report
what time is it
set a five minute timer
remind me to stretch in 20 minutes
set volume to 40
take a screenshot
what's on my clipboard
calculate 15 percent of 240
find the file resume.pdf
open my downloads folder
minimize this window
remember that Yash's phone number is +91XXXXXXXXXX
tell me a joke
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
â”œâ”€â”€ config.py                 Central configuration
â”œâ”€â”€ jarvis.py                 Voice-mode assistant and shared command handler
â”œâ”€â”€ jarvis_text_mode.py       Terminal-only runner
â”œâ”€â”€ jarvis_gui.py             Iron Man style HUD (arc reactor, chat, mic)
â”œâ”€â”€ modules/
â”‚   â”œâ”€â”€ app_finder.py         Dynamic Windows application discovery
â”‚   â”œâ”€â”€ automation.py         App, browser, website, Spotify, file, window, and OS automation
â”‚   â”œâ”€â”€ daily.py              Clock, timers, reminders, arithmetic, smalltalk
â”‚   â”œâ”€â”€ git_manager.py        Git utilities and guarded code modification support
â”‚   â”œâ”€â”€ llm_engine.py         Ollama client and model settings
â”‚   â”œâ”€â”€ memory.py             SQLite memory and fact storage
â”‚   â”œâ”€â”€ screen_control.py     Explicit-consent screen actions
â”‚   â”œâ”€â”€ system_monitor.py     Telemetry, volume, brightness, clipboard
â”‚   â”œâ”€â”€ tools.py              Tool schemas and dispatch
â”‚   â”œâ”€â”€ training_mode.py      Agentic public-source research
â”‚   â”œâ”€â”€ tts_engine.py         Offline butler voice (pyttsx3 / Piper)
â”‚   â””â”€â”€ stt_engine.py         Offline Vosk speech recognition
â”œâ”€â”€ data/                     Local runtime data; ignored except for placeholders
â”œâ”€â”€ generated_code/           Generated scripts; ignored by Git
â”œâ”€â”€ voices/                   Optional Piper voice models; ignored by Git
â”œâ”€â”€ requirements.txt          Python dependencies
â”œâ”€â”€ start_jarvis.bat          Text-mode launcher
â”œâ”€â”€ start_jarvis_gui.bat      HUD launcher
â””â”€â”€ vosk-model-*/             Local speech model; ignored by Git
```

## Security and privacy

JARVIS can interact with a real Windows desktop and can create or run code. Do not run it with privileges beyond those required for normal desktop use. Screen actions require explicit confirmation, but you should still review every action carefully. Do not store credentials, API keys, private databases, memory files, downloaded models, or personal contact data in Git.

The repositoryâ€™s `.gitignore` excludes local databases, knowledge notes, backups, generated scripts, caches, model directories, environment files, and operating-system artifacts. Before publishing a change, inspect `git status` and `git diff --cached`.

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
