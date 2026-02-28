import os
import json
import time
import uuid
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

import jwt
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from python.audio_processor import VoxtralAudioProcessor
from python.vibe_executor import VibeExecutor

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ISSUER = os.environ.get("JWT_ISSUER", "voice-agent-api")

# Optional HTTP endpoints — override the built-in Vibe bridge
COMMAND_MODEL_URL = os.environ.get("COMMAND_MODEL_URL")
AGENT_MODEL_URL = os.environ.get("AGENT_MODEL_URL")

# ---------------------------------------------------------------------------
# Sessions  (swap to Redis for multi-instance deployments)
# ---------------------------------------------------------------------------
SESSIONS: Dict[str, Dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Singletons — None at module-load so tests can monkeypatch before startup.
# Created inside lifespan on real server start.
# ---------------------------------------------------------------------------
audio_processor: Optional[VoxtralAudioProcessor] = None
vibe_executor: Optional[VibeExecutor] = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize heavy singletons on startup; teardown on shutdown."""
    global audio_processor, vibe_executor
    if audio_processor is None:   # tests inject a fake before startup
        audio_processor = VoxtralAudioProcessor()
    if vibe_executor is None:
        vibe_executor = VibeExecutor()
    yield


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

                if payload.get("type") == "control":
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
) -> None:
    """
    Called when Voxtral produces a final transcript for an utterance.

    1. Emit final_transcript event to the client
    2. Extract a structured command (NLU)
    3. Stream the Mistral Vibe CLI response back as agent_delta events
    """
    session["turns"].append(
        {"role": "user", "text": final_text, "ts": int(time.time())}
    )
    await ws_send(websocket, "final_transcript", {"text": final_text})

    # Step 1: Extract structured command
    cmd = await extract_command(final_text, session_id=session["session_id"])
    await ws_send(websocket, "command", cmd)

    # Step 2: Stream Vibe CLI / agent response
    agent_parts: list[str] = []
    try:
        async for delta_line in run_agent_stream(cmd, session_id=session["session_id"]):
            agent_parts.append(delta_line)
            await ws_send(websocket, "agent_delta", {"text": delta_line})
    except Exception as e:
        await ws_send(websocket, "error", {"message": f"Agent error: {e}"})

    session["turns"].append(
        {"role": "assistant", "text": "\n".join(agent_parts), "ts": int(time.time())}
    )


async def extract_command(text: str, session_id: str) -> Dict[str, Any]:
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


async def run_agent_stream(cmd: Dict[str, Any], session_id: str):
    """
    Yield text lines from the agent.

    If AGENT_MODEL_URL is set → single HTTP call, yield one line.
    Otherwise → stream Mistral Vibe CLI output line-by-line.
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

    # Build command text for the Vibe CLI
    intent = cmd.get("intent", "chat")
    args = cmd.get("args", {})
    if intent == "chat":
        command_text = args.get("text", "")
    else:
        args_str = " ".join(f"--{k} {v}" for k, v in args.items())
        command_text = f"{intent} {args_str}".strip()

    async for line in vibe_executor.execute(command_text, session_id=session_id):
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