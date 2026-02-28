import asyncio
import json
import os
import subprocess
from typing import AsyncIterator, Dict, Any, Optional, Callable


class ACPClient:
    """
    Client for the Agent Client Protocol (ACP) server.
    Communicates with a vibe-acp subprocess via JSON-RPC over stdin/stdout.
    """

    def __init__(self, cli_path: str = "vibe-acp") -> None:
        self.cli_path = cli_path
        self.proc: Optional[asyncio.Process] = None
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._handlers: Dict[str, list[Callable]] = {}
        self._loop_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Launch the vibe-acp subprocess and start the response loop."""
        self.proc = await asyncio.create_subprocess_exec(
            self.cli_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._loop_task = asyncio.create_task(self._read_loop())
        
        # Initial handshake
        await self.call("initialize", {
            "capabilities": {},
            "clientInfo": {"name": "mistral-vibe-rc", "version": "0.1.0"}
        })

    async def stop(self) -> None:
        """Gracefully stop the client."""
        if self._loop_task:
            self._loop_task.cancel()
        if self.proc:
            try:
                self.proc.terminate()
                await self.proc.wait()
            except ProcessLookupError:
                pass
        self.proc = None

    def on(self, method: str, handler: Callable) -> None:
        """Register a notification handler."""
        if method not in self._handlers:
            self._handlers[method] = []
        self._handlers[method].append(handler)

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send a JSON-RPC request and wait for the result."""
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("ACP client not started or stdin unavailable")

        self._request_id += 1
        req_id = self._request_id
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[req_id] = future

        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {}
        }
        
        payload = json.dumps(request) + "\n"
        self.proc.stdin.write(payload.encode())
        await self.proc.stdin.drain()

        return await future

    async def _read_loop(self) -> None:
        """Read lines from stdout and dispatch responses/notifications."""
        try:
            while self.proc and self.proc.stdout:
                line_bytes = await self.proc.stdout.readline()
                if not line_bytes:
                    break

                line = line_bytes.decode().strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    print(f"[ACP Client] Error decoding line: {line}")
                    continue

                if "id" in data:
                    # Response to a request
                    req_id = data["id"]
                    future = self._pending_requests.pop(req_id, None)
                    if future:
                        if "error" in data:
                            future.set_exception(RuntimeError(str(data["error"])))
                        else:
                            future.set_result(data.get("result"))
                elif "method" in data:
                    # Notification or request from server (not handling server requests yet)
                    method = data["method"]
                    params = data.get("params", {})
                    if method in self._handlers:
                        for handler in self._handlers[method]:
                            if asyncio.iscoroutinefunction(handler):
                                asyncio.create_task(handler(params))
                            else:
                                handler(params)
        except Exception as e:
            print(f"[ACP Client] Read loop error: {e}")
        finally:
            # Cancel all pending requests
            for future in self._pending_requests.values():
                if not future.done():
                    future.cancel()
            self._pending_requests.clear()

    # --- Session Management ---

    async def create_session(self, session_id: Optional[str] = None) -> Any:
        params: Dict[str, Any] = {}
        if session_id:
            params["sessionId"] = session_id
        return await self.call("session.create", params)

    async def prompt(self, session_id: str, text: str, images: Optional[list[str]] = None) -> None:
        params: Dict[str, Any] = {
            "sessionId": session_id,
            "text": text
        }
        if images:
            params["images"] = images
        await self.call("session.prompt", params)

    async def interrupt(self, session_id: str) -> None:
        await self.call("session.interrupt", {"sessionId": session_id})
