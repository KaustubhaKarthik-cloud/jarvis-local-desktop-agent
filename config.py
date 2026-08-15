"""
Central configuration for JARVIS.
Edit these values to customize behavior.
"""

import os

# ---------- Paths ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
GENERATED_CODE_DIR = os.path.join(BASE_DIR, "generated_code")
MEMORY_DB_PATH = os.path.join(DATA_DIR, "memory.db")
WHISPER_MODEL_SIZE = "base"       # tiny, base, small, medium, large
WHISPER_DEVICE = "cpu"            # "cpu" or "cuda" (set cuda if you have a GPU)
WHISPER_COMPUTE_TYPE = "int8"      # "int8" (fastest CPU), "float16" (GPU), "float32"
NOTES_DIR = os.path.join(DATA_DIR, "notes")
SCREENSHOT_DIR = os.path.join(DATA_DIR, "screenshots")
VOICES_DIR = os.path.join(BASE_DIR, "voices")

# ---------- Wake word ----------
# Any of these phrases wakes the assistant; the rest of the utterance is
# treated as the command ("Jarvis, open Notepad").
WAKE_WORDS = ["wake up jarvis", "hey jarvis", "jarvis"]
USE_WAKE_WORD = True

# ---------- Ollama ----------
OLLAMA_CHAT_MODEL = os.environ.get("JARVIS_CHAT_MODEL", "qwen2.5:7b")
OLLAMA_CODE_MODEL = os.environ.get("JARVIS_CODE_MODEL", "deepseek-r1:7b")
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"  # used for tool/function calling

CHAT_SYSTEM_PROMPT = (
    "You are JARVIS, the user's personal AI butler in the style of the Iron Man "
    "films: composed, precise, witty. Address the user as 'sir'. Keep replies "
    "to 1-3 sentences. Never claim an action happened unless the tool confirms it. "
    "Screen-control actions must wait for explicit user confirmation before executing.\n\n"
    "Training Mode is opt-in, only when the user explicitly asks to research or learn. "
    "When a tool reports an action is pending, tell the user to confirm."
)
CODE_SYSTEM_PROMPT = (
    "You are JARVIS's coding engine. Write clean, correct, well-commented Python code. "
    "Return ONLY the code — no explanation, no markdown fences, no preamble. "
    "Think through edge cases before writing."
)

# ---------- Text-to-speech ----------
# TTS_ENGINE: "auto" (Piper if a model is present, else pyttsx3), "piper", or "pyttsx3".
# For the most cinematic JARVIS voice, install piper-tts (pip install piper-tts)
# and download an en_GB model such as en_GB-alan-medium.onnx into voices/.
TTS_ENGINE = "piper"
PIPER_MODEL_PATH = os.path.join(VOICES_DIR, "en_GB-alan-medium.onnx")
TTS_RATE = 178
TTS_VOLUME = 1.0
TTS_VOICE_INDEX = None  # None = auto-pick the most butler-like installed voice

# ---------- Performance ----------
# Ollama will use as many GPU layers as the hardware supports and fall back safely.
OLLAMA_NUM_GPU = 999
OLLAMA_NUM_THREAD = max(4, (os.cpu_count() or 8) - 1)
OLLAMA_NUM_CTX = 3072   # enough for tool schemas + history; larger = slower
OLLAMA_CHAT_NUM_PREDICT = 80   # most replies are 1-3 sentences
OLLAMA_CODE_NUM_PREDICT = 512
OLLAMA_KEEP_ALIVE = "20m"  # keep model warm between requests
OLLAMA_TEMPERATURE = 0.1

# ---------- Bounded Training Mode and screen consent ----------
TRAINING_KNOWLEDGE_DIR = os.path.join(DATA_DIR, "knowledge")
TRAINING_MAX_SOURCES = 5
SCREEN_CONFIRMATION_REQUIRED = True
TRAINING_MAX_ARTICLES = 3
TRAINING_FETCH_TIMEOUT = 15
TRAINING_SEARCH_TIMEOUT = 20
