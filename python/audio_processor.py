# python/audio_processor.py
"""
Realtime streaming transcription processor using Mistral's Voxtral API.

Pipeline:
  1. start_recording()  - Spawn background task that opens a realtime
                          transcription stream with Mistral.
  2. append_audio()     - Push PCM16 chunks into an asyncio.Queue that
                          feeds the stream.
  3. stop_and_transcribe() - Signal end-of-stream, wait for final
                             transcript, return text.

Transcript deltas are forwarded to the caller via an async on_delta
callback so the WebSocket handler can push them to the client in
real time.
"""

import asyncio
import os
from typing import AsyncIterator, Awaitable, Callable, Optional

from mistralai import Mistral
from mistralai.models import (
    AudioFormat,
    RealtimeTranscriptionError,
    RealtimeTranscriptionSessionCreated,
    TranscriptionStreamDone,
    TranscriptionStreamTextDelta,
)


class _Session:
    """Per-session state for one realtime transcription stream."""

    __slots__ = ("audio_queue", "task", "full_transcript", "done", "error")

    def __init__(self) -> None:
        self.audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.task: asyncio.Task | None = None
        self.full_transcript: str = ""
        self.done: asyncio.Event = asyncio.Event()
        self.error: str | None = None


# Type for the delta callback: (session_id, delta_text) -> awaitable
OnDelta = Callable[[str, str], Awaitable[None]]


class RealtimeTranscriptionProcessor:
    """
    Realtime push-to-talk processor backed by Mistral's streaming
    transcription API (voxtral-mini-transcribe-realtime-2602).

    Config via env vars:
        MISTRAL_API_KEY              - required
        VOXTRAL_REALTIME_MODEL       - default: voxtral-mini-transcribe-realtime-2602
    """

    def __init__(
        self,
        sample_rate: int = 16_000,
        on_delta: Optional[OnDelta] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self._on_delta = on_delta

        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            raise RuntimeError("MISTRAL_API_KEY environment variable is not set.")

        self.model = os.environ.get(
            "VOXTRAL_REALTIME_MODEL",
            "voxtral-mini-transcribe-realtime-2602",
        )
        self._client = Mistral(api_key=api_key)
        self._sessions: dict[str, _Session] = {}

    # ------------------------------------------------------------------
    # Public API (same interface as the old PushToTalkProcessor)
    # ------------------------------------------------------------------

    def start_recording(self, session_id: str) -> None:
        """Begin a realtime transcription session."""
        self._cleanup(session_id)

        session = _Session()
        self._sessions[session_id] = session
        session.task = asyncio.create_task(self._run(session_id, session))
        print(f"[RealtimeTranscription] started for {session_id}", flush=True)

    def is_recording(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        return session is not None and not session.done.is_set()

    def append_audio(self, session_id: str, chunk: bytes) -> None:
        """Push a PCM16 chunk into the session queue."""
        session = self._sessions.get(session_id)
        if session and not session.done.is_set():
            session.audio_queue.put_nowait(chunk)

    async def stop_and_transcribe(self, session_id: str) -> str:
        """Signal end-of-stream and wait for the final transcript."""
        session = self._sessions.get(session_id)
        if not session:
            return ""

        # Signal the async generator to stop
        await session.audio_queue.put(None)

        # Wait for the transcription task to complete
        if session.task:
            try:
                await asyncio.wait_for(session.task, timeout=15.0)
            except asyncio.TimeoutError:
                print(f"[RealtimeTranscription] timeout for {session_id}", flush=True)
                session.task.cancel()
            except Exception as e:
                print(f"[RealtimeTranscription] error: {e}", flush=True)

        transcript = session.full_transcript.strip()
        print(f"[RealtimeTranscription] final transcript: {transcript!r}", flush=True)
        self._cleanup(session_id)
        return transcript

    def cancel_recording(self, session_id: str) -> None:
        """Cancel recording and discard everything."""
        session = self._sessions.get(session_id)
        if session:
            session.audio_queue.put_nowait(None)
            if session.task:
                session.task.cancel()
        self._cleanup(session_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _audio_stream(self, session: _Session) -> AsyncIterator[bytes]:
        """Async generator that drains the queue and feeds transcribe_stream."""
        while True:
            chunk = await session.audio_queue.get()
            if chunk is None:
                return
            yield chunk

    async def _run(self, session_id: str, session: _Session) -> None:
        """Background task: open realtime transcription and process events."""
        audio_format = AudioFormat(encoding="pcm_s16le", sample_rate=self.sample_rate)

        try:
            async for event in self._client.audio.realtime.transcribe_stream(
                audio_stream=self._audio_stream(session),
                model=self.model,
                audio_format=audio_format,
            ):
                if isinstance(event, RealtimeTranscriptionSessionCreated):
                    print(f"[RealtimeTranscription] session created", flush=True)

                elif isinstance(event, TranscriptionStreamTextDelta):
                    session.full_transcript += event.text
                    print(f"[RealtimeTranscription] delta: {event.text!r}", flush=True)
                    if self._on_delta:
                        try:
                            await self._on_delta(session_id, event.text)
                        except Exception as e:
                            print(f"[RealtimeTranscription] on_delta error: {e}", flush=True)

                elif isinstance(event, TranscriptionStreamDone):
                    print(f"[RealtimeTranscription] done", flush=True)

                elif isinstance(event, RealtimeTranscriptionError):
                    session.error = str(event)
                    print(f"[RealtimeTranscription] error event: {event}", flush=True)

        except Exception as e:
            session.error = str(e)
            print(f"[RealtimeTranscription] stream error: {e}", flush=True)

        finally:
            session.done.set()

    def _cleanup(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


# Backwards compatibility aliases
PushToTalkProcessor = RealtimeTranscriptionProcessor
VoxtralAudioProcessor = RealtimeTranscriptionProcessor
AudioProcessor = RealtimeTranscriptionProcessor
