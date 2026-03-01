"""
tests/manual_interrupt_test.py — Voice interrupt demo
======================================================
Demonstrates the voice interrupt feature:

  1. You speak a question.
  2. The agent starts responding (you see text streaming + hear TTS).
  3. As soon as the first words arrive, the script AUTO-INTERRUPTS.
  4. You immediately speak a second question.
  5. The agent responds to the second question.

This proves: pressing mic while agent is responding instantly stops it
and starts listening — the core "voice interrupt" UX.

Requires the backend to be running:
    uv run python -m uvicorn python.main:app --host 0.0.0.0 --port 8000

Run with:
    uv run python tests/manual_interrupt_test.py
"""

import asyncio
import base64
import ctypes
import json
import os
import sys
import tempfile
import threading
import time

_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

import jwt
import pyaudio
import websockets

WS_URL = os.environ.get("BACKEND_WS_URL", "ws://localhost:8000/ws/audio")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ISSUER = os.environ.get("JWT_ISSUER", "voice-agent-api")
RATE, CHANNELS, CHUNK = 16_000, 1, 1024
FORMAT = pyaudio.paInt16


def make_token() -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": "interrupt-test", "iss": JWT_ISSUER, "iat": now, "exp": now + 3600},
        JWT_SECRET, algorithm="HS256",
    )


class MicRecorder:
    def __init__(self, on_chunk):
        self._on_chunk = on_chunk
        self._recording = False
        self._pa = pyaudio.PyAudio()

    def start(self):
        self._recording = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._recording = False

    def _run(self):
        stream = self._pa.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                               input=True, frames_per_buffer=CHUNK)
        try:
            while self._recording:
                self._on_chunk(stream.read(CHUNK, exception_on_overflow=False))
        finally:
            stream.stop_stream()
            stream.close()

    def terminate(self):
        self._pa.terminate()


def play_mp3(chunks: list[bytes]):
    if not chunks:
        return
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    for c in chunks:
        tmp.write(c)
    tmp.close()
    mci = ctypes.windll.winmm
    mci.mciSendStringW(f'open "{tmp.name}" type mpegvideo alias tts', None, 0, None)
    mci.mciSendStringW('seek tts to start', None, 0, None)
    mci.mciSendStringW('play tts wait', None, 0, None)
    mci.mciSendStringW('close tts', None, 0, None)
    os.unlink(tmp.name)


async def record_and_send(ws, loop, label: str) -> None:
    """Record until user presses Enter, streaming PCM to server."""
    send_queue: asyncio.Queue = asyncio.Queue()

    def on_chunk(data):
        loop.call_soon_threadsafe(send_queue.put_nowait, data)

    recorder = MicRecorder(on_chunk=on_chunk)
    recorder.start()

    stop_event = asyncio.Event()

    async def stream():
        while not stop_event.is_set():
            try:
                chunk = await asyncio.wait_for(send_queue.get(), timeout=0.1)
                await ws.send(chunk)
            except asyncio.TimeoutError:
                continue

    await ws.send(json.dumps({"type": "start"}))
    stream_task = asyncio.create_task(stream())
    await asyncio.get_event_loop().run_in_executor(None, input, f"   [{label}] Recording... Press ENTER to stop: ")
    stop_event.set()
    recorder.stop()
    recorder.terminate()
    await stream_task
    await ws.send(json.dumps({"type": "stop"}))


async def run():
    token = make_token()
    url = f"{WS_URL}?token={token}"
    loop = asyncio.get_event_loop()

    print(f"\nConnecting to {WS_URL} ...")
    async with websockets.connect(url) as ws:
        print("Connected.\n")
        print("=" * 60)
        print("VOICE INTERRUPT DEMO")
        print("=" * 60)
        print("Step 1: Speak your first question.")
        print("Step 2: Watch the agent start responding.")
        print("Step 3: Script AUTO-INTERRUPTS after first words.")
        print("Step 4: Speak your second question.")
        print("Step 5: Hear the agent respond to the second question.")
        print("=" * 60 + "\n")

        # ── Receive events in background ─────────────────────────────────
        audio_chunks: list[bytes] = []
        first_delta_event = asyncio.Event()
        done_event = asyncio.Event()

        async def receive_loop():
            async for raw in ws:
                msg = json.loads(raw)
                event = msg.get("event")
                data = msg.get("data", {})

                if event == "session":
                    print(f"[session] {data.get('session_id')}")
                elif event == "recording":
                    print(f"[recording] {data.get('status')}")
                elif event == "transcribing":
                    print("[transcribing] ...")
                elif event == "transcript":
                    print(f"[transcript] {data.get('text')!r}")
                elif event == "agent_start":
                    print("[agent] ", end="", flush=True)
                elif event == "agent_delta":
                    sys.stdout.write(data.get("text", ""))
                    sys.stdout.flush()
                    first_delta_event.set()  # signal: agent has started
                elif event == "agent_done":
                    print("\n[agent done]")
                elif event == "audio_delta":
                    audio_chunks.append(base64.b64decode(data.get("audio", "")))
                    sys.stdout.write(f"\r[audio] {sum(len(c) for c in audio_chunks)} bytes")
                    sys.stdout.flush()
                elif event == "tts_done":
                    print("\n[tts done]")
                    done_event.set()
                elif event == "state":
                    print(f"\n[state] {data.get('status')}")
                elif event == "error":
                    print(f"\n[error] {data.get('message')}")
                    done_event.set()

        recv_task = asyncio.create_task(receive_loop())

        try:
            # ── STEP 1: First question ────────────────────────────────────
            print(">> STEP 1: Speak your first question.\n")
            await record_and_send(ws, loop, "Question 1")

            # Wait for agent to start responding
            print("\n   Waiting for agent to start (vibe agent may take 30-60s)...")
            await asyncio.wait_for(first_delta_event.wait(), timeout=90)

            # Small delay so a few words stream in (makes demo more visible)
            await asyncio.sleep(1.5)

            # ── STEP 2: AUTO-INTERRUPT ────────────────────────────────────
            print("\n\n*** AUTO-INTERRUPT — pressing mic! ***\n")
            await ws.send(json.dumps({"type": "interrupt"}))
            audio_chunks.clear()  # discard first response audio

            # Small pause so server processes the interrupt
            await asyncio.sleep(0.3)

            # ── STEP 3: Second question ───────────────────────────────────
            print(">> STEP 3: Speak your second question.\n")
            first_delta_event.clear()
            done_event.clear()
            await record_and_send(ws, loop, "Question 2")

            print("\n   Waiting for agent + TTS...")
            await asyncio.wait_for(done_event.wait(), timeout=60)

            # Play second response audio
            if audio_chunks:
                total = sum(len(c) for c in audio_chunks)
                print(f"\n[audio] {total} bytes — playing ...")
                play_mp3(audio_chunks)
                print("[audio] done")
            else:
                print("[audio] no audio (check ELEVENLABS_API_KEY)")

            print("\n✓ Voice interrupt demo complete!\n")

        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
        finally:
            recv_task.cancel()


if __name__ == "__main__":
    asyncio.run(run())
