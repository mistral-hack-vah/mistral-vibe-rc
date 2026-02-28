# python/audio_processor.py
"""
Real-time audio processor backed by Mistral's Voxtral Realtime API.

Pipeline per audio chunk received from the mobile app:
  1. Energy VAD  — decide if voice is active (lightweight, local)
  2. Buffer      — accumulate PCM16 bytes for the current utterance
  3. Partial     — periodically call Voxtral with the rolling buffer tail
                   to emit low-latency partial transcripts
  4. Final       — when silence exceeds threshold, flush the full utterance
                   to Voxtral for a high-accuracy final transcript

All Voxtral API calls go to `client.audio.transcriptions.create`.
No local model weights are downloaded.
"""

import asyncio
import io
import os
import time
import wave
from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np
from mistralai import Mistral


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

@dataclass
class SessionState:
    """Mutable per-session buffer and VAD state."""

    # Accumulated PCM16 bytes for the current utterance
    utterance_bytes: bytearray = field(default_factory=bytearray)

    # Simple energy VAD state
    in_speech: bool = False
    last_voice_ts: float = 0.0

    # Throttle partial decode calls
    last_partial_ts: float = 0.0
    last_partial_text: str = ""


# ---------------------------------------------------------------------------
# Voxtral Audio Processor
# ---------------------------------------------------------------------------

class VoxtralAudioProcessor:
    """
    Drop-in replacement for the old Whisper-based AudioProcessor.
    Identical external interface: process_audio / reset / finalize.

    Config via env vars:
        MISTRAL_API_KEY     — required
        VOXTRAL_MODEL       — default: voxtral-mini-transcribe
    """

    def __init__(
        self,
        sample_rate: int = 16_000,
        vad_energy_threshold: float = 0.015,   # tune per microphone/env
        silence_ms_to_finalize: int = 700,     # ms of silence → end utterance
        partial_interval_ms: int = 400,        # min ms between partial decodes
        partial_window_sec: float = 2.5,       # rolling tail sent for partial
        language: Optional[str] = None,        # e.g. "en" — None = auto-detect
    ):
        self.sample_rate = sample_rate
        self.vad_energy_threshold = vad_energy_threshold
        self.silence_ms_to_finalize = silence_ms_to_finalize
        self.partial_interval_ms = partial_interval_ms
        self.partial_window_sec = partial_window_sec
        self.language = language

        # bytes per second for PCM16 mono 16 kHz
        self.bytes_per_second = sample_rate * 2

        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            raise RuntimeError("MISTRAL_API_KEY environment variable is not set.")

        self.model = os.environ.get("VOXTRAL_MODEL", "voxtral-mini-transcribe")
        self._client = Mistral(api_key=api_key)

        # session_id → SessionState
        self._sessions: Dict[str, SessionState] = {}

    # ------------------------------------------------------------------
    # Public interface (same as the old AudioProcessor)
    # ------------------------------------------------------------------

    def reset(self, session_id: str) -> None:
        """Discard all buffered audio and VAD state for this session."""
        self._sessions.pop(session_id, None)

    async def finalize(self, session_id: str) -> Optional[str]:
        """Force-flush any buffered audio and return final transcript."""
        st = self._sessions.get(session_id)
        if not st or not st.utterance_bytes:
            return None
        text = await self._transcribe(bytes(st.utterance_bytes))
        self.reset(session_id)
        return text.strip() if text else None

    async def process_audio(
        self, audio_chunk: bytes, session_id: str
    ) -> Dict[str, Optional[str]]:
        """
        Process one binary audio chunk (PCM16 mono 16 kHz).

        Returns:
            {"partial": str | None, "final": str | None}
        """
        st = self._get_state(session_id)
        now = time.time()

        # ---- Energy VAD (fast, no network)
        pcm_f32 = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(np.square(pcm_f32))) + 1e-12)
        is_voice = rms >= self.vad_energy_threshold

        partial_out: Optional[str] = None
        final_out: Optional[str] = None

        if is_voice:
            st.last_voice_ts = now
            st.in_speech = True
            st.utterance_bytes.extend(audio_chunk)

            # Throttled partial decode — only every partial_interval_ms
            elapsed_ms = (now - st.last_partial_ts) * 1000.0
            if elapsed_ms >= self.partial_interval_ms:
                st.last_partial_ts = now
                window = self._tail_bytes(st.utterance_bytes, self.partial_window_sec)
                text = await self._transcribe(window)
                text = (text or "").strip()
                if text and text != st.last_partial_text:
                    st.last_partial_text = text
                    partial_out = text

        else:
            if st.in_speech:
                silent_ms = (now - st.last_voice_ts) * 1000.0
                if silent_ms >= self.silence_ms_to_finalize:
                    text = await self._transcribe(bytes(st.utterance_bytes))
                    text = (text or "").strip()
                    if text:
                        final_out = text
                    # Clear utterance
                    st.utterance_bytes.clear()
                    st.in_speech = False
                    st.last_partial_text = ""

        return {"partial": partial_out, "final": final_out}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_state(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState()
        return self._sessions[session_id]

    def _tail_bytes(self, buf: bytearray, seconds: float) -> bytes:
        max_len = int(self.bytes_per_second * seconds)
        if len(buf) <= max_len:
            return bytes(buf)
        return bytes(buf[-max_len:])

    async def _transcribe(self, pcm16_bytes: bytes) -> str:
        """
        Send PCM16 bytes to Voxtral via the mistralai SDK.

        The SDK expects an audio file-like object.  We wrap the raw PCM16
        in a minimal WAV container so Voxtral can decode the format correctly.
        """
        if not pcm16_bytes:
            return ""

        wav_bytes = self._pcm16_to_wav(pcm16_bytes)

        def _call() -> str:
            response = self._client.audio.transcriptions.create(
                model=self.model,
                file=("audio.wav", io.BytesIO(wav_bytes), "audio/wav"),
                **({"language": self.language} if self.language else {}),
            )
            # SDK returns an object with a .text attribute
            return getattr(response, "text", "") or ""

        # Run in a thread so the event loop isn't blocked during the API call
        return await asyncio.to_thread(_call)

    def _pcm16_to_wav(self, pcm16_bytes: bytes) -> bytes:
        """Wrap raw PCM16 mono 16 kHz bytes in a WAV container."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)           # mono
            wf.setsampwidth(2)           # 16-bit = 2 bytes
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm16_bytes)
        return buf.getvalue()


# ---------------------------------------------------------------------------
# Backwards-compat alias so any code that imports AudioProcessor still works
# ---------------------------------------------------------------------------
AudioProcessor = VoxtralAudioProcessor