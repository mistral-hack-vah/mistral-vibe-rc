"""
tests/manual_e2e_test.py — Full end-to-end CLI test
=====================================================
Tests the complete pipeline:
  mic → WebSocket → transcription → Mistral agent → ElevenLabs TTS → audio file

Requires the backend to be running:
    uv run python -m uvicorn python.main:app --host 0.0.0.0 --port 8000

Run with:
    uv run python tests/manual_e2e_test.py
"""

import asyncio
import base64
import ctypes
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
import json

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
WS_URL = os.environ.get("BACKEND_WS_URL", "ws://localhost:8000/ws/audio")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ISSUER = os.environ.get("JWT_ISSUER", "voice-agent-api")

RATE = 16_000
CHANNELS = 1
CHUNK = 1024
FORMAT = pyaudio.paInt16


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def make_token() -> str:
    payload = {
        "sub": "cli-test-user",
        "iss": JWT_ISSUER,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


# ---------------------------------------------------------------------------
# Mic recording (runs in a background thread)
# ---------------------------------------------------------------------------
class MicRecorder:
    def __init__(self, on_chunk):
        self._on_chunk = on_chunk
        self._recording = False
        self._thread = None
        self._pa = pyaudio.PyAudio()

    def start(self):
        self._recording = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._recording = False
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self):
        stream = self._pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )
        try:
            while self._recording:
                data = stream.read(CHUNK, exception_on_overflow=False)
                self._on_chunk(data)
        finally:
            stream.stop_stream()
            stream.close()

    def terminate(self):
        self._pa.terminate()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def run():
    token = make_token()
    url = f"{WS_URL}?token={token}"

    print(f"\nConnecting to {WS_URL} ...")

    audio_chunks: list[bytes] = []
    loop = asyncio.get_event_loop()

    async with websockets.connect(url) as ws:
        print("Connected.\n")

        # ---- Receive events in background ----
        done = asyncio.Event()
        full_response = []

        async def receive_loop():
            async for raw in ws:
                msg = json.loads(raw)
                event = msg.get("event")
                data = msg.get("data", {})

                if event == "session":
                    print(f"[session] id={data.get('session_id')}")

                elif event == "recording":
                    print(f"[recording] {data.get('status')}")

                elif event == "transcribing":
                    print("[transcribing] ...")

                elif event == "transcript":
                    text = data.get("text", "")
                    print(f"[transcript] {text!r}")

                elif event == "agent_start":
                    print("[agent] ", end="", flush=True)

                elif event == "agent_delta":
                    sys.stdout.write(data.get("text", ""))
                    sys.stdout.flush()
                    full_response.append(data.get("text", ""))

                elif event == "agent_done":
                    print("\n[agent done]")
                    if not os.environ.get("ELEVENLABS_API_KEY"):
                        done.set()  # no TTS coming, we're done

                elif event == "audio_delta":
                    chunk = base64.b64decode(data.get("audio", ""))
                    audio_chunks.append(chunk)
                    sys.stdout.write(f"\r[audio] received {sum(len(c) for c in audio_chunks)} bytes of MP3")
                    sys.stdout.flush()

                elif event == "tts_done":
                    print(f"\n[tts done]")
                    done.set()

                elif event == "error":
                    print(f"\n[error] {data.get('message')}")
                    done.set()

        recv_task = asyncio.create_task(receive_loop())

        # ---- Push-to-talk loop ----
        print("Press ENTER to start recording. Press ENTER again to send. Ctrl+C to quit.\n")

        try:
            while True:
                await asyncio.get_event_loop().run_in_executor(
                    None, input, ">> Press ENTER to record: "
                )

                # Start recording
                audio_chunks.clear()
                done.clear()
                full_response.clear()
                await ws.send(json.dumps({"type": "start"}))

                send_queue: asyncio.Queue = asyncio.Queue()

                def on_chunk(data):
                    loop.call_soon_threadsafe(send_queue.put_nowait, data)

                recorder = MicRecorder(on_chunk=on_chunk)
                recorder.start()
                print("   Recording... Press ENTER to stop.")

                # Wait for stop signal while streaming audio
                stop_event = asyncio.Event()

                async def stream_audio():
                    while not stop_event.is_set():
                        try:
                            chunk = await asyncio.wait_for(send_queue.get(), timeout=0.1)
                            await ws.send(chunk)
                        except asyncio.TimeoutError:
                            continue

                stream_task = asyncio.create_task(stream_audio())

                await asyncio.get_event_loop().run_in_executor(None, input, "")
                stop_event.set()
                recorder.stop()
                recorder.terminate()
                await stream_task

                # Tell server to transcribe + respond
                await ws.send(json.dumps({"type": "stop"}))

                # Wait for agent + TTS to finish
                print("   Waiting for agent response + TTS...")
                await asyncio.wait_for(done.wait(), timeout=60)

                # Play audio directly through speakers
                if audio_chunks:
                    total = sum(len(c) for c in audio_chunks)
                    print(f"\n[audio] {total} bytes — playing through speakers ...")
                    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                    for c in audio_chunks:
                        tmp.write(c)
                    tmp.close()

                    # Play via Windows winmm — no media player window, blocks until done
                    mci = ctypes.windll.winmm
                    mci.mciSendStringW(f'open "{tmp.name}" type mpegvideo alias tts', None, 0, None)
                    mci.mciSendStringW('play tts wait', None, 0, None)
                    mci.mciSendStringW('close tts', None, 0, None)
                    os.unlink(tmp.name)
                    print("[audio] done")
                else:
                    print("[audio] no audio received — check ELEVENLABS_API_KEY and server logs")

                print()

        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
        finally:
            recv_task.cancel()


if __name__ == "__main__":
    asyncio.run(run())
