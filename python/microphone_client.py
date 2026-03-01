import asyncio
import json
import os
import signal
import sys
import time
import wave
from typing import Optional

import jwt
import pyaudio
import websockets

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SERVER_URL = os.environ.get("SERVER_URL", "ws://127.0.0.1:8000/ws/audio")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ISSUER = os.environ.get("JWT_ISSUER", "voice-agent-api")
USER_ID = os.environ.get("USER_ID", "local-mic-user")

# Audio settings
CHANNELS = 1
RATE = 16000
CHUNK = 1024  # frames per buffer
FORMAT = pyaudio.paInt16

# ---------------------------------------------------------------------------
# Auth Helper
# ---------------------------------------------------------------------------
def generate_token(user_id: str) -> str:
    now = int(time.time())
    payload = {
        "iss": JWT_ISSUER,
        "sub": user_id,
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

# ---------------------------------------------------------------------------
# Client Logic
# ---------------------------------------------------------------------------
async def stream_microphone():
    token = generate_token(USER_ID)
    uri = f"{SERVER_URL}?token={token}"

    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Listening... (Ctrl+C to stop)")

            # Start the microphone stream
            p = pyaudio.PyAudio()
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )

            async def send_audio():
                try:
                    while True:
                        data = stream.read(CHUNK, exception_on_overflow=False)
                        await websocket.send(data)
                        await asyncio.sleep(0)  # yield control
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"\n[Microphone Error] {e}")
                finally:
                    stream.stop_stream()
                    stream.close()
                    p.terminate()

            async def receive_messages():
                try:
                    async for message in websocket:
                        data = json.loads(message)
                        event = data.get("event")
                        payload = data.get("data", {})

                        if event == "session":
                            session_id = payload.get("session_id")
                            print(f"\n[Session Started] ID: {session_id}")
                            # Send init to get history
                            await websocket.send(json.dumps({"type": "init"}))
                        elif event == "history":
                            turns = payload.get("turns", [])
                            if turns:
                                print("\n--- Session History ---")
                                for turn in turns:
                                    role = turn.get("role")
                                    text = turn.get("text")
                                    print(f"[{role}] {text}")
                                print("-----------------------\n")
                        elif event == "partial_transcript":
                            # Print partials on the same line to show "live" updates
                            sys.stdout.write(f"\rPartial: {payload.get('text')}... ")
                            sys.stdout.flush()
                        elif event == "final_transcript":
                            print(f"\n[Final Transcript] {payload.get('text')}")
                        elif event == "command":
                            intent = payload.get("intent")
                            args = payload.get("args")
                            print(f"[Command Detected] Intent: {intent}, Args: {args}")
                        elif event == "agent_delta":
                            print(f"[Agent] {payload.get('text')}")
                        elif event == "error":
                            print(f"\n[Server Error] {payload.get('message')}")
                        elif event == "state":
                            print(f"\n[Server State] {payload.get('status')}")
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"\n[Receiver Error] {e}")

            # Run both send and receive concurrently
            send_task = asyncio.create_task(send_audio())
            receive_task = asyncio.create_task(receive_messages())

            # Wait for either to finish (or Ctrl+C)
            done, pending = await asyncio.wait(
                [send_task, receive_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()

    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    # Handle Ctrl+C gracefully
    try:
        asyncio.run(stream_microphone())
    except KeyboardInterrupt:
        print("\nStopping...")
