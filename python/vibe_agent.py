# python/vibe_agent.py
"""
Adapter that wraps VibeExecutor with the same stream_response/complete
interface used by main.py, so the vibe CLI can be dropped in as the agent.
"""

from typing import AsyncIterator, Optional

from python.session_manager import session_manager
from python.vibe_executor import VibeExecutor


class VibeAgentService:
    def __init__(self) -> None:
        self._executor = VibeExecutor()

    async def stream_response(
        self,
        session_id: str,
        user_message: str,
        image_uris: Optional[list[str]] = None,
    ) -> AsyncIterator[str]:
        session_manager.clear_interrupted(session_id)
        session_manager.add_turn(session_id, role="user", text=user_message)

        full_response = ""
        try:
            async for line in self._executor.execute(user_message, session_id=session_id):
                if session_manager.is_interrupted(session_id):
                    break
                full_response += line + "\n"
                yield line + "\n"
        except Exception as e:
            error_msg = f"\n[Error: {type(e).__name__}: {e}]"
            full_response += error_msg
            yield error_msg

        if full_response.strip():
            session_manager.add_turn(session_id, role="assistant", text=full_response)

    async def complete(
        self,
        session_id: str,
        user_message: str,
        image_uris: Optional[list[str]] = None,
    ) -> str:
        parts = []
        async for delta in self.stream_response(session_id, user_message, image_uris):
            parts.append(delta)
        return "".join(parts)


_service: Optional[VibeAgentService] = None


def get_vibe_agent_service() -> VibeAgentService:
    global _service
    if _service is None:
        _service = VibeAgentService()
    return _service
