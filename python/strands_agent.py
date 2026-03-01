# python/strands_agent.py
"""
Strands Agents service for voice agent conversations.

Uses AWS Strands Agents SDK with Mistral model provider for:
  - Creating agents with tools
  - Streaming agent responses
  - Managing conversation context
"""

import os
from typing import AsyncIterator, Optional

from strands import Agent
from strands.models.mistral import MistralModel

from python.session_manager import session_manager


# Default system prompt for the voice agent
DEFAULT_SYSTEM_PROMPT = """You are a helpful voice-controlled coding assistant.

Your capabilities:
- Answer programming questions
- Help debug code
- Explain concepts clearly and concisely
- Execute code when needed

Keep responses concise since they will be spoken aloud.
Use simple language and avoid overly technical jargon unless asked.
"""


class StrandsAgentService:
    """
    Service for managing Strands Agents with Mistral model.

    Creates agents with tool support and streams responses.
    """

    def __init__(
        self,
        model_id: str = "mistral-large-latest",
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ):
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            raise RuntimeError("MISTRAL_API_KEY environment variable is not set.")

        self.model = MistralModel(
            api_key=api_key,
            model_id=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        # Cache of agents per session
        self._agents: dict[str, Agent] = {}

    def _get_or_create_agent(self, session_id: str) -> Agent:
        """Get or create a Strands agent for this session."""
        if session_id not in self._agents:
            # Import tools - these are from strands-agents-tools package
            try:
                from strands_tools import calculator, file_read, shell
                tools = [calculator, file_read, shell]
            except ImportError:
                tools = []

            self._agents[session_id] = Agent(
                model=self.model,
                system_prompt=self.system_prompt,
                tools=tools,
            )

        return self._agents[session_id]

    async def stream_response(
        self,
        session_id: str,
        user_message: str,
        image_uris: Optional[list[str]] = None,
    ) -> AsyncIterator[str]:
        """
        Stream a response from the Strands agent.

        Args:
            session_id: The session ID
            user_message: The user's message text
            image_uris: Optional list of image URLs (for future multimodal support)

        Yields:
            Text deltas from the agent response.
        """
        agent = self._get_or_create_agent(session_id)

        # Clear interrupt flag before starting
        session_manager.clear_interrupted(session_id)

        # Add user turn to session history
        session_manager.add_turn(
            session_id,
            role="user",
            text=user_message,
            image_uris=image_uris or [],
        )

        full_response = ""

        try:
            # Strands agent streaming - use the streaming interface
            # The agent() call returns an AgentResult with streaming support
            response = agent(user_message, stream=True)

            # Iterate over the streaming response
            for chunk in response:
                if session_manager.is_interrupted(session_id):
                    break

                # Extract text from the chunk
                if hasattr(chunk, "content"):
                    text = str(chunk.content)
                elif hasattr(chunk, "text"):
                    text = chunk.text
                elif isinstance(chunk, str):
                    text = chunk
                else:
                    text = str(chunk)

                if text:
                    full_response += text
                    yield text

        except Exception as e:
            error_msg = f"Agent error: {type(e).__name__}: {e}"
            yield f"\n[Error: {error_msg}]"
            full_response += f"\n[Error: {error_msg}]"

        # Add assistant turn to session history
        if full_response:
            session_manager.add_turn(
                session_id,
                role="assistant",
                text=full_response,
            )

    async def complete(
        self,
        session_id: str,
        user_message: str,
        image_uris: Optional[list[str]] = None,
    ) -> str:
        """
        Non-streaming completion from the Strands agent.

        Args:
            session_id: The session ID
            user_message: The user's message text
            image_uris: Optional list of image URLs

        Returns:
            The complete agent response text.
        """
        parts = []
        async for delta in self.stream_response(session_id, user_message, image_uris):
            parts.append(delta)
        return "".join(parts)

    def reset_session(self, session_id: str) -> None:
        """Reset the agent for a session (clear conversation history)."""
        if session_id in self._agents:
            del self._agents[session_id]


# Global singleton instance - initialized lazily
_strands_agent_service: Optional[StrandsAgentService] = None


def get_strands_agent_service() -> StrandsAgentService:
    """Get or create the global StrandsAgentService instance."""
    global _strands_agent_service
    if _strands_agent_service is None:
        _strands_agent_service = StrandsAgentService()
    return _strands_agent_service
