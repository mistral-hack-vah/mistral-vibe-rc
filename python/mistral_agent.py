# python/mistral_agent.py
"""
Mistral Agents API service for voice agent conversations.

Uses the Mistral beta.agents and beta.conversations APIs for:
  - Creating persistent agents with tools
  - Managing conversation history
  - Streaming agent responses
"""

import os
from typing import AsyncIterator, Optional

from mistralai import Mistral

from python.session_manager import session_manager


# Default system instructions for the voice agent
DEFAULT_INSTRUCTIONS = """You are a helpful voice-controlled coding assistant.

Your capabilities:
- Answer programming questions
- Help debug code
- Explain concepts clearly and concisely
- Execute code when needed using the code interpreter

Keep responses concise since they will be spoken aloud.
Use simple language and avoid overly technical jargon unless asked.
"""


class MistralAgentService:
    """
    Service for managing Mistral Agents and conversations.

    Creates one agent per session and maintains conversation history
    through the Mistral Conversations API.
    """

    def __init__(
        self,
        model: str = "mistral-large-latest",
        instructions: Optional[str] = None,
    ):
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            raise RuntimeError("MISTRAL_API_KEY environment variable is not set.")

        self.client = Mistral(api_key=api_key)
        self.model = model
        self.instructions = instructions or DEFAULT_INSTRUCTIONS

        # Local cache of agent IDs (session_id -> agent_id)
        # These are also stored in session_manager for persistence
        self._agents: dict[str, str] = {}

    async def get_or_create_agent(self, session_id: str) -> str:
        """
        Get or create a Mistral agent for this session.

        Returns the agent_id.
        """
        # Check local cache first
        if session_id in self._agents:
            return self._agents[session_id]

        # Check session manager
        existing_agent_id = session_manager.get_agent_id(session_id)
        if existing_agent_id:
            self._agents[session_id] = existing_agent_id
            return existing_agent_id

        # Create new agent
        agent = await self.client.beta.agents.create_async(
            model=self.model,
            name=f"voice-agent-{session_id[:8]}",
            description="Voice-controlled coding assistant",
            instructions=self.instructions,
            tools=[
                {"type": "code_interpreter"},
            ],
        )

        agent_id = agent.id
        self._agents[session_id] = agent_id
        session_manager.set_agent_id(session_id, agent_id)

        return agent_id

    async def stream_response(
        self,
        session_id: str,
        user_message: str,
        image_uris: Optional[list[str]] = None,
    ) -> AsyncIterator[str]:
        """
        Stream a response from the Mistral agent.

        Args:
            session_id: The session ID
            user_message: The user's message text
            image_uris: Optional list of image URLs to include

        Yields:
            Text deltas from the agent response.
        """
        from mistralai.extra.run.context import RunContext
        from mistralai.extra.run.result import RunResult
        from mistralai.models import MessageOutputEvent

        agent_id = await self.get_or_create_agent(session_id)
        conversation_id = session_manager.get_conversation_id(session_id)

        # Clear interrupt flag before starting
        session_manager.clear_interrupted(session_id)

        # Add user turn to session history
        session_manager.add_turn(
            session_id,
            role="user",
            text=user_message,
            image_uris=image_uris or [],
        )

        # Build inputs - simple string for text-only, structured for images
        if image_uris:
            content: list = [{"type": "text", "text": user_message}]
            for uri in image_uris:
                content.append({"type": "image_url", "image_url": {"url": uri}})
            inputs = [{"role": "user", "content": content, "type": "message.input"}]
        else:
            inputs = user_message

        full_response = ""
        run_ctx = RunContext(agent_id=agent_id, conversation_id=conversation_id)

        try:
            stream = await self.client.beta.conversations.run_stream_async(
                run_ctx=run_ctx,
                inputs=inputs,
            )
            async for event in stream:
                if session_manager.is_interrupted(session_id):
                    break

                # Last event is the RunResult summary - grab conversation_id from it
                if isinstance(event, RunResult):
                    if event.conversation_id:
                        session_manager.set_conversation_id(session_id, event.conversation_id)
                    continue

                # All other events are RunResultEvents with a .data attribute
                data = event.data if hasattr(event, "data") else event

                if isinstance(data, MessageOutputEvent):
                    chunk = data.content
                    if isinstance(chunk, str):
                        text = chunk
                    elif hasattr(chunk, "text"):
                        text = chunk.text
                    else:
                        continue

                    if text:
                        full_response += text
                        yield text

        except Exception as e:
            error_msg = f"Agent error: {type(e).__name__}: {e}"
            yield f"\n[Error: {error_msg}]"
            full_response += f"\n[Error: {error_msg}]"

        finally:
            # Persist conversation_id updated during the stream
            if run_ctx.conversation_id and run_ctx.conversation_id != conversation_id:
                session_manager.set_conversation_id(session_id, run_ctx.conversation_id)

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
        Non-streaming completion from the Mistral agent.

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

    async def delete_agent(self, session_id: str) -> bool:
        """
        Delete the agent for a session.

        Returns True if deleted, False if not found.
        """
        agent_id = self._agents.pop(session_id, None)
        if not agent_id:
            agent_id = session_manager.get_agent_id(session_id)

        if agent_id:
            try:
                await self.client.beta.agents.delete_async(agent_id=agent_id)
                return True
            except Exception:
                pass

        return False


# Global singleton instance - initialized lazily
mistral_agent_service: Optional[MistralAgentService] = None


def get_mistral_agent_service() -> MistralAgentService:
    """Get or create the global MistralAgentService instance."""
    global mistral_agent_service
    if mistral_agent_service is None:
        mistral_agent_service = MistralAgentService()
    return mistral_agent_service
