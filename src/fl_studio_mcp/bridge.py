"""Singleton MIDI bridge — holds the open port connection and dry-run state.

All tools call bridge.send_raw() or bridge.send_msg() instead of touching
mido directly, which lets dry-run intercept everything in one place.
"""

from __future__ import annotations

import json
import os
from typing import Any

import mido

from .errors import ErrorCode, FLMCPError
from .transports import MIDITransport, get_transport


class FLStudioBridge:
    """Singleton that owns the MIDI output port and connection metadata."""

    _instance: FLStudioBridge | None = None

    def __init__(self) -> None:
        self._port: mido.ports.BaseOutput | None = None
        self._port_name: str = ""
        self._transport: MIDITransport = get_transport()
        # Dry-run can be toggled via env var OR the connect_fl_studio tool
        self._dry_run: bool = os.getenv("FL_MCP_DRY_RUN", "0") == "1"

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def get(cls) -> FLStudioBridge:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    @property
    def transport(self) -> MIDITransport:
        return self._transport

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    @property
    def connected(self) -> bool:
        return self._port is not None or self._dry_run

    @property
    def port_name(self) -> str:
        return self._port_name

    def connect(self, port_name_hint: str, dry_run: bool = False) -> str:
        """Resolve and open the MIDI output port.

        Args:
            port_name_hint: Full or partial port name (case-insensitive match).
            dry_run: When True, skips actual MIDI I/O.

        Returns:
            The exact port name that was opened (or "(dry-run)").
        """
        self._dry_run = dry_run

        if dry_run:
            self._port_name = "(dry-run)"
            return self._port_name

        outputs = self._transport.list_output_ports()
        exact = self._transport.resolve_port(port_name_hint, outputs)

        # Close previous port if open
        if self._port is not None:
            try:
                self._port.close()
            except Exception:
                pass

        try:
            self._port = self._transport.open_output(exact)
        except Exception as exc:
            raise FLMCPError(
                ErrorCode.MIDI_CONNECT_FAILED,
                f"Could not open MIDI port {exact!r}: {exc}",
                {"port": exact},
            ) from exc

        self._port_name = exact
        return exact

    def disconnect(self) -> None:
        if self._port is not None:
            self._port.close()
            self._port = None
            self._port_name = ""

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def _require_connection(self) -> None:
        if not self.connected:
            raise FLMCPError(
                ErrorCode.NOT_CONNECTED,
                "Not connected to FL Studio. Call connect_fl_studio first.",
                {"hint": "Use list_midi_ports to find your IAC Driver port name."},
            )

    def send_raw(self, raw_bytes: bytes) -> dict[str, Any]:
        """Send raw SysEx bytes (or any raw MIDI bytes).

        In dry-run mode, returns a preview dict instead of sending.
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
        self._port.send(msg)
        return {"sent": True, "bytes": hex_str}

    def send_msg(self, msg: mido.Message) -> dict[str, Any]:
        """Send a mido Message object."""
        return self.send_raw(bytes(msg.bytes()))

    # ------------------------------------------------------------------
    # Helpers used by tools
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "port": self._port_name,
            "dry_run": self._dry_run,
            "platform_transport": type(self._transport).__name__,
        }


def format_result(data: dict[str, Any]) -> str:
    """Consistent JSON serialisation for tool return values."""
    return json.dumps(data, indent=2)
