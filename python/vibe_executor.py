# python/vibe_executor.py
"""
Mistral Vibe ACP bridge.

`VibeExecutor.execute()` connects to the Vibe CLI via the Agent Client
Protocol (ACP) using `simple_acp_client`, sends a query, and yields
streamed response text back to the WebSocket handler as `agent_delta`
events.

Usage example:
    executor = VibeExecutor()
    async for line in executor.execute("run all tests", session_id="s1"):
        await ws_send(ws, "agent_delta", {"text": line})
"""

import os
from typing import AsyncIterator

from simple_acp_client.sdk.client import PyACPSDKClient, PyACPAgentOptions


class VibeExecutor:
    """
    ACP client wrapper around the Mistral Vibe CLI.

    Config via env vars:
        VIBE_CLI_PATH   — path/name of the ACP agent binary (default: "vibe")
        VIBE_MODEL      — model identifier to pass to the agent (optional)
        VIBE_CWD        — working directory for the agent session (optional)
    """

    def __init__(self) -> None:
        self.cli_path = os.environ.get("VIBE_CLI_PATH", "vibe")
        self.model = os.environ.get("VIBE_MODEL")
        self.cwd = os.environ.get("VIBE_CWD")

    async def execute(
        self,
        command_text: str,
        session_id: str,
    ) -> AsyncIterator[str]:
        """
        Send *command_text* to the Vibe ACP agent and stream response text.

        Yields:
            One non-empty text chunk at a time from the agent's response.

        Raises:
            RuntimeError  — if the connection or query fails.
        """
        options = PyACPAgentOptions(
            model=self.model,
            cwd=self.cwd,
        )

        async with PyACPSDKClient(options) as client:
            await client.connect([self.cli_path])
            await client.query(command_text.strip())

            async for message in client.receive_messages():
                if hasattr(message, "text") and message.text:
                    yield message.text
