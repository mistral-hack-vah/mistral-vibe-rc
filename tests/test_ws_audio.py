import json
import time
import jwt
import pytest
from fastapi.testclient import TestClient

import python.main as main # import your main.py module


class FakeAudioProcessor:
    """
    Mock processor that:
      - returns partial on first audio chunk
      - returns final on third audio chunk
      - supports reset/finalize
    """
    def __init__(self):
        self.count = {}

    def reset(self, session_id: str):
        self.count[session_id] = 0

    async def finalize(self, session_id: str):
        return "forced final"

    async def process_audio(self, audio_chunk: bytes, session_id: str):
        n = self.count.get(session_id, 0) + 1
        self.count[session_id] = n

        if n == 1:
            return {"partial": "hello", "final": None}
        if n == 2:
            return {"partial": "hello world", "final": None}
        if n == 3:
            return {"partial": None, "final": "hello world"}
        return {"partial": None, "final": None}


def make_token(user_id: str) -> str:
    now = int(time.time())
    payload = {
        "iss": main.JWT_ISSUER,
        "sub": user_id,
        "iat": now,
        "exp": now + 3600,
        "jti": "test-jti",
    }
    return jwt.encode(payload, main.JWT_SECRET, algorithm="HS256")


@pytest.fixture(autouse=True)
def patch_audio_processor(monkeypatch):
    # Replace the real processor (and model loading) with our fake
    fake = FakeAudioProcessor()
    monkeypatch.setattr(main, "audio_processor", fake)
    return fake


@pytest.fixture
def client():
    return TestClient(main.app)


def test_ws_audio_emits_partial_and_final(client):
    token = make_token("demo-user")
    session_id = "session-123"

    with client.websocket_connect(f"/ws/audio?token={token}&session_id={session_id}") as ws:
        # First audio chunk -> partial "hello"
        ws.send_bytes(b"\x00\x01\x02\x03")
        msg1 = json.loads(ws.receive_text())
        assert msg1["event"] == "session"  # first message is session info

        # Now read the partial transcript emitted for chunk 1
        msg2 = json.loads(ws.receive_text())
        assert msg2["event"] == "partial_transcript"
        assert msg2["data"]["text"] == "hello"

        # Second audio chunk -> partial "hello world"
        ws.send_bytes(b"\x04\x05\x06\x07")
        msg3 = json.loads(ws.receive_text())
        assert msg3["event"] == "partial_transcript"
        assert msg3["data"]["text"] == "hello world"

        # Third audio chunk -> final "hello world"
        ws.send_bytes(b"\x08\x09\x0A\x0B")

        msg4 = json.loads(ws.receive_text())
        assert msg4["event"] == "final_transcript"
        assert msg4["data"]["text"] == "hello world"


def test_ws_audio_reset_control(client):
    token = make_token("demo-user")
    session_id = "session-abc"

    with client.websocket_connect(f"/ws/audio?token={token}&session_id={session_id}") as ws:
        # consume session event
        _ = json.loads(ws.receive_text())
        # send a chunk to create some state
        ws.send_bytes(b"\x00\x01")
        _ = json.loads(ws.receive_text())  # partial_transcript

        # send reset control
        ws.send_text(json.dumps({"type": "control", "action": "reset"}))
        state_msg = json.loads(ws.receive_text())
        assert state_msg["event"] == "state"
        assert state_msg["data"]["status"] == "reset"


def test_ws_audio_rejects_missing_token(client):
    with pytest.raises(Exception):
        # should close with 4401, TestClient raises on connect
        client.websocket_connect("/ws/audio?session_id=s1")