# tests/test_ws_audio.py
"""
Tests for the Voice Agent API (WebSocket + REST hybrid).

Unit tests (no MISTRAL_API_KEY needed - mocked):
  - WebSocket authentication
  - Push-to-talk flow (start/stop/cancel)
  - Session management
  - REST endpoints (session, message, interrupt, upload)
  - Error handling

Integration tests (requires MISTRAL_API_KEY - skipped otherwise):
  - Real transcription with Voxtral
"""

import json
import os
import time
import uuid
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient
from fastapi import WebSocketDisconnect

# We need to mock before importing main
with patch.dict("os.environ", {"MISTRAL_API_KEY": "test-key"}):
    with patch("python.audio_processor.Mistral"):
        import python.main as main
        from python.session_manager import session_manager


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------

def make_token(user_id: str, *, secret=None, issuer=None, exp_offset=3600) -> str:
    """Generate a JWT token for testing."""
    now = int(time.time())
    return jwt.encode(
        {
            "iss": issuer or main.JWT_ISSUER,
            "sub": user_id,
            "iat": now,
            "exp": now + exp_offset,
            "jti": str(uuid.uuid4()),
        },
        secret or main.JWT_SECRET,
        algorithm="HS256",
    )


class FakePushToTalkProcessor:
    """Mock audio processor for testing."""

    def __init__(self):
        self.model = "fake-voxtral-model"
        self._buffers = {}
        self._recording = {}
        self._transcript = "hello world"

    def start_recording(self, session_id: str):
        self._buffers[session_id] = bytearray()
        self._recording[session_id] = True

    def is_recording(self, session_id: str) -> bool:
        return self._recording.get(session_id, False)

    def append_audio(self, session_id: str, chunk: bytes):
        if session_id not in self._buffers:
            self._buffers[session_id] = bytearray()
            self._recording[session_id] = True
        self._buffers[session_id].extend(chunk)

    async def stop_and_transcribe(self, session_id: str) -> str:
        self._recording[session_id] = False
        self._buffers.pop(session_id, None)
        return self._transcript

    def cancel_recording(self, session_id: str):
        self._buffers.pop(session_id, None)
        self._recording[session_id] = False

    def get_buffer_duration_ms(self, session_id: str) -> int:
        buf = self._buffers.get(session_id)
        return len(buf) // 32 if buf else 0  # Rough approximation


class FakeStrandsAgentService:
    """Mock Strands agent service for testing."""

    def __init__(self):
        self._agents = {}

    async def stream_response(self, session_id, user_message, image_uris=None):
        yield f"[Agent] Received: {user_message}"
        yield "\nProcessing complete."

    async def complete(self, session_id, user_message, image_uris=None):
        return f"[Agent] Received: {user_message}\nProcessing complete."


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_singletons(monkeypatch):
    """Inject mocks so no API keys are required."""
    fake_processor = FakePushToTalkProcessor()
    fake_agent = FakeStrandsAgentService()

    monkeypatch.setattr(main, "audio_processor", fake_processor)

    # Mock get_strands_agent_service to return our fake
    monkeypatch.setattr("python.main.get_strands_agent_service", lambda: fake_agent)

    # Clear session manager between tests
    session_manager._sessions.clear()

    return fake_processor, fake_agent


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(main.app)


# ===========================================================================
# WebSocket Auth Tests
# ===========================================================================

class TestWebSocketAuth:
    def test_rejects_missing_token(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/audio"):
                pass

    def test_rejects_wrong_secret(self, client):
        token = make_token("user-1", secret="wrong-secret")
        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/audio?token={token}"):
                pass

    def test_rejects_expired_token(self, client):
        token = make_token("user-1", exp_offset=-10)
        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/audio?token={token}"):
                pass

    def test_accepts_valid_token(self, client):
        token = make_token("user-1")
        with client.websocket_connect(f"/ws/audio?token={token}") as ws:
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "session"

    def test_accepts_bearer_header(self, client):
        token = make_token("user-1")
        with client.websocket_connect(
            "/ws/audio",
            headers={"Authorization": f"Bearer {token}"},
        ) as ws:
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "session"

    def test_rejects_session_hijack(self, client):
        """A second user cannot join a session owned by someone else."""
        session_id = "shared-session"
        token_a = make_token("user-a")
        token_b = make_token("user-b")

        # user-a creates the session
        with client.websocket_connect(
            f"/ws/audio?token={token_a}&session_id={session_id}"
        ) as ws:
            _ = json.loads(ws.receive_text())

        # user-b tries to join - should be rejected
        with client.websocket_connect(
            f"/ws/audio?token={token_b}&session_id={session_id}"
        ) as ws:
            with pytest.raises(WebSocketDisconnect) as exc:
                _ = json.loads(ws.receive_text())
            assert exc.value.code == 4403


# ===========================================================================
# WebSocket Push-to-Talk Tests
# ===========================================================================

class TestPushToTalk:
    def test_start_recording(self, client):
        token = make_token("user-1")
        with client.websocket_connect(f"/ws/audio?token={token}") as ws:
            _ = json.loads(ws.receive_text())  # session event

            ws.send_text(json.dumps({"type": "start"}))
            msg = json.loads(ws.receive_text())

            assert msg["event"] == "recording"
            assert msg["data"]["status"] == "started"

    def test_stop_recording_triggers_transcription(self, client):
        token = make_token("user-1")
        with client.websocket_connect(f"/ws/audio?token={token}") as ws:
            _ = json.loads(ws.receive_text())  # session

            # Start recording
            ws.send_text(json.dumps({"type": "start"}))
            _ = json.loads(ws.receive_text())  # recording started

            # Send some audio
            ws.send_bytes(b"\x00" * 1600)

            # Stop recording
            ws.send_text(json.dumps({"type": "stop"}))

            events = []
            for _ in range(5):  # recording, transcribing, transcript, agent_start, agent_delta...
                msg = json.loads(ws.receive_text())
                events.append(msg["event"])

            assert "recording" in events
            assert "transcribing" in events
            assert "transcript" in events

    def test_cancel_recording(self, client):
        token = make_token("user-1")
        with client.websocket_connect(f"/ws/audio?token={token}") as ws:
            _ = json.loads(ws.receive_text())  # session

            ws.send_text(json.dumps({"type": "start"}))
            _ = json.loads(ws.receive_text())  # recording started

            ws.send_text(json.dumps({"type": "cancel"}))
            msg = json.loads(ws.receive_text())

            assert msg["event"] == "recording"
            assert msg["data"]["status"] == "cancelled"

    def test_interrupt_agent(self, client):
        token = make_token("user-1")
        with client.websocket_connect(f"/ws/audio?token={token}") as ws:
            _ = json.loads(ws.receive_text())  # session

            ws.send_text(json.dumps({"type": "interrupt"}))
            msg = json.loads(ws.receive_text())

            assert msg["event"] == "state"
            assert msg["data"]["status"] == "interrupted"

    def test_init_returns_history(self, client):
        token = make_token("user-1")
        session_id = "history-test"

        # Add some history to the session
        session_manager.create("user-1", session_id)
        session_manager.add_turn(session_id, "user", "previous message")

        with client.websocket_connect(
            f"/ws/audio?token={token}&session_id={session_id}"
        ) as ws:
            _ = json.loads(ws.receive_text())  # session

            ws.send_text(json.dumps({"type": "init"}))
            msg = json.loads(ws.receive_text())

            assert msg["event"] == "history"
            assert len(msg["data"]["turns"]) == 1

    def test_unknown_type_returns_error(self, client):
        token = make_token("user-1")
        with client.websocket_connect(f"/ws/audio?token={token}") as ws:
            _ = json.loads(ws.receive_text())  # session

            ws.send_text(json.dumps({"type": "unknown"}))
            msg = json.loads(ws.receive_text())

            assert msg["event"] == "error"

    def test_invalid_json_returns_error(self, client):
        token = make_token("user-1")
        with client.websocket_connect(f"/ws/audio?token={token}") as ws:
            _ = json.loads(ws.receive_text())  # session

            ws.send_text("not valid json {{{")
            msg = json.loads(ws.receive_text())

            assert msg["event"] == "error"


# ===========================================================================
# REST API Tests
# ===========================================================================

class TestSessionAPI:
    def test_create_session(self, client):
        token = make_token("user-1")
        response = client.post(
            "/api/session",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "created_at" in data

    def test_create_session_with_id(self, client):
        token = make_token("user-1")
        response = client.post(
            "/api/session",
            headers={"Authorization": f"Bearer {token}"},
            json={"session_id": "custom-session"},
        )
        assert response.status_code == 200
        assert response.json()["session_id"] == "custom-session"

    def test_create_session_requires_auth(self, client):
        response = client.post("/api/session", json={})
        assert response.status_code == 401

    def test_get_history(self, client):
        token = make_token("user-1")
        session_id = "history-session"

        # Create session and add history
        session_manager.create("user-1", session_id)
        session_manager.add_turn(session_id, "user", "hello")
        session_manager.add_turn(session_id, "assistant", "hi there")

        response = client.get(
            f"/api/session/{session_id}/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["turns"]) == 2

    def test_get_history_wrong_user(self, client):
        session_manager.create("user-1", "secret-session")

        token = make_token("user-2")
        response = client.get(
            "/api/session/secret-session/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestMessageAPI:
    def test_send_message_streams_response(self, client):
        token = make_token("user-1")
        session_id = "msg-session"
        session_manager.create("user-1", session_id)

        response = client.post(
            "/api/message",
            headers={"Authorization": f"Bearer {token}"},
            json={"session_id": session_id, "text": "hello"},
        )
        assert response.status_code == 200
        # SSE response
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_send_message_wrong_session(self, client):
        session_manager.create("user-1", "other-session")

        token = make_token("user-2")
        response = client.post(
            "/api/message",
            headers={"Authorization": f"Bearer {token}"},
            json={"session_id": "other-session", "text": "hello"},
        )
        assert response.status_code == 403


class TestInterruptAPI:
    def test_interrupt_session(self, client):
        token = make_token("user-1")
        session_id = "interrupt-session"
        session_manager.create("user-1", session_id)

        response = client.post(
            "/api/interrupt",
            headers={"Authorization": f"Bearer {token}"},
            json={"session_id": session_id},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "interrupted"
        assert session_manager.is_interrupted(session_id)

    def test_interrupt_wrong_session(self, client):
        session_manager.create("user-1", "other-session")

        token = make_token("user-2")
        response = client.post(
            "/api/interrupt",
            headers={"Authorization": f"Bearer {token}"},
            json={"session_id": "other-session"},
        )
        assert response.status_code == 403


class TestUploadAPI:
    def test_upload_file(self, client):
        token = make_token("user-1")
        file_content = b"fake image content"

        response = client.post(
            "/api/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.png", BytesIO(file_content), "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert data["url"].startswith("/uploads/")


class TestHealthAPI:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "model" in data


# ===========================================================================
# Integration Tests (require MISTRAL_API_KEY)
# ===========================================================================

requires_api_key = pytest.mark.skipif(
    not os.environ.get("MISTRAL_API_KEY"),
    reason="MISTRAL_API_KEY not set",
)


@requires_api_key
class TestVoxtralIntegration:
    """Real Voxtral API tests."""

    @pytest.fixture(autouse=True)
    def use_real_processor(self, monkeypatch):
        from python.audio_processor import PushToTalkProcessor
        real = PushToTalkProcessor()
        monkeypatch.setattr(main, "audio_processor", real)

    @pytest.mark.asyncio
    async def test_transcribe_silence(self):
        from python.audio_processor import PushToTalkProcessor
        processor = PushToTalkProcessor()
        processor.start_recording("test-session")
        processor.append_audio("test-session", b"\x00\x00" * 8000)  # 0.5s silence
        result = await processor.stop_and_transcribe("test-session")
        assert isinstance(result, str)