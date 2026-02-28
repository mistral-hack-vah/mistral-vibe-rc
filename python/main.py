import os
import sys
import json
import time
import uuid
import asyncio
import traceback
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

import jwt
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from simple_acp_client.sdk.client import (
    PyACPSDKClient,
    PyACPAgentOptions,
    TextBlock,
    ResultMessage,
)

from python.audio_processor import VoxtralAudioProcessor
from python.vibe_executor import VibeExecutor

# ACP subprocess transport is broken on Windows — use vibe -p there instead.
USE_ACP = sys.platform != "win32"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ISSUER = os.environ.get("JWT_ISSUER", "voice-agent-api")

# Optional HTTP endpoints — override the built-in Vibe bridge
COMMAND_MODEL_URL = os.environ.get("COMMAND_MODEL_URL")
AGENT_MODEL_URL = os.environ.get("AGENT_MODEL_URL")

# Uploads
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Sessions  (swap to Redis for multi-instance deployments)
# ---------------------------------------------------------------------------
SESSIONS: Dict[str, Dict[str, Any]] = {}

# One persistent ACP client per session — maintains conversation history.
ACP_CLIENTS: Dict[str, PyACPSDKClient] = {}

# ---------------------------------------------------------------------------
# Singletons — None at module-load so tests can monkeypatch before startup.
# Created inside lifespan on real server start.
# ---------------------------------------------------------------------------
audio_processor: Optional[VoxtralAudioProcessor] = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize heavy singletons on startup; teardown on shutdown."""
    from dotenv import load_dotenv
    load_dotenv()
    global audio_processor
    if audio_processor is None:   # tests inject a fake before startup
        audio_processor = VoxtralAudioProcessor()
    yield
    # Disconnect all ACP clients on shutdown
    for client in list(ACP_CLIENTS.values()):
        try:
            await client.disconnect()
        except Exception:
            pass
    ACP_CLIENTS.clear()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Mistral Vibe — Voice Agent API",
    description="Real-time audio → Voxtral STT → Mistral Vibe CLI",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Save an uploaded file and return its public URL."""
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] if file.filename else ".bin"
    safe_name = f"{file_id}{ext}"
    dest_path = os.path.join(UPLOAD_DIR, safe_name)

    with open(dest_path, "wb") as f:
        f.write(await file.read())

    # In production, this should use the absolute public domain.
    # For local testing, we assume the client knows the host.
    return {"url": f"/uploads/{safe_name}"}

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------
def verify_jwt(token: str) -> str:
    """Return user_id (sub claim) if the token is valid, else raise."""
    payload = jwt.decode(
        token, JWT_SECRET, algorithms=["HS256"], issuer=JWT_ISSUER
    )
    return payload["sub"]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
async def call_http_json(
    url: str, payload: Dict[str, Any], timeout: float = 60.0
) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------------
# WebSocket send helper
# ---------------------------------------------------------------------------
async def ws_send(websocket: WebSocket, event: str, data: Dict[str, Any]) -> None:
    await websocket.send_text(json.dumps({"event": event, "data": data}))


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------
@app.websocket("/ws/audio")
async def ws_audio(websocket: WebSocket):
    """
    Real-time audio streaming endpoint.

    Auth
    ----
    Pass a JWT either as a query parameter:  /ws/audio?token=<JWT>
    or as an HTTP header:                    Authorization: Bearer <JWT>

    Client → Server frames
    ----------------------
    Binary  — raw PCM16 mono 16 kHz audio chunk
    Text    — JSON control message:
                {"type": "control", "action": "reset"}   # discard buffer
                {"type": "control", "action": "stop"}    # flush + finalize

    Server → Client events
    ----------------------
    {"event": "session",            "data": {"session_id": "..."}}
    {"event": "partial_transcript", "data": {"text": "..."}}
    {"event": "final_transcript",   "data": {"text": "..."}}
    {"event": "command",            "data": {"intent": "...", "args": {...}}}
    {"event": "agent_delta",        "data": {"text": "..."}}
    {"event": "state",              "data": {"status": "reset"|"stopped"|...}}
    {"event": "error",              "data": {"message": "..."}}
    """

    # ---- Authenticate -------------------------------------------------------
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if not token:
        await websocket.close(code=4401)
        return

    try:
        user_id = verify_jwt(token)
    except Exception:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    # ---- Session ------------------------------------------------------------
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

    # ---- Real-time loop -----------------------------------------------------
    try:
        while True:
            msg = await websocket.receive()

            # ----------------------------------------------------------------
            # Text frame → control message
            # ----------------------------------------------------------------
            if msg.get("text") is not None:
                try:
                    payload = json.loads(msg["text"])
                except Exception:
                    await ws_send(websocket, "error", {"message": "Invalid JSON"})
                    continue

                if payload.get("type") == "init":
                    # Send history if session was recovered
                    await ws_send(websocket, "history", {"turns": session["turns"]})
                    await ws_send(websocket, "state", {"status": "initialized"})

                elif payload.get("type") == "message":
                    # Manually sent text message (+ optional images)
                    text = payload.get("text", "")
                    image_uris = payload.get("image_uris", [])
                    if text or image_uris:
                        # Emits command + agent_delta events
                        await handle_final_text(websocket, session, text, image_uris=image_uris)

                elif payload.get("type") == "interrupt":
                    # Request to stop agent stream
                    if USE_ACP:
                        client = await get_or_create_acp_client(session_id)
                        # PyACPSDKClient might need an interrupt method if supported
                        # For now, we'll just track it to stop the loop in run_agent_stream if possible
                        session["interrupted"] = True
                    await ws_send(websocket, "state", {"status": "interrupted"})

                elif payload.get("type") == "control":
                    action = payload.get("action")
                    if action == "reset":
                        audio_processor.reset(session_id=session_id)
                        await ws_send(websocket, "state", {"status": "reset"})
                    elif action == "stop":
                        final_text = await audio_processor.finalize(session_id=session_id)
                        if final_text:
                            await handle_final_text(websocket, session, final_text)
                        await ws_send(websocket, "state", {"status": "stopped"})
                    else:
                        await ws_send(
                            websocket, "state",
                            {"status": "unknown_control", "action": action}
                        )
                else:
                    await ws_send(websocket, "error", {"message": "Unknown message type"})
                continue

            # ----------------------------------------------------------------
            # Binary frame → audio chunk
            # ----------------------------------------------------------------
            if msg.get("bytes") is not None:
                audio_chunk: bytes = msg["bytes"]
                out = await audio_processor.process_audio(
                    audio_chunk, session_id=session_id
                )

                partial = out.get("partial")
                if partial:
                    await ws_send(websocket, "partial_transcript", {"text": partial})

                final = out.get("final")
                if final:
                    # Emits final_transcript + command + agent_delta events
                    await handle_final_text(websocket, session, final)

    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await ws_send(websocket, "error", {"message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Pipeline: final transcript → NLU command → Vibe CLI
# ---------------------------------------------------------------------------

async def handle_final_text(
    websocket: WebSocket,
    session: Dict[str, Any],
    final_text: str,
    image_uris: Optional[list[str]] = None,
) -> None:
    """
    Called when Voxtral produces a final transcript OR a manual message is sent.

    1. Emit final_transcript event to the client
    2. Extract a structured command (NLU)
    3. Stream the Mistral Vibe CLI response back as agent_delta events
    """
    image_uris = image_uris or []
    session["turns"].append(
        {
            "role": "user",
            "text": final_text,
            "image_uris": image_uris,
            "ts": int(time.time())
        }
    )
    if final_text:
        await ws_send(websocket, "final_transcript", {"text": final_text})

    # Reset interruption flag for new utterance
    session["interrupted"] = False

    # Step 1: Extract structured command
    cmd = await extract_command(
        final_text,
        session_id=session["session_id"],
        image_uris=image_uris
    )
    await ws_send(websocket, "command", cmd)

    # Step 2: Stream Vibe CLI / agent response
    agent_parts: list[str] = []
    try:
        async for delta in run_agent_stream(cmd, session_id=session["session_id"]):
            if session.get("interrupted"):
                break
            
            if isinstance(delta, str):
                agent_parts.append(delta)
                await ws_send(websocket, "agent_delta", {"text": delta})
            elif isinstance(delta, dict) and delta.get("type") == "audio":
                # Forward binary audio delta from agent (e.g. NineLabs/ElevenLabs)
                await ws_send(websocket, "audio_delta", {"data": delta.get("data")})
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Agent Error]\n{tb}", flush=True)
        await ws_send(websocket, "error", {"message": f"Agent error: {type(e).__name__}: {e}"})

    full_agent_text = "\n".join(agent_parts)
    if full_agent_text:
        session["turns"].append(
            {"role": "assistant", "text": full_agent_text, "ts": int(time.time())}
        )


async def extract_command(
    text: str,
    session_id: str,
    image_uris: Optional[list[str]] = None
) -> Dict[str, Any]:
    """
    Convert a raw transcript into a structured command dict.

    Uses COMMAND_MODEL_URL if configured, otherwise a keyword heuristic.
    """
    if COMMAND_MODEL_URL:
        return await call_http_json(
            COMMAND_MODEL_URL,
            {
                "session_id": session_id,
                "text": text,
                "image_uris": image_uris or [],
                "schema": {"intent": "string", "args": "object"},
            },
        )

    t = text.lower()
    if "run test" in t or "run the test" in t:
        return {"intent": "run_tests", "args": {"target": "all"}}
    if "build" in t:
        return {"intent": "build", "args": {}}
    if "deploy" in t:
        return {"intent": "deploy", "args": {}}
    if "status" in t or "what" in t:
        return {"intent": "status", "args": {}}
    return {"intent": "chat", "args": {"text": text}}


async def get_or_create_acp_client(session_id: str) -> PyACPSDKClient:
    """Return the persistent ACP client for this session, creating it if needed."""
    if session_id not in ACP_CLIENTS:
        options = PyACPAgentOptions(
            cwd=os.getcwd(),
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        client = PyACPSDKClient(options)
        # Connect to 'strand' agent via vibe-acp
        await client.connect(["vibe-acp", "strand"])
        ACP_CLIENTS[session_id] = client
    return ACP_CLIENTS[session_id]


async def run_agent_stream(cmd: Dict[str, Any], session_id: str):
    """
    Yield agent response parts (text lines or audio chunks).

    If AGENT_MODEL_URL is set → single HTTP call, yield one line.
    Otherwise → stream via simple-acp-client connected to vibe-acp.
    """
    if AGENT_MODEL_URL:
        data = await call_http_json(
            AGENT_MODEL_URL,
            {"session_id": session_id, "command": cmd},
        )
        output = data.get("output_text", "")
        if output:
            yield output
        return

    # Pass the original spoken text directly — vibe understands natural language
    command_text = cmd.get("args", {}).get("text") or cmd.get("intent", "")

    if USE_ACP:
        client = await get_or_create_acp_client(session_id)
        await client.query(command_text)
        async for message in client.receive_messages():
            if isinstance(message, TextBlock) and message.text:
                yield message.text
            # Forward audio blocks if supported by the SDK
            elif hasattr(message, "audio") and message.audio:
                yield {"type": "audio", "data": message.audio}
    else:
        # Windows fallback: vibe -p (subprocess, no persistent session)
        executor = VibeExecutor()
        async for line in executor.execute(command_text, session_id=session_id):
            yield line


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> Dict[str, str]:
    model = audio_processor.model if audio_processor else "not-initialized"
    return {"status": "ok", "model": model}


# ---------------------------------------------------------------------------
# Entry point (local dev)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("python.main:app", host="0.0.0.0", port=8000, reload=True)