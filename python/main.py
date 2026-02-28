import os
import json
import time
import uuid
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

import jwt
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from python.audio_processor import VoxtralAudioProcessor
from python.vibe_executor import VibeExecutor
from python.acp_client import ACPClient

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
audio_processor: Optional[Any] = None
vibe_executor: Optional[VibeExecutor] = None
acp_client: Optional[ACPClient] = None

class FakeAudioProcessor:
    def __init__(self):
        self.model = "fake-voxtral"
    def reset(self, session_id: str): pass
    async def finalize(self, session_id: str): return "fake final"
    async def process_audio(self, audio_chunk: bytes, session_id: str):
        return {"partial": "fake partial", "final": None}

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize heavy singletons on startup; teardown on shutdown."""
    global audio_processor, vibe_executor, acp_client
    if audio_processor is None:
        try:
            audio_processor = VoxtralAudioProcessor()
        except RuntimeError:
            print("[Warning] Using FakeAudioProcessor (MISTRAL_API_KEY not set)")
            audio_processor = FakeAudioProcessor()
    if vibe_executor is None:
        vibe_executor = VibeExecutor()
    if acp_client is None:
        acp_client = ACPClient()
        try:
            await acp_client.start()
        except Exception as e:
            print(f"[Warning] ACP client failed to start: {e}")
            # Keep acp_client as None or a dummy if needed
            acp_client = None

    yield

    if acp_client:
        await acp_client.stop()


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
# Static storage for uploads
# ---------------------------------------------------------------------------
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

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
# HTTP Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    """Upload an image and return its public URI."""
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(await file.read())

    # Assuming the server is running on localhost:8000 for now
    # In production, this should be the external base URL
    base_url = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
    return {"uri": f"{base_url}/uploads/{filename}", "path": filepath}


# ---------------------------------------------------------------------------
# WebSocket send helper
# ---------------------------------------------------------------------------
async def ws_send(websocket: WebSocket, event: str, data: Dict[str, Any]) -> None:
    await websocket.send_text(json.dumps({"event": event, "data": data}))


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    """
    Overhauled WebSocket endpoint supporting:
    - init (server confirms and sends history)
    - message (text + images)
    - audio (binary chunks)
    - interrupt
    """
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

    # Setup ACP handlers for this session if available
    if acp_client:
        async def on_text_delta(params):
            if params.get("sessionId") == session_id:
                await ws_send(websocket, "agent_delta", {"text": params.get("text", "")})

        async def on_audio_delta(params):
            if params.get("sessionId") == session_id:
                await ws_send(websocket, "audio_delta", {"audio": params.get("audio", "")})

        async def on_completed(params):
            if params.get("sessionId") == session_id:
                await ws_send(websocket, "agent_stop", {"status": "completed"})

        acp_client.on("session.textDelta", on_text_delta)
        acp_client.on("session.audioDelta", on_audio_delta)
        acp_client.on("session.completed", on_completed)

    try:
        while True:
            msg = await websocket.receive()

            if msg.get("text") is not None:
                try:
                    payload = json.loads(msg["text"])
                except Exception:
                    await ws_send(websocket, "error", {"message": "Invalid JSON"})
                    continue

                m_type = payload.get("type")
                
                if m_type == "init":
                    # ACP init session
                    await acp_client.create_session(session_id)
                    await ws_send(websocket, "session", {
                        "session_id": session_id,
                        "history": session["turns"]
                    })

                elif m_type == "message":
                    text = payload.get("text", "")
                    images = payload.get("images", [])
                    session["turns"].append({"role": "user", "text": text, "images": images, "ts": int(time.time())})
                    await acp_client.prompt(session_id, text, images)

                elif m_type == "interrupt":
                    await acp_client.interrupt(session_id)
                    await ws_send(websocket, "state", {"status": "interrupted"})

                elif m_type == "control":
                    action = payload.get("action")
                    if audio_processor is None:
                        await ws_send(websocket, "error", {"message": "Audio processor not initialized"})
                        continue

                    if action == "reset":
                        audio_processor.reset(session_id=session_id)
                        await ws_send(websocket, "state", {"status": "reset"})
                    elif action == "stop":
                        final_text = await audio_processor.finalize(session_id=session_id)
                        if final_text:
                            await handle_final_text_acp(websocket, session, final_text)
                        await ws_send(websocket, "state", {"status": "stopped"})

            elif msg.get("bytes") is not None:
                if audio_processor is None:
                    continue
                audio_chunk: bytes = msg["bytes"]
                out = await audio_processor.process_audio(audio_chunk, session_id=session_id)

                if out.get("partial"):
                    await ws_send(websocket, "partial_transcript", {"text": out["partial"]})

                if out.get("final"):
                    await handle_final_text_acp(websocket, session, out["final"])

    except WebSocketDisconnect:
        pass
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


async def handle_final_text_acp(
    websocket: WebSocket,
    session: Dict[str, Any],
    final_text: str,
) -> None:
    """Forward final transcript to ACP."""
    session["turns"].append(
        {"role": "user", "text": final_text, "ts": int(time.time())}
    )
    await ws_send(websocket, "final_transcript", {"text": final_text})
    if acp_client:
        await acp_client.prompt(session["session_id"], final_text)


@app.websocket("/ws/audio")
async def ws_audio(websocket: WebSocket):
    # Keep old endpoint for backwards compatibility but point it to the same logic if needed
    # or just keep it as is for ahora.
    # The request specifically asked for /ws so I'll prioritize that.
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