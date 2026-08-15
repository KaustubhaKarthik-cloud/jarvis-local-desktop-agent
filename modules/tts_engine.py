"""
Offline text-to-speech using pyttsx3 (wraps Windows SAPI5 on Windows).
No internet required.
"""

import pyttsx3
from config import TTS_RATE, TTS_VOLUME, TTS_VOICE_INDEX


class TTSEngine:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", TTS_RATE)
        self.engine.setProperty("volume", TTS_VOLUME)

        voices = self.engine.getProperty("voices")
        if voices and 0 <= TTS_VOICE_INDEX < len(voices):
            self.engine.setProperty("voice", voices[TTS_VOICE_INDEX].id)

    def list_voices(self):
        """Utility: print available voices so you can pick TTS_VOICE_INDEX in config.py"""
        voices = self.engine.getProperty("voices")
        for i, v in enumerate(voices):
            print(f"[{i}] {v.name} ({v.id})")

    def say(self, text: str):
        print(f"JARVIS: {text}")
        self.engine.say(text)
        self.engine.runAndWait()


if __name__ == "__main__":
    tts = TTSEngine()
    tts.list_voices()
    tts.say("Hello, I am JARVIS. All systems online.")
