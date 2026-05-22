"""Singleton MIDI bridge — holds connection state, input listener, and response queue.

Architecture
------------
Output side:  bridge.send_raw(bytes) → mido output port → IAC Driver → FL Studio
Input side:   FL Studio → IAC Driver → mido input port (callback) → _response_queue
                                                                    ↓
              tools call bridge.query(sysex, expected_cmd) → async poll with timeout

Dry-run:      send_raw / query both short-circuit; query returns None (callers
              substitute a canned "dry_run" preview response).
"""

from __future__ import annotations

import asyncio
import json
import queue as thread_queue
import sys
import time
from typing import Any, Callable

import mido

from .errors import ErrorCode, FLMCPError
from .protocol import decode_sysex
from .transports import MIDITransport, get_transport

# How long to poll the response queue between asyncio yields (seconds)
_POLL_INTERVAL = 0.05


class FLStudioBridge:
    """Singleton that owns the MIDI I/O ports and bidirectional response queue."""

    _instance: FLStudioBridge | None = None

    def __init__(self) -> None:
        import os
        self._output_port: mido.ports.BaseOutput | None = None
        self._input_port: mido.ports.BaseInput | None = None
        self._output_port_name: str = ""
        self._input_port_name: str = ""
        self._transport: MIDITransport = get_transport()
        self._dry_run: bool = os.getenv("FL_MCP_DRY_RUN", "0") == "1"
        # Thread-safe queue for MIDI responses from FL Studio
        self._response_queue: thread_queue.Queue[dict[str, Any]] = thread_queue.Queue(maxsize=64)
        # Lock to serialise concurrent bidirectional queries (prevents response swapping)
        self._query_lock: asyncio.Lock | None = None

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    @classmethod
    def get(cls) -> FLStudioBridge:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def transport(self) -> MIDITransport:
        return self._transport

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    @property
    def connected(self) -> bool:
        return self._output_port is not None or self._dry_run

    @property
    def listening(self) -> bool:
        """True if the MIDI input listener is active."""
        return self._input_port is not None

    @property
    def port_name(self) -> str:
        return self._output_port_name

    @property
    def input_port_name(self) -> str:
        return self._input_port_name

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(
        self,
        port_name_hint: str,
        dry_run: bool = False,
        input_port_hint: str | None = None,
    ) -> str:
        """Open the MIDI output port and optionally start the input listener.

        Args:
            port_name_hint:  Full or partial output port name.
            dry_run:         When True, skip all real MIDI I/O.
            input_port_hint: Full or partial input port name for receiving FL Studio
                             responses. When None, auto-detected from the same hint as
                             the output. Pass "" to disable input explicitly.

        Returns:
            Exact output port name opened, or "(dry-run)".
        """
        self._dry_run = dry_run

        if dry_run:
            self._output_port_name = "(dry-run)"
            self._input_port_name = "(dry-run)"
            return self._output_port_name

        if port_name_hint.startswith("ws://") or port_name_hint.startswith("wss://"):
            self._transport = get_transport(port_name_hint)

        # --- Output port ---
        outputs = self._transport.list_output_ports()
        exact_out = self._transport.resolve_port(port_name_hint, outputs)
        self._close_output()
        try:
            self._output_port = self._transport.open_output(exact_out)
        except Exception as exc:
            raise FLMCPError(
                ErrorCode.MIDI_CONNECT_FAILED,
                f"Could not open MIDI output {exact_out!r}: {exc}",
                {"port": exact_out},
            ) from exc
        self._output_port_name = exact_out

        # --- Input port (bidirectional) ---
        # Use the explicit hint, or fall back to the same hint as the output.
        # Pass input_port_hint="" to skip.
        effective_input_hint = input_port_hint if input_port_hint is not None else port_name_hint
        if effective_input_hint:
            self._start_listener(effective_input_hint)

        return exact_out

    def _start_listener(self, hint: str) -> bool:
        """Try to open the MIDI input port for receiving FL Studio responses.

        Returns True on success, False if no matching port found.
        Non-fatal — tools degrade gracefully when the listener is absent.
        """
        try:
            inputs = self._transport.list_input_ports()
            exact_in = self._transport.resolve_port(hint, inputs)
            self._close_input()
            self._input_port = self._transport.open_input(exact_in, callback=self._on_midi_in)
            self._input_port_name = exact_in
            return True
        except Exception:
            # No matching input port — that's fine, bidirectional tools will timeout
            return False

    def _on_midi_in(self, msg: mido.Message) -> None:
        """Called by mido in its background thread for each incoming message."""
        if msg.type != "sysex":
            return
        # mido strips F0/F7 from sysex data; reconstruct full bytes for decode_sysex
        raw = bytes([0xF0]) + bytes(msg.data) + bytes([0xF7])
        result = decode_sysex(raw)
        if result is None:
            return
        cmd, payload = result
        try:
            self._response_queue.put_nowait({"cmd": cmd, "payload": payload})
        except thread_queue.Full:
            print(
                f"[FL MCP Bridge] WARNING: response queue full — dropping cmd {cmd:#04x}. "
                "This may cause a tool timeout. Consider calling fl_disconnect and reconnecting.",
                file=sys.stderr,
            )

    def disconnect(self) -> None:
        self._close_output()
        self._close_input()
        # Always clear names + dry_run so status() reflects a clean slate
        self._output_port_name = ""
        self._input_port_name = ""
        self._dry_run = False
        self._query_lock = None  # reset lock so a new event loop gets a fresh one
        self._transport = get_transport()

    def _close_output(self) -> None:
        if self._output_port is not None:
            try:
                self._output_port.close()
            except Exception:
                pass
            self._output_port = None
            self._output_port_name = ""

    def _close_input(self) -> None:
        if self._input_port is not None:
            try:
                self._input_port.close()
            except Exception:
                pass
            self._input_port = None
            self._input_port_name = ""

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def _require_connection(self) -> None:
        if not self.connected:
            raise FLMCPError(
                ErrorCode.NOT_CONNECTED,
                "Not connected to FL Studio. Call fl_connect first.",
                {"hint": "Use fl_list_midi_ports to find your IAC Driver port name."},
            )

    def send_raw(self, raw_bytes: bytes) -> dict[str, Any]:
        """Send raw bytes (SysEx or any MIDI message).

        In dry-run mode returns a preview dict without touching any port.
        """
        self._require_connection()
        hex_str = raw_bytes.hex(" ").upper()

        if self._dry_run:
            return {
                "dry_run": True,
                "would_send_bytes": hex_str,
                "byte_count": len(raw_bytes),
            }

        msg = mido.Message.from_bytes(raw_bytes)
        try:
            self._output_port.send(msg)
        except (mido.PortsError, OSError, AttributeError) as exc:
            self.disconnect()
            raise FLMCPError(
                ErrorCode.CONNECTION_ERROR,
                f"MIDI connection is stale or disconnected: {exc}",
                {"original_error": str(exc)},
            ) from exc
        return {"sent": True, "bytes": hex_str}

    async def send_raw_with_ack(
        self,
        raw_bytes: bytes,
        cmd_byte: int,
        timeout_ms: int = 200,
    ) -> dict[str, Any]:
        """Send raw bytes and wait for RESP_ACK from FL Studio for this command."""
        self._require_connection()
        hex_str = raw_bytes.hex(" ").upper()

        if self._dry_run:
            return {
                "dry_run": True,
                "would_send_bytes": hex_str,
                "byte_count": len(raw_bytes),
                "ack_received": True,
            }

        if not self.listening:
            # If no input port is active, we cannot listen for ACK, so we degrade gracefully
            self.send_raw(raw_bytes)
            return {"sent": True, "bytes": hex_str, "ack_received": False, "reason": "No input listener"}

        from .protocol import RESP_ACK, decode_resp_ack

        async with self._get_query_lock():
            self._drain_queue()
            self.send_raw(raw_bytes)

            deadline = time.monotonic() + timeout_ms / 1000.0
            while time.monotonic() < deadline:
                try:
                    item = self._response_queue.get_nowait()
                    if item["cmd"] == RESP_ACK:
                        acked_cmd = decode_resp_ack(item["payload"])
                        if acked_cmd == cmd_byte:
                            return {"sent": True, "bytes": hex_str, "ack_received": True}
                    # Put it back if it's not ours
                    try:
                        self._response_queue.put_nowait(item)
                    except thread_queue.Full:
                        pass
                except thread_queue.Empty:
                    pass
                await asyncio.sleep(_POLL_INTERVAL)

        raise FLMCPError(
            ErrorCode.TIMEOUT,
            f"Command {cmd_byte:#x} write verification (ACK) timed out after {timeout_ms}ms.",
            {"cmd": cmd_byte, "timeout_ms": timeout_ms}
        )

    async def send_write(
        self,
        raw_bytes: bytes,
        cmd_byte: int,
        ack: bool = False,
        timeout_ms: int = 200,
    ) -> dict[str, Any]:
        """Send a write command SysEx, optionally waiting for RESP_ACK from FL Studio."""
        if ack:
            return await self.send_raw_with_ack(raw_bytes, cmd_byte, timeout_ms)
        else:
            return self.send_raw(raw_bytes)


    # ------------------------------------------------------------------
    # Bidirectional query
    # ------------------------------------------------------------------

    def _drain_queue(self) -> None:
        """Discard any stale responses before sending a new query."""
        while True:
            try:
                self._response_queue.get_nowait()
            except thread_queue.Empty:
                break

    def _get_query_lock(self) -> asyncio.Lock:
        """Lazily create the query lock on the running event loop."""
        if self._query_lock is None:
            self._query_lock = asyncio.Lock()
        return self._query_lock

    async def query(
        self,
        sysex_bytes: bytes,
        expected_cmd: int,
        timeout_ms: int = 2000,
    ) -> dict[str, Any] | None:
        """Send a query SysEx and wait for a matching response from FL Studio.

        Serialised via asyncio.Lock so concurrent tool calls cannot steal each
        other's responses (e.g. fl_get_status and fl_list_channels called at
        the same time will queue rather than swap payloads).

        Returns the response dict {cmd, payload} on success, or None on timeout.
        Returns None immediately in dry-run mode (callers substitute mock data).
        """
        self._require_connection()

        if self._dry_run:
            return None

        if not self.listening:
            # No input port — send the query but return None (caller shows hint)
            self.send_raw(sysex_bytes)
            return None

        async with self._get_query_lock():
            self._drain_queue()
            self.send_raw(sysex_bytes)

            deadline = time.monotonic() + timeout_ms / 1000.0
            while time.monotonic() < deadline:
                try:
                    item = self._response_queue.get_nowait()
                    if item["cmd"] == expected_cmd:
                        return item
                    # Not our response — put it back for the next waiter
                    try:
                        self._response_queue.put_nowait(item)
                    except thread_queue.Full:
                        pass
                except thread_queue.Empty:
                    pass
                await asyncio.sleep(_POLL_INTERVAL)

        return None  # timeout

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        return {
            "connected":         self.connected,
            "port":              self._output_port_name,
            "input_port":        self._input_port_name,
            "listening":         self.listening,
            "dry_run":           self._dry_run,
            "platform_transport": type(self._transport).__name__,
        }


def format_result(data: dict[str, Any]) -> str:
    """Consistent JSON serialisation for tool return values."""
    return json.dumps(data, indent=2)
