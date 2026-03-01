# python/vibe_executor.py
"""
Mistral Vibe CLI bridge.

`VibeExecutor.execute()` spawns the `vibe` CLI (or any compatible
binary configured via VIBE_CLI_PATH) in programmatic mode (`-p`), and
yields stdout lines back to the WebSocket handler as `agent_delta` events.

Uses a thread + queue internally so it works with any asyncio event loop,
including uvicorn's SelectorEventLoop on Windows.

Usage example:
    executor = VibeExecutor()
    async for line in executor.execute("run all tests", session_id="s1"):
        await ws_send(ws, "agent_delta", {"text": line})
"""

import asyncio
import os
import queue
import subprocess
import threading
from typing import AsyncIterator


class VibeExecutor:
    """
    Subprocess wrapper around the Mistral Vibe CLI.

    Config via env vars:
        VIBE_CLI_PATH   — path/name of the CLI binary (default: "vibe")
        VIBE_TIMEOUT    — max seconds to wait for a response (default: 60)
    """

    def __init__(self) -> None:
        self.cli_path = os.environ.get("VIBE_CLI_PATH", "vibe")
        self.timeout = float(os.environ.get("VIBE_TIMEOUT", "60"))

    async def execute(
        self,
        command_text: str,
        session_id: str,
    ) -> AsyncIterator[str]:
        """
        Send *command_text* to the Vibe CLI and stream output lines.

        Runs the subprocess in a thread so it works with any asyncio event
        loop (including uvicorn's SelectorEventLoop on Windows).

        Yields:
            One non-empty stripped line at a time from the CLI's stdout.

        Raises:
            RuntimeError  — if the CLI exits with a non-zero code.
        """
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"

        line_queue: queue.Queue = queue.Queue()

        def _run() -> None:
            proc = subprocess.Popen(
                [self.cli_path, "-p", command_text.strip(), "--output", "text"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            try:
                for raw in proc.stdout:
                    line = raw.decode(errors="replace").rstrip()
                    if line:
                        line_queue.put(line)
                proc.wait()
                if proc.returncode not in (0, None):
                    stderr_text = proc.stderr.read().decode(errors="replace").strip()
                    line_queue.put(RuntimeError(
                        f"[vibe] CLI exited {proc.returncode} "
                        f"for session={session_id}: {stderr_text}"
                    ))
            except Exception as exc:
                line_queue.put(exc)
            finally:
                line_queue.put(None)  # sentinel

        loop = asyncio.get_event_loop()
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        while True:
            item = await asyncio.wait_for(
                loop.run_in_executor(None, line_queue.get),
                timeout=self.timeout,
            )
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item
