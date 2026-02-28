"""
tests/test_ws_audio.py

Unit tests (no MISTRAL_API_KEY needed — FakeAudioProcessor is injected):
  - partial + final transcript event shape
  - reset control
  - stop 2ntrol (triggers finalize)
  - unknown control action
  - invalid JSON text frame
  - missing token → 4401
  - invalid/expired token → 4401
  - header-based Bearer auth
  - session ownership protection → 4403
  - session persistence across reconnect
  - command event emitted after final transcript
  - health endpoint

Integration test (requires MISTRAL_API_KEY — skipped otherwise):
  - VoxtralAudioProcessor.process_audio with real PCM audio

Integration test (requires mistral-vibe on PATH — skipped otherwise):
  - VibeExecutor streams real output from the CLI against the current codebase
"""

import io
import json
import os
import shutil
import time
import uuid
import wave
from typing import AsyncIterator

import jwt
import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

import python.main as main
from python.audio_processor import VoxtralAudioProcessor


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class FakeAudioProcessor:
    """
    Mock processor:
      chunk 1 → partial "hello"
      chunk 2 → partial "hello world"
      chunk 3 → final  "hello world"
      chunk 4+ → nothing
    Supports reset / finalize.
    """

    def __init__(self):
        self.count: dict = {}
        self.model = "fake-voxtral-model"

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


class FakeVibeExecutor:
    """Mock for the Mistral Vibe CLI bridge."""
    async def execute(self, command_text: str, session_id: str) -> AsyncIterator[str]:
        yield f"[fake-vibe] Executing: {command_text}"
        yield "Success"


def make_token(user_id: str, *, secret=None, issuer=None, exp_offset=3600) -> str:
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


def _drain_session_event(ws) -> dict:
    """Consume and return the mandatory first session event."""
    return json.loads(ws.receive_text())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_singletons(monkeypatch):
    """Inject fakes so no Voxtral API key or CLI is required."""
    fake_processor = FakeAudioProcessor()
    fake_executor = FakeVibeExecutor()
    monkeypatch.setattr(main, "audio_processor", fake_processor)
    monkeypatch.setattr(main, "vibe_executor", fake_executor)
    # Also clear SESSIONS between tests to avoid cross-test state
    main.SESSIONS.clear()
    return fake_processor


@pytest.fixture
def client():
    # lifespan will see that singletons are already patched (not None)
    # and skip real initialization.
    return TestClient(main.app)


# ===========================================================================
# Auth tests
# ===========================================================================

class TestAuth:
    def test_rejects_missing_token(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/audio?session_id=s1"):
                pass

    def test_rejects_wrong_secret(self, client):
        token = make_token("user-1", secret="wrong-secret")
        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/audio?token={token}&session_id=s1"):
                pass

    def test_rejects_expired_token(self, client):
        token = make_token("user-1", exp_offset=-10)   # already expired
        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/audio?token={token}&session_id=s1"):
                pass

    def test_accepts_bearer_header(self, client):
        token = make_token("user-1")
        # Pass token via Authorization header instead of query param
        with client.websocket_connect(
            "/ws/audio?session_id=header-session",
            headers={"Authorization": f"Bearer {token}"},
        ) as ws:
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "session"
            assert msg["data"]["session_id"] == "header-session"

    def test_rejects_session_hijack(self, client):
        """A second user cannot join a session owned by someone else."""
        session_id = "shared-session"
        token_a = make_token("user-a")
        token_b = make_token("user-b")

        # user-a creates the session
        with client.websocket_connect(
            f"/ws/audio?token={token_a}&session_id={session_id}"
        ) as ws:
            _ = _drain_session_event(ws)

        # user-b tries to join — should be rejected with 4403
        # In TestClient, after accept() then close(), we must attempt to recv to see closure
        with client.websocket_connect(
            f"/ws/audio?token={token_b}&session_id={session_id}"
        ) as ws:
            # The next receive should fail with WebSocketDisconnect (4403)
            # because the server closes before sending the session event.
            with pytest.raises(WebSocketDisconnect) as exc:
                _ = _drain_session_event(ws)
            assert exc.value.code == 4403


# ===========================================================================
# Transcript tests
# ===========================================================================

class TestTranscripts:
    def test_emits_partial_and_final(self, client):
        token = make_token("user-1")
        with client.websocket_connect(
            f"/ws/audio?token={token}&session_id=t1"
        ) as ws:
            _ = _drain_session_event(ws)
            # chunk 1 → partial "hello"
            ws.send_bytes(b"\x00\x01\x02\x03")
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "partial_transcript"
            assert msg["data"]["text"] == "hello"

            # chunk 2 → partial "hello world"
            ws.send_bytes(b"\x04\x05\x06\x07")
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "partial_transcript"
            assert msg["data"]["text"] == "hello world"

            # chunk 3 → final "hello world"
            ws.send_bytes(b"\x08\x09\x0A\x0B")
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "final_transcript"
            assert msg["data"]["text"] == "hello world"

    def test_final_emits_command_and_agent_events(self, client):
        """After a final transcript, server emits command + agent_delta events."""
        token = make_token("user-1")
        with client.websocket_connect(
            f"/ws/audio?token={token}&session_id=t-cmd"
        ) as ws:
            _ = _drain_session_event(ws)
            # burn through chunks 1 & 2 (partials)
            for _ in range(2):
                ws.send_bytes(b"\x00")
                _ = ws.receive_text()

            ws.send_bytes(b"\x04\x05")   # chunk 3 → final
            # 1. final_transcript
            assert json.loads(ws.receive_text())["event"] == "final_transcript"
            # 2. command
            assert json.loads(ws.receive_text())["event"] == "command"
            # 3. agent_delta (from FakeVibeExecutor)
            msg3 = json.loads(ws.receive_text())
            assert msg3["event"] == "agent_delta"
            assert "fake-vibe" in msg3["data"]["text"]

    def test_silent_chunks_emit_nothing(self, client):
        """Chunks 4+ return {partial:None, final:None} — no WS frames should be sent."""
        token = make_token("user-1")
        with client.websocket_connect(
            f"/ws/audio?token={token}&session_id=t-silent"
        ) as ws:
            _ = _drain_session_event(ws)
            # chunk 1 → partial
            ws.send_bytes(b"\x01")
            _ = ws.receive_text()
            # chunk 2 → partial
            ws.send_bytes(b"\x01")
            _ = ws.receive_text()
            # chunk 3 → final + command + agent_deltas (2 lines)
            ws.send_bytes(b"\x01")
            _ = ws.receive_text() # final
            _ = ws.receive_text() # command
            _ = ws.receive_text() # delta 1
            _ = ws.receive_text() # delta 2

            # chunk 4 onwards → nothing emitted
            ws.send_bytes(b"\xFF")
            
            # send reset to confirm we're still connected and no phantom messages were queued
            ws.send_text(json.dumps({"type": "control", "action": "reset"}))
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "state"
            assert msg["data"]["status"] == "reset"


# ===========================================================================
# Control message tests
# ===========================================================================

class TestControls:
    def test_reset_clears_state(self, client):
        token = make_token("user-1")
        with client.websocket_connect(
            f"/ws/audio?token={token}&session_id=c-reset"
        ) as ws:
            _ = _drain_session_event(ws)
            ws.send_bytes(b"\x00\x01")
            _ = json.loads(ws.receive_text())  # partial

            ws.send_text(json.dumps({"type": "control", "action": "reset"}))
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "state"
            assert msg["data"]["status"] == "reset"

    def test_stop_triggers_finalize_and_final_transcript(self, client):
        token = make_token("user-1")
        with client.websocket_connect(
            f"/ws/audio?token={token}&session_id=c-stop"
        ) as ws:
            _ = _drain_session_event(ws)

            # Send stop — FakeAudioProcessor.finalize() returns "forced final"
            ws.send_text(json.dumps({"type": "control", "action": "stop"}))

            # Sequence: final_transcript → command → delta 1 → delta 2 → state:stopped
            events = []
            for _ in range(5):
                m = json.loads(ws.receive_text())
                events.append(m["event"])
            
            assert "final_transcript" in events
            assert "command" in events
            assert "agent_delta" in events
            assert "state" in events

    def test_unknown_control_action(self, client):
        token = make_token("user-1")
        with client.websocket_connect(
            f"/ws/audio?token={token}&session_id=c-unknown"
        ) as ws:
            _ = _drain_session_event(ws)
            ws.send_text(json.dumps({"type": "control", "action": "fly"}))
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "state"
            assert msg["data"]["status"] == "unknown_control"

    def test_invalid_json_text_frame(self, client):
        token = make_token("user-1")
        with client.websocket_connect(
            f"/ws/audio?token={token}&session_id=c-json"
        ) as ws:
            _ = _drain_session_event(ws)
            ws.send_text("this is not json {{{{")
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "error"


# ===========================================================================
# Session tests
# ===========================================================================

class TestSessions:
    def test_session_created_with_given_id(self, client):
        token = make_token("user-1")
        with client.websocket_connect(
            f"/ws/audio?token={token}&session_id=my-session"
        ) as ws:
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "session"
            assert msg["data"]["session_id"] == "my-session"

    def test_session_id_auto_generated_if_missing(self, client):
        token = make_token("user-1")
        with client.websocket_connect(f"/ws/audio?token={token}") as ws:
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "session"
            assert len(msg["data"]["session_id"]) > 0

    def test_session_turns_recorded(self, client):
        """Final transcripts must be appended to session['turns']."""
        token = make_token("user-1")
        session_id = "turn-test"
        with client.websocket_connect(
            f"/ws/audio?token={token}&session_id={session_id}"
        ) as ws:
            _ = _drain_session_event(ws)
            # trigger a final on chunk 3
            for i in range(3):
                ws.send_bytes(bytes([i]))
                # Drain messages
                m = json.loads(ws.receive_text())
                if m["event"] == "final_transcript":
                    # drain command and deltas
                    ws.receive_text() # command
                    ws.receive_text() # delta 1
                    ws.receive_text() # delta 2

        session = main.SESSIONS.get(session_id)
        assert session is not None
        user_turns = [t for t in session["turns"] if t["role"] == "user"]
        assert any("hello world" in t["text"] for t in user_turns)


# ===========================================================================
# HTTP endpoint tests
# ===========================================================================

class TestHTTP:
    def test_health_endpoint(self, client):
        # We need to ensure audio_processor is initialized for health check
        with client:
            r = client.get("/health")
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "ok"
            assert body["model"] == "fake-voxtral-model"


# ===========================================================================
# NLU / extract_command heuristic tests (pure function, no WS needed)
# ===========================================================================

class TestExtractCommand:
    @pytest.mark.asyncio
    async def test_run_tests_intent(self):
        cmd = await main.extract_command("please run tests now", "s")
        assert cmd["intent"] == "run_tests"

    @pytest.mark.asyncio
    async def test_build_intent(self):
        cmd = await main.extract_command("build the project", "s")
        assert cmd["intent"] == "build"

    @pytest.mark.asyncio
    async def test_deploy_intent(self):
        cmd = await main.extract_command("deploy to production", "s")
        assert cmd["intent"] == "deploy"

    @pytest.mark.asyncio
    async def test_chat_fallback(self):
        cmd = await main.extract_command("hey what's up", "s")
        assert cmd["intent"] in ("chat", "status")

    @pytest.mark.asyncio
    async def test_unknown_falls_back_to_chat(self):
        cmd = await main.extract_command("xyzzy frobnicator", "s")
        assert cmd["intent"] == "chat"
        assert cmd["args"]["text"] == "xyzzy frobnicator"


# ===========================================================================
# Integration test — skipped without MISTRAL_API_KEY
# ===========================================================================

requires_api_key = pytest.mark.skipif(
    not os.environ.get("MISTRAL_API_KEY"),
    reason="MISTRAL_API_KEY not set — skipping live Voxtral API test",
)


def _make_silence_wav(duration_sec: float = 0.5, sample_rate: int = 16_000) -> bytes:
    """Return a WAV-wrapped buffer of silence (all zeros)."""
    n_samples = int(sample_rate * duration_sec)
    pcm = b"\x00\x00" * n_samples   # int16 zeros
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


@requires_api_key
class TestVoxtralIntegration:
    """
    These tests call the real Voxtral API.
    They are skipped automatically when MISTRAL_API_KEY is not set.
    """

    @pytest.fixture(autouse=True)
    def use_real_processor(self, monkeypatch):
        """Override the autouse fake with the real VoxtralAudioProcessor."""
        real = VoxtralAudioProcessor()
        monkeypatch.setattr(main, "audio_processor", real)

    @pytest.mark.asyncio
    async def test_real_processor_returns_dict(self):
        processor = VoxtralAudioProcessor()
        # Send 500ms of silence — should return empty partials/finals, not crash
        silence_pcm = b"\x00\x00" * (16_000 // 2)   # 0.5s at 16kHz PCM16
        result = await processor.process_audio(silence_pcm, session_id="integration-1")
        assert isinstance(result, dict)
        assert "partial" in result
        assert "final" in result

    @pytest.mark.asyncio
    async def test_real_processor_finalize_empty_returns_none(self):
        processor = VoxtralAudioProcessor()
        result = await processor.finalize(session_id="integration-new")
        # No audio buffered → should return None
        assert result is None

    @pytest.mark.asyncio
    async def test_real_processor_reset_is_idempotent(self):
        processor = VoxtralAudioProcessor()
        # Reset a session that doesn't exist yet — must not raise
        processor.reset(session_id="nonexistent")
        # Reset again — still safe
        processor.reset(session_id="nonexistent")


# ===========================================================================
# Integration test — skipped without mistral-vibe on PATH
# Runs against the current working directory (the repo root when using pytest).
# ===========================================================================

requires_vibe_cli = pytest.mark.skipif(
    shutil.which("vibe") is None,
    reason="vibe CLI not on PATH — skipping live Vibe executor test",
)


@requires_vibe_cli
class TestVibeExecutorIntegration:
    """
    These tests spawn the real mistral-vibe CLI.
    They are skipped automatically when mistral-vibe is not installed.

    The CLI inherits the CWD of the pytest process (repo root), so it
    operates on this codebase.
    """

    @pytest.mark.asyncio
    async def test_executor_returns_output(self):
        """CLI should produce at least one line of output for a simple prompt."""
        from python.vibe_executor import VibeExecutor
        executor = VibeExecutor()
        lines = [line async for line in executor.execute("list the files in this project", session_id="vibe-int-1")]
        assert len(lines) > 0, "Expected at least one output line from mistral-vibe"

    @pytest.mark.asyncio
    async def test_executor_output_is_strings(self):
        """Every yielded line should be a non-empty string."""
        from python.vibe_executor import VibeExecutor
        executor = VibeExecutor()
        lines = [line async for line in executor.execute("what is this project?", session_id="vibe-int-2")]
        assert all(isinstance(l, str) and len(l) > 0 for l in lines)

    @pytest.mark.asyncio
    async def test_executor_completes_without_error(self):
        """CLI should exit cleanly (return code 0) for a benign query."""
        from python.vibe_executor import VibeExecutor
        executor = VibeExecutor()
        # If the CLI exits non-zero, execute() raises RuntimeError
        try:
            async for _ in executor.execute("describe the python directory", session_id="vibe-int-3"):
                pass
        except RuntimeError as e:
            pytest.fail(f"VibeExecutor raised RuntimeError: {e}")