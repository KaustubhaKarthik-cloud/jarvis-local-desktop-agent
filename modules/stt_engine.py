"""
Offline speech-to-text using Vosk.
Requires a downloaded Vosk model folder (see README.md for the link) placed at
the path configured in config.VOSK_MODEL_PATH.

No internet connection is used at any point - recognition happens fully on-device.
"""

import json
import os
import queue

import sounddevice as sd
from vosk import Model, KaldiRecognizer

from config import VOSK_MODEL_PATH

SAMPLE_RATE = 16000


class STTEngine:
    def __init__(self, model_path=VOSK_MODEL_PATH):
        if not os.path.isdir(model_path):
            raise FileNotFoundError(
                f"Vosk model not found at '{model_path}'.\n"
                "Download a model from https://alphacephei.com/vosk/models "
                "(e.g. vosk-model-small-en-us-0.15), unzip it, and place it at that path.\n"
                "See README.md for step-by-step instructions."
            )
        self.model = Model(model_path)
        self.audio_queue = queue.Queue()

    def _callback(self, indata, frames, time, status):
        self.audio_queue.put(bytes(indata))

    def listen_once(self, timeout_seconds=8):
        """
        Listens to the microphone until a pause is detected (or timeout hit),
        and returns the recognized text (lowercase). Returns "" if nothing understood.
        """
        recognizer = KaldiRecognizer(self.model, SAMPLE_RATE)
        recognizer.SetWords(True)

        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=self._callback,
        ):
            print("Listening...")
            silence_blocks = 0
            max_silence_blocks = int(timeout_seconds * SAMPLE_RATE / 8000)

            while True:
                data = self.audio_queue.get()
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        return text.lower()
                    silence_blocks += 1
                else:
                    silence_blocks += 1

                if silence_blocks > max_silence_blocks:
                    partial = json.loads(recognizer.FinalResult())
                    return partial.get("text", "").strip().lower()


if __name__ == "__main__":
    stt = STTEngine()
    print("Say something...")
    print("You said:", stt.listen_once())
