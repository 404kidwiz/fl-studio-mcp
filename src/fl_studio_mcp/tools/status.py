"""Tool: fl_get_status — query FL Studio's current playback state via bidirectional MIDI."""

from mcp.server.fastmcp import FastMCP

import sys
import mido

from ..bridge import FLStudioBridge, format_result
from ..errors import ErrorCode, FLMCPError
from ..models import GetStatusInput
from ..protocol import (
    RESP_STATUS,
    decode_resp_status,
    encode_query_status,
)
from ..automation import get_automation

_NO_LISTENER_HINT = (
    "No MIDI input port is listening. "
    "Reconnect with fl_connect — the input port is auto-detected from the same "
    "port name hint, or pass input_port_name explicitly."
)

_TIMEOUT_HINT = (
    "FL Studio did not respond within the timeout. "
    "Check that: (1) the FL MCP Bridge controller script is loaded in FL Studio's "
    "MIDI Settings, (2) the IAC Driver input is enabled in FL Studio, "
    "(3) FL Studio is open and not frozen."
)


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="fl_get_status",
        annotations={
            "title": "Get FL Studio Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_get_status(params: GetStatusInput) -> str:
        """Query FL Studio's current playback state, BPM, pattern, and channel count.

        Sends a CMD_QUERY_STATUS SysEx (F0 7D 06 F7) to the FL MCP Bridge
        controller script and waits for a RESP_STATUS reply (F0 7D 10 ...).

        Requires:
          - fl_connect to have been called (input listener auto-started)
          - The FL MCP Bridge controller script loaded in FL Studio MIDI Settings

        Args:
            params (GetStatusInput):
                - timeout_ms (int): Response wait timeout 100-10000 ms. Default 2000.

        Returns:
            str: JSON with one of:

            Success:
            {
                "playing":       bool,   # true if transport is running
                "bpm":           int,    # current project BPM
                "pattern_index": int,    # current pattern number (0-based)
                "channel_count": int,    # number of channels in the channel rack
                "listening":     bool,   # whether input port is active
                "source":        "fl_studio"
            }

            Dry-run:
            {
                "dry_run": true,
                "playing": false, "bpm": 120, "pattern_index": 0, "channel_count": 0,
                "source": "dry_run_preview"
            }

            No listener / timeout:
            {
                "error": "...",
                "hint":  "..."
            }
        """
        bridge = FLStudioBridge.get()

        try:
            response = await bridge.query(
                encode_query_status(), RESP_STATUS, params.timeout_ms
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        # Dry-run: bridge.query returns None; return a canned preview
        if bridge.dry_run:
            return format_result(
                {
                    "dry_run": True,
                    "playing": False,
                    "bpm": 120,
                    "pattern_index": 0,
                    "channel_count": 0,
                    "source": "dry_run_preview",
                }
            )

        # No input listener
        if response is None and not bridge.listening:
            return format_result(
                {
                    "error": ErrorCode.NOT_CONNECTED.value,
                    "message": "No MIDI input listener active.",
                    "hint": _NO_LISTENER_HINT,
                }
            )

        # Timeout
        if response is None:
            return format_result(
                {
                    "error": "TIMEOUT",
                    "message": "FL Studio did not respond.",
                    "hint": _TIMEOUT_HINT,
                    "timeout_ms": params.timeout_ms,
                }
            )

        try:
            status = decode_resp_status(response["payload"])
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.UNKNOWN, f"Bad status response: {exc}").to_dict()
            )

        status["listening"] = bridge.listening
        status["source"] = "fl_studio"
        return format_result(status)

    @mcp.tool(
        name="fl_health_check",
        annotations={
            "title": "System Health Check",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_health_check() -> str:
        """Run a full system diagnostic check for the FL Studio MCP environment.

        Returns OS info, Python version, MIDI port availability, current connection status,
        and whether the FL Studio window can be detected. Use this when troubleshooting
        connection or automation issues.

        Returns:
            str: JSON diagnostic report.
        """
        bridge = FLStudioBridge.get()
        automation = get_automation()

        try:
            inputs = mido.get_input_names()
            outputs = mido.get_output_names()
        except Exception as e:
            inputs = [f"Error: {e}"]
            outputs = [f"Error: {e}"]

        try:
            window_found = automation.focus_fl_studio()
        except Exception:
            window_found = False

        report = {
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "mido_version": mido.__version__,
            "bridge": {
                "connected": bridge.connected,
                "listening": bridge.listening,
                "output_port": bridge.port_name,
                "input_port": bridge._input_port.name if bridge._input_port else None,
                "dry_run": bridge.dry_run,
            },
            "automation": {
                "driver": automation.__class__.__name__,
                "window_detected": window_found,
            },
            "system_midi": {
                "inputs_available": inputs,
                "outputs_available": outputs,
            },
        }

        return format_result(report)
