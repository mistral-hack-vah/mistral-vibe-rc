# python/audio_processor.py
"""
Push-to-talk audio processor backed by Mistral's Voxtral API.

Simple buffering model:
  1. start_recording() - Begin buffering audio
  2. append_audio()    - Add audio chunks to buffer
  3. stop_and_transcribe() - Stop recording, transcribe, return text

No VAD - user explicitly controls recording start/stop.
"""

import io
import os
import wave
from typing import Optional

from mistralai import Mistral


class PushToTalkProcessor:
    """
    Simple push-to-talk audio processor.

    Buffers PCM16 audio until user explicitly stops recording,
    then transcribes the entire buffer via Voxtral.

    Config via env vars:
        MISTRAL_API_KEY     — required
        VOXTRAL_MODEL       — default: voxtral-mini-2602
    """

    def __init__(
        self,
        sample_rate: int = 16_000,
        language: Optional[str] = None,
    ):
        self.sample_rate = sample_rate
        self.language = language

        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            raise RuntimeError("MISTRAL_API_KEY environment variable is not set.")

        self.model = os.environ.get("VOXTRAL_MODEL", "voxtral-mini-2602")
        self._client = Mistral(api_key=api_key)

        # session_id -> audio buffer (bytearray)
        self._buffers: dict[str, bytearray] = {}
        # session_id -> recording state
        self._recording: dict[str, bool] = {}

    def start_recording(self, session_id: str) -> None:
        """Begin recording for a session. Clears any existing buffer."""
        self._buffers[session_id] = bytearray()
        self._recording[session_id] = True

    def is_recording(self, session_id: str) -> bool:
        """Check if a session is currently recording."""
        return self._recording.get(session_id, False)

    def append_audio(self, session_id: str, chunk: bytes) -> None:
        """
        Append audio chunk to the session buffer.

        Args:
            session_id: The session ID
            chunk: Raw PCM16 mono 16kHz audio bytes
        """
        if session_id not in self._buffers:
            # Auto-start if not already recording
            self._buffers[session_id] = bytearray()
            self._recording[session_id] = True

        self._buffers[session_id].extend(chunk)

    async def stop_and_transcribe(self, session_id: str) -> str:
        """
        Stop recording and transcribe the buffered audio.

        Args:
            session_id: The session ID

        Returns:
            Transcribed text, or empty string if no audio buffered.
        """
        self._recording[session_id] = False

        if session_id not in self._buffers:
            return ""

        audio_bytes = bytes(self._buffers.pop(session_id))
        if not audio_bytes:
            return ""

        return await self._transcribe(audio_bytes)

    def cancel_recording(self, session_id: str) -> None:
        """Cancel recording and discard buffered audio."""
        self._buffers.pop(session_id, None)
        self._recording[session_id] = False

    def get_buffer_duration_ms(self, session_id: str) -> int:
        """Get the duration of buffered audio in milliseconds."""
        buf = self._buffers.get(session_id)
        if not buf:
            return 0
        # PCM16 mono: 2 bytes per sample
        num_samples = len(buf) // 2
        duration_sec = num_samples / self.sample_rate
        return int(duration_sec * 1000)

    async def _transcribe(self, pcm16_bytes: bytes) -> str:
        """
        Send PCM16 bytes to Voxtral for transcription.

        Wraps raw PCM16 in a WAV container for the API.
        """
        if not pcm16_bytes:
            return ""

        wav_bytes = self._pcm16_to_wav(pcm16_bytes)

        try:
            response = await self._client.audio.transcriptions.complete_async(
                model=self.model,
                file={
                    "file_name": "audio.wav",
                    "content": wav_bytes,
                },
                **({"language": self.language} if self.language else {}),
            )
            return (response.text or "").strip()
        except Exception as e:
            print(f"[Voxtral API Error] {e}")
            return ""

    def _pcm16_to_wav(self, pcm16_bytes: bytes) -> bytes:
        """Wrap raw PCM16 mono 16 kHz bytes in a WAV container."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm16_bytes)
        return buf.getvalue()


# Backwards compatibility aliases
VoxtralAudioProcessor = PushToTalkProcessor
AudioProcessor = PushToTalkProcessor
