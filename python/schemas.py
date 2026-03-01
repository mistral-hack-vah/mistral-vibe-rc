"""
Wire protocol schemas for WebSocket and REST communication.

All messages between client ↔ server are defined here as Pydantic models.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Client → Server (WebSocket control messages)
# ---------------------------------------------------------------------------
class WsControlMessage(BaseModel):
    """JSON text frame sent from client to server over WebSocket."""

    type: Literal["start", "stop", "cancel", "interrupt", "init", "mode"]
    mode: Optional[str] = None  # only for type="mode"


# ---------------------------------------------------------------------------
# Server → Client (WebSocket / SSE events)
# ---------------------------------------------------------------------------
class SessionEvent(BaseModel):
    event: Literal["session"] = "session"
    data: SessionData


class SessionData(BaseModel):
    session_id: str


class RecordingEvent(BaseModel):
    event: Literal["recording"] = "recording"
    data: RecordingData


class RecordingData(BaseModel):
    status: Literal["started", "stopped", "cancelled"]


class TranscribingEvent(BaseModel):
    event: Literal["transcribing"] = "transcribing"
    data: dict[str, Any] = {}


class TranscriptDeltaEvent(BaseModel):
    event: Literal["transcript_delta"] = "transcript_delta"
    data: TranscriptDeltaData


class TranscriptDeltaData(BaseModel):
    text: str


class TranscriptEvent(BaseModel):
    event: Literal["transcript"] = "transcript"
    data: TranscriptData


class TranscriptData(BaseModel):
    text: str


class AgentStartEvent(BaseModel):
    event: Literal["agent_start"] = "agent_start"
    data: dict[str, Any] = {}


class AgentDeltaEvent(BaseModel):
    event: Literal["agent_delta"] = "agent_delta"
    data: AgentDeltaData


class AgentDeltaData(BaseModel):
    text: str


class AgentDoneEvent(BaseModel):
    event: Literal["agent_done"] = "agent_done"
    data: AgentDoneData


class AgentDoneData(BaseModel):
    text: str


class AudioDeltaEvent(BaseModel):
    event: Literal["audio_delta"] = "audio_delta"
    data: AudioDeltaData


class AudioDeltaData(BaseModel):
    audio: str  # base64-encoded audio bytes


class HistoryEvent(BaseModel):
    event: Literal["history"] = "history"
    data: HistoryData


class HistoryData(BaseModel):
    turns: list[dict[str, Any]]


class ErrorEvent(BaseModel):
    event: Literal["error"] = "error"
    data: ErrorData


class ErrorData(BaseModel):
    message: str


class StateEvent(BaseModel):
    event: Literal["state"] = "state"
    data: StateData


class StateData(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# REST Request/Response Models
# ---------------------------------------------------------------------------
class SessionRequest(BaseModel):
    session_id: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    created_at: int


class MessageRequest(BaseModel):
    session_id: str
    text: str
    image_uris: list[str] = []


class InterruptRequest(BaseModel):
    session_id: str


class StatusResponse(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Union of all server events (for JSON schema export)
# ---------------------------------------------------------------------------
ServerEvent = (
    SessionEvent
    | RecordingEvent
    | TranscribingEvent
    | TranscriptDeltaEvent
    | TranscriptEvent
    | AgentStartEvent
    | AgentDeltaEvent
    | AgentDoneEvent
    | AudioDeltaEvent
    | HistoryEvent
    | ErrorEvent
    | StateEvent
)
