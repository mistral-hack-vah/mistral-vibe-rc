import os
import json
import time
import uuid
import asyncio
from typing import Dict, Any, Optional

import jwt
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from python.audio_processor import AudioProcessor

# -----------------------------
# Config
# -----------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ISSUER = os.environ.get("JWT_ISSUER", "voice-agent-api")

# Your deployed model endpoints (internal services)
# - ASR is local here (whisper), but agent/LLM should be remote for scaling.
COMMAND_MODEL_URL = os.environ.get("COMMAND_MODEL_URL")  # optional
AGENT_MODEL_URL = os.environ.get("AGENT_MODEL_URL")      # optional

app = FastAPI(
    title="Real-Time Voice Agent",
    description="Real-time audio -> transcript -> command -> agent response"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Sessions (swap to Redis later)
# -----------------------------
SESSIONS: Dict[str, Dict[str, Any]] = {}  # session_id -> session dict


def verify_jwt(token: str) -> str:
    """Return user_id (sub) if token valid, else raise."""
    payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], issuer=JWT_ISSUER)
    return payload["sub"]


async def call_http_json(url: str, payload: Dict[str, Any], timeout: float = 60.0) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()


# -----------------------------
# Load whisper model via your AudioProcessor
# -----------------------------
# You already have this; keep it. Internally, make AudioProcessor do:
# - bytes -> PCM float32
# - VAD + buffering
# - whisper decode on rolling window
audio_processor = AudioProcessor()  # let it load model inside, or pass model


# -----------------------------
# WS protocol helpers
# -----------------------------
async def ws_send(websocket: WebSocket, event: str, data: Dict[str, Any]):
    await websocket.send_text(json.dumps({"event": event, "data": data}))


# -----------------------------
# WebSocket endpoint (single definition!)
# -----------------------------
@app.websocket("/ws/audio")
async def ws_audio(websocket: WebSocket):
    """
    Real-time audio streaming endpoint.

    Auth:
      - Pass JWT as query: /ws/audio?token=...
        OR as header: Authorization: Bearer <token>

    Client sends:
      - binary frames: raw PCM16 mono 16k OR Opus etc (match your AudioProcessor)
      - text frames: JSON {"type":"control", ...} for start/stop/reset, etc.

    Server sends:
      - {"event":"partial_transcript", "data":{"text":...}}
      - {"event":"final_transcript", "data":{"text":...}}
      - {"event":"command", "data":{...}}
      - {"event":"agent_delta", "data":{"text":...}}  (if you stream agent)
    """
    # ---- Authenticate
    token = websocket.query_params.get("token")
    if not token:
        auth = websocket.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()

    if not token:
        await websocket.close(code=4401)
        return

    try:
        user_id = verify_jwt(token)
    except Exception:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    # ---- Session init
    session_id = websocket.query_params.get("session_id") or str(uuid.uuid4())
    session = SESSIONS.get(session_id)
    if not session:
        session = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": int(time.time()),
            "turns": [],
        }
        SESSIONS[session_id] = session
    elif session["user_id"] != user_id:
        await websocket.close(code=4403)
        return

    await ws_send(websocket, "session", {"session_id": session_id})

    # ---- Real-time loop
    try:
        while True:
            msg = await websocket.receive()

            # Text control messages
            if msg.get("text") is not None:
                try:
                    payload = json.loads(msg["text"])
                except Exception:
                    await ws_send(websocket, "error", {"message": "Invalid JSON control message"})
                    continue

                if payload.get("type") == "control":
                    action = payload.get("action")
                    if action == "reset":
                        audio_processor.reset(session_id=session_id)
                        await ws_send(websocket, "state", {"status": "reset"})
                    elif action == "stop":
                        # force finalize any buffered speech
                        final_text = await audio_processor.finalize(session_id=session_id)
                        if final_text:
                            await handle_final_text(websocket, session, final_text)
                        await ws_send(websocket, "state", {"status": "stopped"})
                    else:
                        await ws_send(websocket, "state", {"status": "unknown_control", "action": action})
                else:
                    await ws_send(websocket, "error", {"message": "Unknown message type"})
                continue

            # Binary audio frames
            if msg.get("bytes") is not None:
                audio_chunk = msg["bytes"]

                # process_audio should return dict like:
                # {
                #   "partial": "some text" or None,
                #   "final": "final text" or None
                # }

                # inside ws loop receiving bytes...
                out = await audio_processor.process_audio(audio_chunk, session_id=session_id)

                partial = out.get("partial")
                if partial:
                    await websocket.send_text(json.dumps({"event": "partial_transcript", "text": partial}))

                final = out.get("final")
                if final:
                    await websocket.send_text(json.dumps({"event": "final_transcript", "text": final}))

    except WebSocketDisconnect:
        # normal close
        return
    except Exception as e:
        await ws_send(websocket, "error", {"message": str(e)})
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# -----------------------------
# Final transcript -> command -> agent
# -----------------------------
async def handle_final_text(websocket: WebSocket, session: Dict[str, Any], final_text: str):
    session["turns"].append({"role": "user", "text": final_text, "ts": int(time.time())})
    await ws_send(websocket, "final_transcript", {"text": final_text})

    # 1) Extract structured command (either local heuristic or model)
    cmd = await extract_command(final_text, session_id=session["session_id"])
    await ws_send(websocket, "command", cmd)

    # 2) Run agent/model to produce response
    response_text = await run_agent(cmd, session_id=session["session_id"])
    session["turns"].append({"role": "assistant", "text": response_text, "ts": int(time.time())})
    await ws_send(websocket, "agent_delta", {"text": response_text})


async def extract_command(text: str, session_id: str) -> Dict[str, Any]:
    # If you have a command model deployed, call it.
    if COMMAND_MODEL_URL:
        payload = {
            "session_id": session_id,
            "text": text,
            "schema": {
                "intent": "string",
                "args": "object"
            }
        }
        return await call_http_json(COMMAND_MODEL_URL, payload)

    # Fallback heuristic (replace later)
    t = text.lower()
    if "run tests" in t:
        return {"intent": "run_tests", "args": {"target": "all"}}
    if "build" in t:
        return {"intent": "build", "args": {}}
    return {"intent": "chat", "args": {"text": text}}


async def run_agent(cmd: Dict[str, Any], session_id: str) -> str:
    # If you have an agent model deployed, call it.
    if AGENT_MODEL_URL:
        payload = {"session_id": session_id, "command": cmd}
        data = await call_http_json(AGENT_MODEL_URL, payload)
        return data.get("output_text", "")

    # Fallback stub
    return f"[stub-agent] Received intent={cmd.get('intent')} args={cmd.get('args')}"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)