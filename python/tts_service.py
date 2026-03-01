"""
ElevenLabs TTS streaming service.

Streams text to speech via the ElevenLabs API, yielding raw audio chunks
suitable for base64 encoding and sending over WebSocket.
"""

from __future__ import annotations

import os
from typing import AsyncIterator

import httpx

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE_ID = "xNtG3W2oqJs0cJZuTyBc"
DEFAULT_MODEL_ID = "eleven_turbo_v2_5"


def _get_api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY environment variable is not set")
    return key


def _get_voice_id() -> str:
    return os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)


async def stream_tts(text: str) -> AsyncIterator[bytes]:
    """
    Stream TTS audio from ElevenLabs.

    Yields raw audio bytes (mp3) as they arrive from the streaming API.
    """
    if not text.strip():
        print("[TTS] stream_tts: skipping empty text", flush=True)
        return

    api_key = _get_api_key()
    voice_id = _get_voice_id()

    url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}/stream"
    print(f"[TTS] stream_tts: text={text[:80]!r}  voice={voice_id}", flush=True)

    chunk_count = 0
    total_bytes = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream(
            "POST",
            url,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": DEFAULT_MODEL_ID,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            },
        ) as response:
            print(
                f"[TTS] ElevenLabs response status={response.status_code}", flush=True
            )
            response.raise_for_status()
            async for chunk in response.aiter_bytes(chunk_size=4096):
                if chunk:
                    chunk_count += 1
                    total_bytes += len(chunk)
                    yield chunk
    print(
        f"[TTS] stream_tts done: {chunk_count} chunks, {total_bytes} bytes total",
        flush=True,
    )
