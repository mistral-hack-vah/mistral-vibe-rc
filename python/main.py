# python/main.py
"""
Voice Agent API - WebSocket + REST Hybrid Architecture.

REST Endpoints:
    POST /api/session           - Create/recover session
    GET  /api/session/{id}/history - Get conversation history
    POST /api/message           - Send text message (SSE streaming response)
    POST /api/interrupt         - Interrupt current agent stream
    POST /api/upload            - Upload file (image)

WebSocket Endpoint:
    /ws/audio                   - Push-to-talk audio streaming

Audio Format: PCM16 mono 16 kHz
"""

import base64
import json
import os
import traceback
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

import jwt
from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from python.audio_processor import PushToTalkProcessor
from python.schemas import (
    InterruptRequest,
    MessageRequest,
    SessionRequest,
    SessionResponse,
    StatusResponse,
)
from python.strands_agent import get_strands_agent_service
from python.session_manager import session_manager
from python.tts_service import stream_tts


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ISSUER = os.environ.get("JWT_ISSUER", "voice-agent-api")

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------
audio_processor: Optional[PushToTalkProcessor] = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize singletons on startup."""
    from dotenv import load_dotenv

    load_dotenv()

    global audio_processor
    if audio_processor is None:
        audio_processor = PushToTalkProcessor()

    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Mistral Vibe - Voice Agent API",
    description="Real-time audio + REST API for voice-controlled coding assistant",
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
# Auth
# ---------------------------------------------------------------------------
def verify_jwt(token: str) -> str:
    """Return user_id (sub claim) if token is valid, else raise."""
    try:
        payload = jwt.decode(
            token, JWT_SECRET, algorithms=["HS256"], issuer=JWT_ISSUER
        )
        return payload["sub"]
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


async def get_current_user(authorization: str = Header(None)) -> str:
    """Extract user_id from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    else:
        token = authorization

    return verify_jwt(token)



# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/session", response_model=SessionResponse)
async def create_session(
    request: SessionRequest = None,
    user_id: str = Depends(get_current_user),
):
    """Create a new session or recover an existing one."""
    request = request or SessionRequest()
    session = session_manager.get_or_create(request.session_id, user_id)
    return SessionResponse(session_id=session.id, created_at=session.created_at)


@app.get("/api/session/{session_id}/history")
async def get_history(
    session_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get conversation history for a session."""
    try:
        session = session_manager.get(session_id, user_id)
        return {"turns": session.turns}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.post("/api/message")
async def send_message(
    request: MessageRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Send a text message and stream the agent response via SSE.

    Events:
        agent_start: {}
        agent_delta: {text: str}
        agent_done:  {text: str}
        error:       {message: str}
    """
    # Verify session ownership
    try:
        session_manager.get(request.session_id, user_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    async def generate_events() -> AsyncIterator[dict]:
        yield {"event": "agent_start", "data": json.dumps({})}

        full_response = ""
        try:
            async for delta in get_strands_agent_service().stream_response(
                session_id=request.session_id,
                user_message=request.text,
                image_uris=request.image_uris,
            ):
                # Check for interrupt
                if session_manager.is_interrupted(request.session_id):
                    break

                full_response += delta
                yield {"event": "agent_delta", "data": json.dumps({"text": delta})}

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[Agent Error]\n{tb}", flush=True)
            yield {
                "event": "error",
                "data": json.dumps({"message": f"{type(e).__name__}: {e}"}),
            }

        yield {"event": "agent_done", "data": json.dumps({"text": full_response})}

        # Stream TTS audio if response is non-empty
        if full_response.strip() and os.environ.get("ELEVENLABS_API_KEY"):
            try:
                async for chunk in stream_tts(full_response):
                    if session_manager.is_interrupted(request.session_id):
                        break
                    audio_b64 = base64.b64encode(chunk).decode("ascii")
                    yield {
                        "event": "audio_delta",
                        "data": json.dumps({"audio": audio_b64}),
                    }
            except Exception as e:
                print(f"[TTS Error] {e}", flush=True)

    return EventSourceResponse(generate_events())


@app.post("/api/interrupt", response_model=StatusResponse)
async def interrupt_session(
    request: InterruptRequest,
    user_id: str = Depends(get_current_user),
):
    """Interrupt the current agent stream for a session."""
    try:
        session_manager.get(request.session_id, user_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    session_manager.set_interrupted(request.session_id, True)
    return StatusResponse(status="interrupted")


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    """Upload a file and return its URL."""
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] if file.filename else ".bin"
    safe_name = f"{file_id}{ext}"
    dest_path = os.path.join(UPLOAD_DIR, safe_name)

    with open(dest_path, "wb") as f:
        f.write(await file.read())

    return {"url": f"/uploads/{safe_name}"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    model = audio_processor.model if audio_processor else "not-initialized"
    return {"status": "ok", "model": model}


# ---------------------------------------------------------------------------
# WebSocket Helpers
# ---------------------------------------------------------------------------
async def ws_send(websocket: WebSocket, event: str, data: dict[str, Any]) -> None:
    """Send a JSON event to WebSocket client."""
    await websocket.send_text(json.dumps({"event": event, "data": data}))


# ---------------------------------------------------------------------------
# WebSocket Endpoint - Audio Only (Push-to-Talk)
# ---------------------------------------------------------------------------
@app.websocket("/ws/audio")
async def ws_audio(websocket: WebSocket):
    """
    Push-to-talk audio streaming endpoint.

    Auth:
        /ws/audio?token=<JWT>
        or Authorization: Bearer <JWT> header

    Client -> Server (Text - JSON):
        {"type": "start"}     - Begin recording
        {"type": "stop"}      - Stop recording, trigger transcription + agent
        {"type": "cancel"}    - Cancel recording without transcription
        {"type": "interrupt"} - Interrupt agent stream
        {"type": "init"}      - Request session history

    Client -> Server (Binary):
        Raw PCM16 mono 16 kHz audio chunks

    Server -> Client (Text - JSON):
        {"event": "session",      "data": {"session_id": "..."}}
        {"event": "recording",    "data": {"status": "started|stopped|cancelled"}}
        {"event": "transcribing", "data": {}}
        {"event": "transcript",   "data": {"text": "..."}}
        {"event": "agent_start",  "data": {}}
        {"event": "agent_delta",  "data": {"text": "..."}}
        {"event": "agent_done",   "data": {"text": "..."}}
        {"event": "audio_delta",  "data": {"audio": "<base64>"}}
        {"event": "history",      "data": {"turns": [...]}}
        {"event": "state",        "data": {"status": "..."}}
        {"event": "error",        "data": {"message": "..."}}
    """
    # ---- Authenticate ----
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
    except HTTPException:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    # ---- Session ----
    session_id = websocket.query_params.get("session_id") or str(uuid.uuid4())

    try:
        session_manager.get_or_create(session_id, user_id)
    except PermissionError:
        await websocket.close(code=4403)
        return

    await ws_send(websocket, "session", {"session_id": session_id})

    # ---- Main Loop ----
    try:
        while True:
            msg = await websocket.receive()

            # Text frame -> control message
            if msg.get("text") is not None:
                try:
                    payload = json.loads(msg["text"])
                except json.JSONDecodeError:
                    await ws_send(websocket, "error", {"message": "Invalid JSON"})
                    continue

                msg_type = payload.get("type")

                if msg_type == "start":
                    # Begin recording
                    audio_processor.start_recording(session_id)
                    session_manager.clear_interrupted(session_id)
                    await ws_send(websocket, "recording", {"status": "started"})

                elif msg_type == "stop":
                    # Stop recording, transcribe, run agent
                    await ws_send(websocket, "recording", {"status": "stopped"})
                    await ws_send(websocket, "transcribing", {})

                    transcript = await audio_processor.stop_and_transcribe(session_id)

                    if transcript:
                        await ws_send(websocket, "transcript", {"text": transcript})

                        # Stream agent response
                        await ws_send(websocket, "agent_start", {})
                        full_response = ""

                        try:
                            async for delta in get_strands_agent_service().stream_response(
                                session_id=session_id,
                                user_message=transcript,
                            ):
                                if session_manager.is_interrupted(session_id):
                                    break
                                full_response += delta
                                await ws_send(websocket, "agent_delta", {"text": delta})

                        except Exception as e:
                            tb = traceback.format_exc()
                            print(f"[Agent Error]\n{tb}", flush=True)
                            await ws_send(
                                websocket,
                                "error",
                                {"message": f"Agent error: {type(e).__name__}: {e}"},
                            )

                        await ws_send(websocket, "agent_done", {"text": full_response})

                        # Stream TTS audio
                        if full_response.strip() and os.environ.get("ELEVENLABS_API_KEY"):
                            try:
                                async for chunk in stream_tts(full_response):
                                    if session_manager.is_interrupted(session_id):
                                        break
                                    audio_b64 = base64.b64encode(chunk).decode("ascii")
                                    await ws_send(websocket, "audio_delta", {"audio": audio_b64})
                            except Exception as e:
                                print(f"[TTS Error] {e}", flush=True)
                    else:
                        await ws_send(websocket, "transcript", {"text": ""})

                elif msg_type == "cancel":
                    # Cancel recording without transcribing
                    audio_processor.cancel_recording(session_id)
                    await ws_send(websocket, "recording", {"status": "cancelled"})

                elif msg_type == "interrupt":
                    # Interrupt agent stream
                    session_manager.set_interrupted(session_id, True)
                    await ws_send(websocket, "state", {"status": "interrupted"})

                elif msg_type == "init":
                    # Send session history
                    turns = session_manager.get_turns(session_id)
                    await ws_send(websocket, "history", {"turns": turns})

                else:
                    await ws_send(
                        websocket, "error", {"message": f"Unknown type: {msg_type}"}
                    )

            # Binary frame -> audio chunk
            elif msg.get("bytes") is not None:
                audio_chunk: bytes = msg["bytes"]
                audio_processor.append_audio(session_id, audio_chunk)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws_send(websocket, "error", {"message": str(e)})
        except Exception:
            pass
    finally:
        # Clean up recording state on disconnect
        audio_processor.cancel_recording(session_id)
        try:
            await websocket.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("python.main:app", host="0.0.0.0", port=8000, reload=True)
