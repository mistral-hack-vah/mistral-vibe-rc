# python/vibe_executor.py
"""
Mistral Vibe CLI bridge.

`VibeExecutor.execute()` spawns the `mistral-vibe` CLI (or any compatible
binary configured via VIBE_CLI_PATH) as an async subprocess, feeds it a
command text via stdin, and yields stdout lines back to the WebSocket
handler as `agent_delta` events.

Usage example:
    executor = VibeExecutor()
    async for line in executor.execute("run all tests", session_id="s1"):
        await ws_send(ws, "agent_delta", {"text": line})
"""

import asyncio
import os
import subprocess
from typing import AsyncIterator


class VibeExecutor:
    """
    Async subprocess wrapper around the Mistral Vibe CLI.

    Config via env vars:
        VIBE_CLI_PATH   — path/name of the CLI binary (default: "mistral-vibe")
        VIBE_TIMEOUT    — max seconds to wait for a response (default: 60)
    """

    def __init__(self) -> None:
        self.cli_path = os.environ.get("VIBE_CLI_PATH", "mistral-vibe")
        self.timeout = float(os.environ.get("VIBE_TIMEOUT", "60"))

    async def execute(
        self,
        command_text: str,
        session_id: str,
    ) -> AsyncIterator[str]:
        """
        Send *command_text* to the Vibe CLI and stream output lines.

        Yields:
            One non-empty stripped line at a time from the CLI's stdout.

        Raises:
            RuntimeError  — if the CLI exits with a non-zero code.
        """
        proc = await asyncio.create_subprocess_exec(
            self.cli_path,
            "--no-color",      # avoid ANSI escape codes in streamed output
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Write the command and signal EOF on stdin
        try:
            cmd_bytes = (command_text.strip() + "\n").encode()
            proc.stdin.write(cmd_bytes)
            await proc.stdin.drain()
            proc.stdin.close()
        except (BrokenPipeError, ConnectionResetError):
            # Process may have already exited
            pass

        # Stream stdout line by line with an overall timeout
        deadline = asyncio.get_event_loop().time() + self.timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                proc.kill()
                raise RuntimeError(
                    f"[vibe] Timeout after {self.timeout}s for session={session_id}"
                )
            try:
                line_bytes = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=remaining
                )
            except asyncio.TimeoutError:
                proc.kill()
                raise RuntimeError(
                    f"[vibe] Timeout waiting for output in session={session_id}"
                )

            if not line_bytes:
                # EOF — CLI finished writing
                break

            line = line_bytes.decode(errors="replace").rstrip()
            if line:
                yield line

        # Wait for process exit and check return code
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()

        if proc.returncode not in (0, None):
            stderr_bytes = b""
            if proc.stderr:
                try:
                    stderr_bytes = await asyncio.wait_for(
                        proc.stderr.read(), timeout=2.0
                    )
                except asyncio.TimeoutError:
                    pass
            raise RuntimeError(
                f"[vibe] CLI exited with code {proc.returncode} "
                f"for session={session_id}: "
                f"{stderr_bytes.decode(errors='replace').strip()}"
            )
