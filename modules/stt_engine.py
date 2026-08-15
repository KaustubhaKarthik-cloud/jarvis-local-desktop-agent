"""
Offline speech-to-text using faster-whisper (local Whisper).

Uses actual audio energy (RMS) for voice-activity detection instead of
counting every block as silence. The flow is:
  1. Open a raw mic stream and collect 100 ms audio blocks.
  2. RMS energy determines whether the user is speaking or silent.
  3. Once speech starts, audio is accumulated into a buffer.
  4. After ~300 ms of silence the utterance is considered complete.
  5. The buffer is passed to Whisper for transcription.

No internet connection is used at any point - recognition happens fully
on-device.
"""

import math
import os
import queue
import struct

import numpy as np
import sounddevice as sd

from config import WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE

SAMPLE_RATE = 16000

# Voice-activity detection thresholds (tuned for a typical desktop mic).
_SILENCE_RMS = 300
_SILENCE_BLOCKS = 3          # 3 x 100 ms = 300 ms end-of-speech gap
_LEAD_IN_BLOCKS = 50         # 5 s maximum wait for speech to start
_BLOCK_MS = 100
_BLOCK_SIZE = int(SAMPLE_RATE * _BLOCK_MS / 1000)  # 1600 samples


class STTEngine:
    def __init__(self):
        from faster_whisper import WhisperModel

        device = WHISPER_DEVICE
        compute = WHISPER_COMPUTE_TYPE
        print(f"[STT] Loading Whisper ({WHISPER_MODEL_SIZE}) on {device}/{compute}...")
        self.model = WhisperModel(WHISPER_MODEL_SIZE, device=device, compute_type=compute)
        print("[STT] Whisper model loaded.")
        self.audio_queue = queue.Queue()

    def _callback(self, indata, frames, time, status):
        self.audio_queue.put(bytes(indata))

    @staticmethod
    def _rms(data: bytes) -> float:
        """Root-mean-square energy of a 16-bit PCM audio chunk."""
        n = len(data) // 2
        if n == 0:
            return 0.0
        fmt = f"<{n}h"
        samples = struct.unpack(fmt, data[: n * 2])
        return math.sqrt(sum(s * s for s in samples) / n)

    def listen_once(self, timeout_seconds=8):
        """
        Listens to the microphone until speech ends (or timeout hit),
        and returns the recognized text (lowercase). Returns "" if nothing
        understood. Uses RMS energy for fast, accurate end-of-speech.
        """
        audio_buffer = bytearray()

        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=_BLOCK_SIZE,
            dtype="int16",
            channels=1,
            callback=self._callback,
        ):
            print("Listening...")
            silence_count = 0
            lead_in = 0
            heard_speech = False

            while True:
                data = self.audio_queue.get()
                energy = self._rms(data)

                if energy > _SILENCE_RMS:
                    heard_speech = True
                    silence_count = 0
                    audio_buffer.extend(data)
                else:
                    silence_count += 1
                    if heard_speech:
                        audio_buffer.extend(data)

                if not heard_speech:
                    lead_in += 1
                    if lead_in >= _LEAD_IN_BLOCKS:
                        return ""

                # End of utterance: user was speaking and is now silent.
                if heard_speech and silence_count >= _SILENCE_BLOCKS:
                    text = self._transcribe(bytes(audio_buffer))
                    return text

                # Hard timeout (safety net).
                if lead_in + silence_count > int(timeout_seconds * 1000 / _BLOCK_MS):
                    if heard_speech:
                        text = self._transcribe(bytes(audio_buffer))
                        return text
                    return ""

    def _transcribe(self, raw_pcm: bytes) -> str:
        """Convert raw 16-bit PCM bytes to text via Whisper."""
        if len(raw_pcm) < _BLOCK_SIZE * 2:
            return ""

        audio = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32) / 32768.0

        segments, _ = self.model.transcribe(audio, language="en", beam_size=3)
        text = " ".join(seg.text for seg in segments).strip()
        return text.lower()


if __name__ == "__main__":
    stt = STTEngine()
    print("Say something...")
    print("You said:", stt.listen_once())
