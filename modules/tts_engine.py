"""
Offline text-to-speech for JARVIS â€” no API keys.

Voice strategy (in order):
  1. Piper TTS with a local en_GB model (e.g. en_GB-alan-medium.onnx in
     voices/) â€” the most cinematic, Jarvis-like result. Fully offline.
     If the model is missing it is downloaded automatically on first use.
  2. pyttsx3 wrapping Windows SAPI5, automatically preferring a British
     male voice (George, Ryan, Guy, Andrew, Brian...) so JARVIS sounds
     the part even with stock Windows voices.

Speech is pumped from a queue on a dedicated worker thread, so say()
never blocks the caller and is safe to call from any thread (important
for the GUI and for timers firing in the background).
"""

import os
import queue
import threading
import urllib.request
import wave

from config import TTS_RATE, TTS_VOLUME, TTS_VOICE_INDEX, TTS_ENGINE, PIPER_MODEL_PATH, VOICES_DIR

# Piper model download URLs (HuggingFace mirror)
_PIPER_ONNX_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
    "en/en_GB/en_GB-alan-medium.onnx"
)
_PIPER_JSON_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
    "en/en_GB/en_GB-alan-medium.onnx.json"
)


class TTSEngine:
    # Voice names/id fragments that sound most like the films' butler.
    _BRITISH_HINTS = (
        "george", "ryan", "guy", "andrew", "brian", "thomas", "richard",
        "en-gb", "en_gb", "2057", "united kingdom", "google uk english male",
    )
    _FEMALE_HINTS = ("zira", "hazel", "susan", "susan;", "aria", "jenny", "sonia", "libby", "female")

    def __init__(self):
        self._queue = queue.Queue()
        self._speaking = threading.Event()
        self.on_speak_start = None   # optional callbacks (GUI hooks in here)
        self.on_speak_end = None
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    # â”€â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def say(self, text: str):
        """Queue a line to be spoken (and printed) â€” non-blocking."""
        text = str(text)
        print(f"JARVIS: {text}")
        self._queue.put(text)

    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    # â”€â”€â”€ Worker â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _worker(self):
        speaker = self._make_speaker()
        while True:
            text = self._queue.get()
            if text is None:
                break
            self._speaking.set()
            if self.on_speak_start:
                try:
                    self.on_speak_start()
                except Exception:
                    pass
            try:
                speaker(text)
            except Exception as exc:
                print(f"[TTS error] {exc}")
            finally:
                self._speaking.clear()
                if self.on_speak_end:
                    try:
                        self.on_speak_end()
                    except Exception:
                        pass

    def _make_speaker(self):
        if TTS_ENGINE in ("auto", "piper"):
            piper = self._init_piper()
            if piper is not None:
                print("[TTS] Using Piper voice â€” offline.")
                return piper
            if TTS_ENGINE == "piper":
                print("[TTS] Piper requested but unavailable; falling back to pyttsx3.")
        return self._init_pyttsx3()

    # â”€â”€â”€ Piper (offline, most Jarvis-like) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _init_piper(self):
        if not PIPER_MODEL_PATH:
            return None

        if not os.path.exists(PIPER_MODEL_PATH):
            print("[TTS] Piper model not found. Downloading en_GB-alan-medium...")
            if not self._download_piper_model():
                print("[TTS] Download failed. Falling back to pyttsx3.")
                return None

        try:
            import io

            import numpy as np
            import sounddevice as sd
            from piper import PiperVoice
        except ImportError:
            return None

        try:
            voice = PiperVoice.load(PIPER_MODEL_PATH)
        except Exception as exc:
            print(f"[TTS] Failed to load Piper model: {exc}")
            return None

        def speak(text: str):
            buffer = io.BytesIO()
            try:
                voice.synthesize(text, buffer)
            except AttributeError:
                buffer = io.BytesIO()
                voice.synthesize_wav(text, buffer)
            buffer.seek(0)
            with wave.open(buffer, "rb") as wav:
                audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
                sd.play(audio, wav.getframerate())
                sd.wait()

        return speak

    @staticmethod
    def _download_piper_model() -> bool:
        """Download the Piper voice model files. Returns True on success."""
        os.makedirs(VOICES_DIR, exist_ok=True)
        onnx_path = PIPER_MODEL_PATH
        json_path = PIPER_MODEL_PATH + ".json"

        for url, dest in ((_PIPER_ONNX_URL, onnx_path), (_PIPER_JSON_URL, json_path)):
            if os.path.exists(dest):
                continue
            try:
                print(f"[TTS] Downloading {os.path.basename(dest)}...")
                urllib.request.urlretrieve(url, dest, reporthook=_download_hook)
                print()
            except Exception as exc:
                print(f"[TTS] Failed to download {dest}: {exc}")
                return False
        print("[TTS] Piper model ready.")
        return True

    # â”€â”€â”€ pyttsx3 / Windows SAPI5 â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _init_pyttsx3(self):
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", TTS_RATE)
        engine.setProperty("volume", TTS_VOLUME)

        voices = engine.getProperty("voices") or []
        if TTS_VOICE_INDEX is not None and 0 <= TTS_VOICE_INDEX < len(voices):
            engine.setProperty("voice", voices[TTS_VOICE_INDEX].id)
        elif voices:
            best = max(voices, key=self._voice_score)
            engine.setProperty("voice", best.id)
            print(f"[TTS] Using Windows voice: {best.name}")

        def speak(text: str):
            engine.say(text)
            engine.runAndWait()

        return speak

    def _voice_score(self, voice) -> int:
        name = f"{getattr(voice, 'name', '')} {getattr(voice, 'id', '')}".lower()
        score = 0
        if any(hint in name for hint in self._BRITISH_HINTS):
            score += 5
        if any(hint in name for hint in self._FEMALE_HINTS):
            score -= 4
        if "david" in name or "mark" in name:
            score += 1  # neutral male fallbacks
        if "en-us" in name or "409" in name:
            score -= 1
        return score

    # â”€â”€â”€ Utility â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    @staticmethod
    def list_voices():
        """Print installed SAPI voices so you can pin one via TTS_VOICE_INDEX."""
        import pyttsx3

        engine = pyttsx3.init()
        for i, v in enumerate(engine.getProperty("voices") or []):
            print(f"[{i}] {v.name} ({v.id})")


def _download_hook(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0:
        pct = downloaded / total_size * 100
        mb = downloaded / 1048576
        total_mb = total_size / 1048576
        print(f"\r[TTS] ... {mb:.1f}/{total_mb:.1f} MB ({pct:.0f}%)", end="", flush=True)


if __name__ == "__main__":
    tts = TTSEngine()
    tts.list_voices()
    tts.say("Good evening, sir. All systems online.")
    tts._thread.join(timeout=30)
