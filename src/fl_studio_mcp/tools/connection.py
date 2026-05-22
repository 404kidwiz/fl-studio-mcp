"""Tools: fl_connect, fl_disconnect — open/close MIDI port and session state."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import FLMCPError
from ..models import ConnectInput, DisconnectInput, PingInput


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="fl_connect",
        annotations={
            "title": "Connect to FL Studio",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_connect(params: ConnectInput) -> str:
        """Open the MIDI output port used to send commands to FL Studio.

        Must be called before play_transport, stop_transport, set_tempo,
        insert_notes, add_chord_progression, or save_project_as.

        Dry-run mode (dry_run=true) enables full tool exploration without
        sending any MIDI — useful for testing prompts and validating inputs.

        Args:
            params (ConnectInput):
                - port_name (str): MIDI output port name. Partial match OK.
                  Use fl_list_midi_ports to discover names.
                - dry_run (bool): If true, no MIDI is sent. Defaults to false.

        Returns:
            str: JSON with keys:
                - connected (bool)
                - port (str): exact port name opened (or "(dry-run)")
                - dry_run (bool)
                - platform_transport (str): transport class used

        Examples:
            - Connect for real:    {"port_name": "IAC Driver Bus 1"}
            - Explore without MIDI: {"port_name": "IAC Driver Bus 1", "dry_run": true}
        """
        bridge = FLStudioBridge.get()
        try:
            bridge.connect(
                params.port_name,
                dry_run=params.dry_run,
                input_port_hint=params.input_port_name,
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            from ..errors import ErrorCode

            return format_result(
                FLMCPError(ErrorCode.MIDI_PORT_NOT_FOUND, str(exc)).to_dict()
            )

        return format_result(bridge.status())

    @mcp.tool(
        name="fl_disconnect",
        annotations={
            "title": "Disconnect from FL Studio",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_disconnect(params: DisconnectInput) -> str:
        """Close the active MIDI output and input ports.

        Useful when switching ports, recovering from a stale connection after
        FL Studio crashes, or cleanly ending a session before restart.

        Safe to call even if not currently connected — returns the resulting
        status either way.

        Returns:
            str: JSON bridge status after disconnecting:
                - connected (bool): always False after this call
                - port (str): empty string after disconnect
                - dry_run (bool)
                - platform_transport (str)
        """
        bridge = FLStudioBridge.get()
        bridge.disconnect()
        return format_result({**bridge.status(), "disconnected": True})

    @mcp.tool(
        name="fl_ping",
        annotations={
            "title": "Ping FL Studio",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_ping(params: PingInput) -> str:
        """Send a lightweight ping to FL Studio to verify connection and script responsiveness.

        Sends CMD_PING (0x18) with a challenge byte, and waits for a matching pong response.
        If the connection is stale or non-responsive, raises a TIMEOUT error.

        Args:
            params (PingInput):
                - challenge (int): Challenge byte (0-127). Defaults to 42.
                - timeout_ms (int): Response timeout in milliseconds. Defaults to 1000.

        Returns:
            str: JSON with keys:
                - success (bool)
                - challenge (int)
                - response_time_ms (float)
        """
        import time
        from ..protocol import encode_ping, CMD_PING
        from ..errors import ErrorCode

        bridge = FLStudioBridge.get()
        if bridge.dry_run:
            return format_result(
                {
                    "dry_run": True,
                    "success": True,
                    "challenge": params.challenge,
                    "response_time_ms": 0.0,
                }
            )

        try:
            start_time = time.monotonic()
            pong = await bridge.query(
                encode_ping(params.challenge),
                expected_cmd=CMD_PING,
                timeout_ms=params.timeout_ms,
            )
            if pong is None:
                raise FLMCPError(
                    ErrorCode.TIMEOUT,
                    f"Ping challenge {params.challenge} timed out after {params.timeout_ms}ms.",
                    {"challenge": params.challenge, "timeout_ms": params.timeout_ms},
                )

            payload = pong.get("payload", [])
            if not payload or payload[0] != params.challenge:
                raise FLMCPError(
                    ErrorCode.UNKNOWN,
                    f"Ping challenge verification failed: expected {params.challenge}, got {payload}",
                    {"expected": params.challenge, "got": payload},
                )

            elapsed = (time.monotonic() - start_time) * 1000.0
            return format_result(
                {
                    "success": True,
                    "challenge": params.challenge,
                    "response_time_ms": round(elapsed, 2),
                }
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())
