"""WebSocket MIDI transport — breaks the physical MIDI hardware/IAC bus constraint.

Enables local network communication (WebSocket) to control remote or containerized FL Studio instances.
The MCP server hosts a WebSocket server, and FL Studio script clients connect to it.
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Callable, Set

import mido

from .base import MIDITransport


def parse_ws_url(url: str) -> tuple[str, int]:
    """Parse a websocket URL into host and port.
    
    Examples:
        "ws://127.0.0.1:8765" -> ("127.0.0.1", 8765)
        "ws://localhost" -> ("localhost", 8765)
    """
    cleaned = url
    if url.startswith("ws://"):
        cleaned = url[5:]
    elif url.startswith("wss://"):
        cleaned = url[6:]

    if ":" in cleaned:
        host, port_str = cleaned.split(":", 1)
        try:
            return host or "0.0.0.0", int(port_str)
        except ValueError:
            return host or "0.0.0.0", 8765
    else:
        return cleaned or "0.0.0.0", 8765


class WebSocketOutputPort:
    """Mock mido output port that sends messages over WebSocket."""

    def __init__(self, transport: WebSocketMIDITransport, name: str):
        self.transport = transport
        self.name = name
        self._closed = False

    def send(self, message: mido.Message) -> None:
        if self._closed:
            raise RuntimeError("Output port is closed.")
        self.transport.send_bytes(message.bytes())

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self.transport.decrement_ports()


class WebSocketInputPort:
    """Mock mido input port that receives messages over WebSocket."""

    def __init__(self, transport: WebSocketMIDITransport, name: str):
        self.transport = transport
        self.name = name
        self._closed = False

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self.transport.decrement_ports()


class WebSocketMIDITransport(MIDITransport):
    """WebSocket MIDI transport serving as a network bridge for FL Studio."""

    def __init__(self) -> None:
        self._server_thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server = None
        self._clients: Set[Any] = set()
        self._input_callback: Callable[[mido.Message], None] | None = None
        self._host = "0.0.0.0"
        self._port = 8765
        self._port_ref_count = 0
        self._lock = threading.Lock()
        self._server_ready = threading.Event()
        self._actual_url = ""

    def list_output_ports(self) -> list[str]:
        return [self._actual_url or "ws://localhost:8765"]

    def list_input_ports(self) -> list[str]:
        return [self._actual_url or "ws://localhost:8765"]

    def resolve_port(self, partial: str, ports: list[str]) -> str:
        return partial

    def open_output(self, port_name: str) -> WebSocketOutputPort:
        with self._lock:
            self._actual_url = port_name
            self._start_server_once(port_name)
            self._port_ref_count += 1
            return WebSocketOutputPort(self, port_name)

    def open_input(self, port_name: str, callback=None) -> WebSocketInputPort:
        with self._lock:
            self._actual_url = port_name
            self._start_server_once(port_name)
            self._input_callback = callback
            self._port_ref_count += 1
            return WebSocketInputPort(self, port_name)

    @property
    def default_output_hint(self) -> str:
        return "ws://localhost:8765"

    def decrement_ports(self) -> None:
        with self._lock:
            self._port_ref_count -= 1
            if self._port_ref_count <= 0:
                self._stop_server()

    def _start_server_once(self, port_name: str) -> None:
        if self._server_thread is not None:
            return

        host, port = parse_ws_url(port_name)
        self._host = host
        self._port = port

        self._server_ready.clear()
        self._loop = asyncio.new_event_loop()
        self._server_thread = threading.Thread(
            target=self._run_server,
            daemon=True,
            name="WebSocketMIDITransportServer",
        )
        self._server_thread.start()
        
        # Wait up to 5 seconds for the server to start up
        if not self._server_ready.wait(timeout=5.0):
            self._stop_server()
            raise RuntimeError(f"WebSocket server failed to start on {host}:{port} within 5 seconds.")

    def _run_server(self) -> None:
        import websockets
        asyncio.set_event_loop(self._loop)

        async def handler(websocket):
            self._clients.add(websocket)
            try:
                async for message in websocket:
                    try:
                        self._handle_client_message(message)
                    except Exception as e:
                        import sys
                        print(f"[FL STUDIO MCP] Exception in _handle_client_message: {e}", file=sys.stderr)
            except websockets.exceptions.ConnectionClosed:
                pass
            except Exception as e:
                import sys
                print(f"[FL STUDIO MCP] Exception in websocket handler: {e}", file=sys.stderr)
            finally:
                self._clients.discard(websocket)

        async def main():
            try:
                self._server = await websockets.serve(handler, self._host, self._port)
            except Exception as exc:
                self._server_ready.set()
                raise exc

            self._server_ready.set()
            
            # Keep loop active
            while True:
                await asyncio.sleep(3600)

        try:
            self._loop.run_until_complete(main())
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    def _handle_client_message(self, message: str | bytes) -> None:
        if not self._input_callback:
            return

        raw_bytes = b""
        if isinstance(message, bytes):
            raw_bytes = message
        elif isinstance(message, str):
            try:
                # Try parsing as JSON
                data = json.loads(message)
                if isinstance(data, dict):
                    if "bytes" in data:
                        raw_bytes = bytes.fromhex(data["bytes"])
                    elif "midi" in data:
                        raw_bytes = bytes(data["midi"])
                elif isinstance(data, list):
                    raw_bytes = bytes(data)
            except json.JSONDecodeError:
                # Treat as raw hex string
                try:
                    raw_bytes = bytes.fromhex(message.strip())
                except ValueError:
                    pass

        if raw_bytes:
            try:
                msg = mido.Message.from_bytes(raw_bytes)
                self._input_callback(msg)
            except Exception as e:
                import sys
                print(f"[FL STUDIO MCP] Exception invoking input callback: {e}", file=sys.stderr)

    def send_bytes(self, raw_bytes: bytes | list[int]) -> None:
        actual_bytes = bytes(raw_bytes) if not isinstance(raw_bytes, bytes) else raw_bytes
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(actual_bytes), self._loop)

    async def _broadcast(self, raw_bytes: bytes) -> None:
        if not self._clients:
            return
        
        # Broadcast to all connected clients
        # Support sending binary bytes
        tasks = []
        for client in list(self._clients):
            tasks.append(self._send_to_client(client, raw_bytes))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_to_client(self, client: Any, raw_bytes: bytes) -> None:
        try:
            await client.send(raw_bytes)
        except Exception:
            pass

    def _stop_server(self) -> None:
        if self._loop and self._loop.is_running():
            async def shutdown():
                if self._server:
                    self._server.close()
                    await self._server.wait_closed()
                for client in list(self._clients):
                    try:
                        await client.close()
                    except Exception:
                        pass
            
            future = asyncio.run_coroutine_threadsafe(shutdown(), self._loop)
            try:
                future.result(timeout=2.0)
            except Exception:
                pass
            
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._server_thread:
            self._server_thread.join(timeout=2.0)
            self._server_thread = None
            self._loop = None
            self._server = None
            self._clients.clear()
            self._actual_url = ""
