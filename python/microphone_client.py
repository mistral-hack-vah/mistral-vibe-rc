#!/usr/bin/env python3
"""
Push-to-talk microphone client for the Voice Agent API.

Usage:
    python microphone_client.py

Controls:
    Press ENTER to start recording
    Press ENTER again to stop and send to agent
    Press 'q' + ENTER to quit
    Press 'c' + ENTER to cancel current recording
"""

import asyncio
import json
import os
import sys
import time
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
# Client State
# ---------------------------------------------------------------------------
class ClientState:
    def __init__(self):
        self.recording = False
        self.running = True
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.audio_stream: Optional[pyaudio.Stream] = None
        self.pyaudio: Optional[pyaudio.PyAudio] = None


# ---------------------------------------------------------------------------
# Client Logic
# ---------------------------------------------------------------------------
async def push_to_talk_client():
    state = ClientState()
    token = generate_token(USER_ID)
    uri = f"{SERVER_URL}?token={token}"

    print("=" * 60)
    print("  Push-to-Talk Voice Agent Client")
    print("=" * 60)
    print(f"Server: {SERVER_URL}")
    print()
    print("Controls:")
    print("  ENTER     - Start/Stop recording")
    print("  c + ENTER - Cancel recording")
    print("  i + ENTER - Interrupt agent")
    print("  q + ENTER - Quit")
    print("=" * 60)
    print()

    print(f"Connecting to server...")

    try:
        async with websockets.connect(uri) as websocket:
            state.websocket = websocket
            print("Connected!")
            print()

            # Initialize PyAudio
            state.pyaudio = pyaudio.PyAudio()

            async def send_audio():
                """Continuously send audio while recording."""
                try:
                    while state.running:
                        if state.recording and state.audio_stream:
                            try:
                                data = state.audio_stream.read(
                                    CHUNK, exception_on_overflow=False
                                )
                                await websocket.send(data)
                            except Exception as e:
                                if state.recording:
                                    print(f"\n[Audio Error] {e}")
                        await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    pass

            async def receive_messages():
                """Handle incoming messages from server."""
                try:
                    async for message in websocket:
                        data = json.loads(message)
                        event = data.get("event")
                        payload = data.get("data", {})

                        if event == "session":
                            session_id = payload.get("session_id")
                            print(f"[Session] {session_id[:8]}...")
                            # Request history
                            await websocket.send(json.dumps({"type": "init"}))

                        elif event == "history":
                            turns = payload.get("turns", [])
                            if turns:
                                print("\n--- Previous Conversation ---")
                                for turn in turns[-5:]:  # Last 5 turns
                                    role = turn.get("role", "?")
                                    text = turn.get("text", "")[:100]
                                    prefix = "You" if role == "user" else "Agent"
                                    print(f"  {prefix}: {text}")
                                print("-----------------------------\n")

                        elif event == "recording":
                            status = payload.get("status")
                            if status == "started":
                                print("[Recording] Started - speak now...")
                            elif status == "stopped":
                                print("[Recording] Stopped")
                            elif status == "cancelled":
                                print("[Recording] Cancelled")

                        elif event == "transcribing":
                            print("[Transcribing...]")

                        elif event == "transcript_delta":
                            text = payload.get("text", "")
                            print(text, end="", flush=True)

                        elif event == "transcript":
                            text = payload.get("text", "")
                            if text:
                                print(f"\n[You said] {text}")
                            else:
                                print("[No speech detected]")

                        elif event == "agent_start":
                            print("\n[Agent]", end=" ", flush=True)

                        elif event == "agent_delta":
                            text = payload.get("text", "")
                            print(text, end="", flush=True)

                        elif event == "agent_done":
                            print()  # New line after agent response
                            print()
                            print("Press ENTER to record, 'q' to quit")

                        elif event == "error":
                            print(f"\n[Error] {payload.get('message')}")

                        elif event == "state":
                            status = payload.get("status")
                            print(f"[State] {status}")

                except asyncio.CancelledError:
                    pass
                except websockets.exceptions.ConnectionClosed:
                    print("\n[Disconnected]")
                    state.running = False

            async def handle_input():
                """Handle keyboard input for push-to-talk."""
                loop = asyncio.get_event_loop()

                print("Press ENTER to start recording...")
                print()

                while state.running:
                    try:
                        # Read input in a thread to avoid blocking
                        line = await loop.run_in_executor(
                            None, sys.stdin.readline
                        )
                        line = line.strip().lower()

                        if line == "q":
                            print("\nQuitting...")
                            state.running = False
                            break

                        elif line == "c":
                            if state.recording:
                                # Cancel recording
                                state.recording = False
                                if state.audio_stream:
                                    state.audio_stream.stop_stream()
                                    state.audio_stream.close()
                                    state.audio_stream = None
                                await websocket.send(json.dumps({"type": "cancel"}))
                            else:
                                print("Not recording.")

                        elif line == "i":
                            # Interrupt agent
                            await websocket.send(json.dumps({"type": "interrupt"}))

                        else:
                            # Toggle recording
                            if not state.recording:
                                # Start recording
                                state.recording = True
                                state.audio_stream = state.pyaudio.open(
                                    format=FORMAT,
                                    channels=CHANNELS,
                                    rate=RATE,
                                    input=True,
                                    frames_per_buffer=CHUNK,
                                )
                                await websocket.send(json.dumps({"type": "start"}))
                            else:
                                # Stop recording
                                state.recording = False
                                if state.audio_stream:
                                    state.audio_stream.stop_stream()
                                    state.audio_stream.close()
                                    state.audio_stream = None
                                await websocket.send(json.dumps({"type": "stop"}))

                    except Exception as e:
                        print(f"[Input Error] {e}")
                        break

            # Run all tasks concurrently
            tasks = [
                asyncio.create_task(send_audio()),
                asyncio.create_task(receive_messages()),
                asyncio.create_task(handle_input()),
            ]

            try:
                done, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
            finally:
                for task in tasks:
                    task.cancel()

    except websockets.exceptions.ConnectionRefusedError:
        print(f"Could not connect to {SERVER_URL}")
        print("Make sure the server is running:")
        print("  python -m uvicorn python.main:app --reload")
    except Exception as e:
        print(f"Connection error: {e}")
    finally:
        # Cleanup
        if state.audio_stream:
            state.audio_stream.stop_stream()
            state.audio_stream.close()
        if state.pyaudio:
            state.pyaudio.terminate()


if __name__ == "__main__":
    try:
        asyncio.run(push_to_talk_client())
    except KeyboardInterrupt:
        print("\nStopped.")
