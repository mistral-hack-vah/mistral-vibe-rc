# tests/test_session_manager.py
"""
Unit tests for SessionManager.
"""

import pytest
import time

from python.session_manager import SessionManager, Session


class TestSessionManager:
    @pytest.fixture
    def manager(self):
        return SessionManager()

    def test_create_session(self, manager):
        session = manager.create("user-1")
        assert session.user_id == "user-1"
        assert session.id is not None
        assert len(session.turns) == 0

    def test_create_session_with_id(self, manager):
        session = manager.create("user-1", session_id="custom-id")
        assert session.id == "custom-id"

    def test_get_session(self, manager):
        created = manager.create("user-1", session_id="s1")
        retrieved = manager.get("s1", "user-1")
        assert retrieved.id == created.id

    def test_get_session_wrong_user_raises(self, manager):
        manager.create("user-1", session_id="s1")
        with pytest.raises(PermissionError):
            manager.get("s1", "user-2")

    def test_get_nonexistent_session_raises(self, manager):
        with pytest.raises(PermissionError):
            manager.get("nonexistent", "user-1")

    def test_get_or_create_creates_new(self, manager):
        session = manager.get_or_create(None, "user-1")
        assert session.user_id == "user-1"

    def test_get_or_create_returns_existing(self, manager):
        created = manager.create("user-1", session_id="s1")
        retrieved = manager.get_or_create("s1", "user-1")
        assert retrieved.id == created.id

    def test_add_turn(self, manager):
        manager.create("user-1", session_id="s1")
        turn = manager.add_turn("s1", "user", "hello")
        assert turn["role"] == "user"
        assert turn["text"] == "hello"
        assert "ts" in turn

    def test_add_turn_with_extras(self, manager):
        manager.create("user-1", session_id="s1")
        turn = manager.add_turn("s1", "user", "hello", image_uris=["img1.png"])
        assert turn["image_uris"] == ["img1.png"]

    def test_get_turns(self, manager):
        manager.create("user-1", session_id="s1")
        manager.add_turn("s1", "user", "hello")
        manager.add_turn("s1", "assistant", "hi there")
        turns = manager.get_turns("s1")
        assert len(turns) == 2

    def test_interrupt_flag(self, manager):
        manager.create("user-1", session_id="s1")
        assert not manager.is_interrupted("s1")

        manager.set_interrupted("s1", True)
        assert manager.is_interrupted("s1")

        manager.clear_interrupted("s1")
        assert not manager.is_interrupted("s1")

    def test_agent_id(self, manager):
        manager.create("user-1", session_id="s1")
        assert manager.get_agent_id("s1") is None

        manager.set_agent_id("s1", "agent-123")
        assert manager.get_agent_id("s1") == "agent-123"

    def test_conversation_id(self, manager):
        manager.create("user-1", session_id="s1")
        assert manager.get_conversation_id("s1") is None

        manager.set_conversation_id("s1", "conv-456")
        assert manager.get_conversation_id("s1") == "conv-456"

    def test_delete_session(self, manager):
        manager.create("user-1", session_id="s1")
        assert manager.exists("s1")

        result = manager.delete("s1")
        assert result is True
        assert not manager.exists("s1")

    def test_delete_nonexistent_returns_false(self, manager):
        result = manager.delete("nonexistent")
        assert result is False

    def test_list_user_sessions(self, manager):
        manager.create("user-1", session_id="s1")
        manager.create("user-1", session_id="s2")
        manager.create("user-2", session_id="s3")

        sessions = manager.list_user_sessions("user-1")
        assert len(sessions) == 2
        assert all(s.user_id == "user-1" for s in sessions)


class TestSession:
    def test_to_dict(self):
        session = Session(
            id="s1",
            user_id="user-1",
            created_at=1234567890,
            turns=[{"role": "user", "text": "hello"}],
        )
        d = session.to_dict()
        assert d["session_id"] == "s1"
        assert d["user_id"] == "user-1"
        assert d["created_at"] == 1234567890
        assert len(d["turns"]) == 1