# python/audio_processor.py
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List

import numpy as np
import whisper


@dataclass
class SessionState:
    # Raw PCM16 bytes buffer for current utterance
    utterance_bytes: bytearray = field(default_factory=bytearray)

    # VAD state
    in_speech: bool = False
    last_voice_ts: float = 0.0

    # Partial transcription throttling
    last_partial_ts: float = 0.0
    last_partial_text: str = ""

    # For rolling partial decode, keep only last N seconds
    # (we store bytes and slice)
    # audio is PCM16 mono 16k -> 32000 bytes/sec
    pass


class AudioProcessor:
    """
    Real-time-ish Whisper chunk processor with partial/final outputs.

    Assumptions:
      - incoming audio chunks are PCM16 mono at 16kHz
      - uses simple energy-based VAD and Whisper decoding on rolling windows
    """

    def __init__(
        self,
        model_name: str = "base",
        sample_rate: int = 16000,
        vad_energy_threshold: float = 0.015,   # tune per microphone
        silence_ms_to_finalize: int = 700,     # silence duration to end utterance
        partial_interval_ms: int = 400,        # how often to emit partial updates
        partial_window_sec: float = 2.5,       # rolling window for partial decode
        language: Optional[str] = None,        # set e.g. "en" to speed up
    ):
        self.sample_rate = sample_rate
        self.vad_energy_threshold = vad_energy_threshold
        self.silence_ms_to_finalize = silence_ms_to_finalize
        self.partial_interval_ms = partial_interval_ms
        self.partial_window_sec = partial_window_sec
        self.language = language

        self.model = whisper.load_model(model_name)

        # per-session state
        self.sessions: Dict[str, SessionState] = {}

        # bytes per second for PCM16 mono
        self.bytes_per_second = self.sample_rate * 2

    def _state(self, session_id: str) -> SessionState:
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState()
        return self.sessions[session_id]

    def reset(self, session_id: str):
        self.sessions.pop(session_id, None)

    async def finalize(self, session_id: str) -> Optional[str]:
        st = self.sessions.get(session_id)
        if not st or not st.utterance_bytes:
            return None
        text = await self._decode_bytes(bytes(st.utterance_bytes))
        # clear utterance
        st.utterance_bytes.clear()
        st.in_speech = False
        st.last_partial_text = ""
        return text.strip() if text else None

    async def process_audio(self, audio_chunk: bytes, session_id: str) -> Dict[str, Optional[str]]:
        """
        Returns {"partial": str|None, "final": str|None}
        """
        st = self._state(session_id)
        now = time.time()

        # Convert chunk to float32 for VAD energy check (fast)
        pcm = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0

        # Simple energy VAD (RMS)
        rms = float(np.sqrt(np.mean(np.square(pcm))) + 1e-12)
        is_voice = rms >= self.vad_energy_threshold

        partial_out: Optional[str] = None
        final_out: Optional[str] = None

        if is_voice:
            st.last_voice_ts = now
            st.in_speech = True
            st.utterance_bytes.extend(audio_chunk)

            # emit partial at most every partial_interval_ms
            if (now - st.last_partial_ts) * 1000.0 >= self.partial_interval_ms:
                st.last_partial_ts = now

                # For partial: decode only last partial_window_sec seconds
                window_bytes = self._tail_bytes(st.utterance_bytes, self.partial_window_sec)
                text = await self._decode_bytes(window_bytes)
                text = (text or "").strip()

                # only emit if changed (reduce spam)
                if text and text != st.last_partial_text:
                    st.last_partial_text = text
                    partial_out = text

        else:
            # if we were speaking and now silent long enough -> finalize
            if st.in_speech:
                silent_ms = (now - st.last_voice_ts) * 1000.0
                if silent_ms >= self.silence_ms_to_finalize:
                    # finalize full utterance
                    text = await self._decode_bytes(bytes(st.utterance_bytes))
                    text = (text or "").strip()
                    if text:
                        final_out = text

                    # reset utterance state
                    st.utterance_bytes.clear()
                    st.in_speech = False
                    st.last_partial_text = ""

        return {"partial": partial_out, "final": final_out}

    def _tail_bytes(self, buf: bytearray, seconds: float) -> bytes:
        max_len = int(self.bytes_per_second * seconds)
        if len(buf) <= max_len:
            return bytes(buf)
        return bytes(buf[-max_len:])

    async def _decode_bytes(self, pcm16_bytes: bytes) -> str:
        """
        Decode PCM16 mono 16kHz bytes with Whisper.
        Runs in a thread to avoid blocking the event loop.
        """
        if not pcm16_bytes:
            return ""

        audio = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        def _run():
            # Whisper expects float32 waveform at 16kHz
            result = self.model.transcribe(
                audio,
                fp16=False,
                language=self.language,
                # You can add: temperature=0, no_speech_threshold=...
            )
            return result.get("text", "")

        return await asyncio.to_thread(_run)