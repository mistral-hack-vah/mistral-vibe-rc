# python/session_manager.py
"""
Session management for voice agent conversations.

Provides in-memory session storage with a Redis-ready interface.
Each session tracks:
  - User ownership
  - Conversation history (turns)
  - Interrupt flags for cancelling agent streams
  - Mistral agent/conversation IDs
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Session:
    """Represents a user session with conversation state."""

    id: str
    user_id: str
    created_at: int
    turns: list[dict] = field(default_factory=list)
    interrupted: bool = False
    agent_id: Optional[str] = None
    conversation_id: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize session for API responses."""
        return {
            "session_id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "turns": self.turns,
        }


class SessionManager:
    """
    In-memory session store.

    For production, swap the dict with Redis using the same interface.
    """

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create(self, user_id: str, session_id: Optional[str] = None) -> Session:
        """Create a new session or return existing one if session_id provided."""
        session_id = session_id or str(uuid.uuid4())

        if session_id in self._sessions:
            existing = self._sessions[session_id]
            if existing.user_id != user_id:
                raise PermissionError("Session belongs to another user")
            return existing

        session = Session(
            id=session_id,
            user_id=user_id,
            created_at=int(time.time()),
            turns=[],
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str, user_id: str) -> Session:
        """
        Retrieve a session by ID.

        Raises:
            PermissionError: If session not found or belongs to another user.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise PermissionError("Session not found")
        if session.user_id != user_id:
            raise PermissionError("Session access denied")
        return session

    def get_or_create(self, session_id: Optional[str], user_id: str) -> Session:
        """Get existing session or create new one."""
        if session_id and session_id in self._sessions:
            return self.get(session_id, user_id)
        return self.create(user_id, session_id)

    def exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        return session_id in self._sessions

    def add_turn(
        self,
        session_id: str,
        role: str,
        text: str,
        **kwargs: Any,
    ) -> dict:
        """
        Add a conversation turn to the session.

        Args:
            session_id: The session ID
            role: "user" or "assistant"
            text: The message content
            **kwargs: Additional fields (e.g., image_uris)

        Returns:
            The created turn dict.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Session {session_id} not found")

        turn = {
            "role": role,
            "text": text,
            "ts": int(time.time()),
            **kwargs,
        }
        session.turns.append(turn)
        return turn

    def get_turns(self, session_id: str) -> list[dict]:
        """Get all turns for a session."""
        session = self._sessions.get(session_id)
        return session.turns if session else []

    def set_interrupted(self, session_id: str, value: bool) -> None:
        """Set the interrupt flag for a session."""
        if session_id in self._sessions:
            self._sessions[session_id].interrupted = value

    def is_interrupted(self, session_id: str) -> bool:
        """Check if a session is interrupted."""
        session = self._sessions.get(session_id)
        return session.interrupted if session else False

    def clear_interrupted(self, session_id: str) -> None:
        """Clear the interrupt flag (alias for set_interrupted(False))."""
        self.set_interrupted(session_id, False)

    def set_agent_id(self, session_id: str, agent_id: str) -> None:
        """Store the Mistral agent ID for this session."""
        if session_id in self._sessions:
            self._sessions[session_id].agent_id = agent_id

    def get_agent_id(self, session_id: str) -> Optional[str]:
        """Get the Mistral agent ID for this session."""
        session = self._sessions.get(session_id)
        return session.agent_id if session else None

    def set_conversation_id(self, session_id: str, conversation_id: str) -> None:
        """Store the Mistral conversation ID for this session."""
        if session_id in self._sessions:
            self._sessions[session_id].conversation_id = conversation_id

    def get_conversation_id(self, session_id: str) -> Optional[str]:
        """Get the Mistral conversation ID for this session."""
        session = self._sessions.get(session_id)
        return session.conversation_id if session else None

    def delete(self, session_id: str) -> bool:
        """Delete a session. Returns True if deleted, False if not found."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_user_sessions(self, user_id: str) -> list[Session]:
        """List all sessions for a user."""
        return [s for s in self._sessions.values() if s.user_id == user_id]


# Global singleton instance
session_manager = SessionManager()
