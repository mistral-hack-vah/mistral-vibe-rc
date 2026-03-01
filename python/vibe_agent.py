# python/vibe_agent.py
"""
Adapter that wraps VibeExecutor with the same stream_response/complete
interface used by main.py, so the vibe CLI can be dropped in as the agent.

Includes intent classification to differentiate between:
- Commands: Actions for the vibe CLI (create file, run tests, etc.)
- Prompts: Conversational queries that need explanations
"""

import os
from typing import AsyncIterator, Optional

from mistralai import Mistral

from python.intent_classifier import IntentType, get_intent_classifier
from python.session_manager import session_manager
from python.vibe_executor import VibeExecutor


class VibeAgentService:
    def __init__(self) -> None:
        self._executor = VibeExecutor()
        self._classifier = get_intent_classifier()

        # Mistral client for handling prompts (conversational queries)
        api_key = os.environ.get("MISTRAL_API_KEY")
        self._chat_client = Mistral(api_key=api_key) if api_key else None
        self._chat_model = os.environ.get("MISTRAL_CHAT_MODEL", "mistral-large-latest")

    async def stream_response(
        self,
        session_id: str,
        user_message: str,
        image_uris: Optional[list[str]] = None,
    ) -> AsyncIterator[str]:
        session_manager.clear_interrupted(session_id)

        # Classify intent and clean the message
        classified = await self._classifier.classify(user_message)

        # Log classification for debugging
        print(
            f"[Intent] {classified.intent.value} (confidence={classified.confidence:.2f}): "
            f"'{user_message[:50]}...' -> '{classified.cleaned_text[:50]}...'"
        )

        # Store the cleaned text as the user turn
        session_manager.add_turn(session_id, role="user", text=classified.cleaned_text)

        full_response = ""

        if classified.intent == IntentType.COMMAND:
            # Route to vibe CLI for commands
            try:
                async for line in self._executor.execute(
                    classified.cleaned_text, session_id=session_id
                ):
                    if session_manager.is_interrupted(session_id):
                        break
                    full_response += line + "\n"
                    yield line + "\n"
            except Exception as e:
                error_msg = f"\n[Error: {type(e).__name__}: {e}]"
                full_response += error_msg
                yield error_msg

        else:
            # Route to Mistral chat for prompts/questions
            async for chunk in self._stream_chat_response(
                session_id, classified.cleaned_text
            ):
                if session_manager.is_interrupted(session_id):
                    break
                full_response += chunk
                yield chunk

        if full_response.strip():
            session_manager.add_turn(session_id, role="assistant", text=full_response)

    async def _stream_chat_response(
        self, session_id: str, message: str
    ) -> AsyncIterator[str]:
        """Stream a conversational response from Mistral chat."""
        if not self._chat_client:
            yield "Error: MISTRAL_API_KEY not configured for chat responses.\n"
            return

        # Build conversation history
        turns = session_manager.get_turns(session_id)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful coding assistant. Answer questions clearly and concisely. "
                    "When explaining code concepts, use examples when helpful."
                ),
            }
        ]

        # Add recent conversation history (last 10 turns)
        for turn in turns[-10:]:
            messages.append({"role": turn["role"], "content": turn["text"]})

        # Add current message
        messages.append({"role": "user", "content": message})

        try:
            stream = await self._chat_client.chat.stream_async(
                model=self._chat_model,
                messages=messages,
            )

            async for event in stream:
                if event.data.choices and event.data.choices[0].delta.content:
                    yield event.data.choices[0].delta.content

        except Exception as e:
            yield f"\n[Chat Error: {type(e).__name__}: {e}]\n"

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
