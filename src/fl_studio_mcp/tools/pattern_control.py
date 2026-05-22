"""Tools for bidirectional read and pattern control: fl_get_notes, fl_get_context, fl_set_pattern_length, fl_rename_channel, fl_rename_pattern."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import ErrorCode, FLMCPError
from ..models import (
    GetNotesInput,
    GetContextInput,
    SetPatternLengthInput,
    RenameChannelInput,
    RenamePatternInput,
)
from ..protocol import (
    RESP_CHANNELS,
    RESP_NOTES,
    RESP_STATUS,
    decode_resp_channels,
    decode_resp_notes,
    decode_resp_status,
    encode_get_notes,
    encode_query_channels,
    encode_query_status,
    encode_rename_channel,
    encode_rename_pattern,
    encode_set_pattern_length,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="fl_get_notes",
        annotations={
            "title": "Get Pattern Notes",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_get_notes(params: GetNotesInput) -> str:
        """Read MIDI notes of the active pattern from the session cache in FL Studio.

        Sends CMD_GET_NOTES SysEx (F0 7D 14 F7) to the bridge controller script,
        which queries the session cache of notes played/recorded into the current pattern,
        and responds with RESP_NOTES (F0 7D 14 ...).

        Requires:
          - fl_connect to have been called (input listener active)
          - The FL MCP Bridge script loaded in FL Studio Settings

        Args:
            params (GetNotesInput):
                - timeout_ms (int): Wait timeout in milliseconds (100-10000). Default 2000.

        Returns:
            str: JSON with keys:
                - notes (list[dict]): Note data with pitch, velocity, channel, start_tick, duration_ticks.
                - count (int): Number of notes in pattern
                - source (str): "fl_studio" | "dry_run_preview"
        """
        bridge = FLStudioBridge.get()
        try:
            response = await bridge.query(
                encode_get_notes(), RESP_NOTES, params.timeout_ms
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        if bridge.dry_run:
            mock = [
                {
                    "pitch": 60,
                    "velocity": 100,
                    "channel": 0,
                    "start_tick": 0,
                    "duration_ticks": 96,
                },
                {
                    "pitch": 64,
                    "velocity": 100,
                    "channel": 0,
                    "start_tick": 96,
                    "duration_ticks": 96,
                },
                {
                    "pitch": 67,
                    "velocity": 100,
                    "channel": 0,
                    "start_tick": 192,
                    "duration_ticks": 192,
                },
            ]
            return format_result(
                {
                    "dry_run": True,
                    "notes": mock,
                    "count": len(mock),
                    "source": "dry_run_preview",
                }
            )

        if response is None and not bridge.listening:
            return format_result(
                {
                    "error": ErrorCode.NOT_CONNECTED.value,
                    "hint": "No MIDI input port active. Reconnect with fl_connect to auto-start the listener.",
                }
            )

        if response is None:
            return format_result(
                {
                    "error": "TIMEOUT",
                    "hint": "FL Studio did not respond. Ensure the FL MCP Bridge controller script is loaded in FL Studio → MIDI Settings and the IAC Driver input is enabled.",
                    "timeout_ms": params.timeout_ms,
                }
            )

        try:
            notes = decode_resp_notes(response["payload"])
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.UNKNOWN, f"Bad notes response: {exc}").to_dict()
            )

        return format_result(
            {"notes": notes, "count": len(notes), "source": "fl_studio"}
        )

    @mcp.tool(
        name="fl_get_context",
        annotations={
            "title": "Get Session Context",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_get_context(params: GetContextInput) -> str:
        """Consolidate FL Studio state by querying status, channels, and pattern notes.

        Sequentially sends:
          1. CMD_QUERY_STATUS -> RESP_STATUS
          2. CMD_QUERY_CHANNELS -> RESP_CHANNELS
          3. CMD_GET_NOTES -> RESP_NOTES

        Requires:
          - fl_connect to have been called (input listener active)
          - The FL MCP Bridge script loaded in FL Studio Settings

        Args:
            params (GetContextInput):
                - timeout_ms (int): Response wait timeout 100-10000 ms. Default 2000.

        Returns:
            str: JSON with keys:
                - status (dict): playing, bpm, pattern_index, channel_count
                - channels (list[str]): Names of active channels
                - notes (list[dict]): Notes of the active pattern
                - source (str): "fl_studio" | "dry_run_preview"
        """
        bridge = FLStudioBridge.get()

        if bridge.dry_run:
            mock_status = {
                "playing": False,
                "bpm": 120,
                "pattern_index": 0,
                "channel_count": 5,
            }
            mock_channels = ["Kick", "Snare", "Hi-Hat", "Bass", "Synth Lead"]
            mock_notes = [
                {
                    "pitch": 60,
                    "velocity": 100,
                    "channel": 0,
                    "start_tick": 0,
                    "duration_ticks": 96,
                }
            ]
            return format_result(
                {
                    "dry_run": True,
                    "status": mock_status,
                    "channels": mock_channels,
                    "notes": mock_notes,
                    "source": "dry_run_preview",
                }
            )

        # 1. Query Status
        try:
            status_resp = await bridge.query(
                encode_query_status(), RESP_STATUS, params.timeout_ms
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        if status_resp is None and not bridge.listening:
            return format_result(
                {
                    "error": ErrorCode.NOT_CONNECTED.value,
                    "hint": "No MIDI input port active. Reconnect with fl_connect to auto-start the listener.",
                }
            )
        if status_resp is None:
            return format_result(
                {
                    "error": "TIMEOUT",
                    "message": "Failed to get status context.",
                    "timeout_ms": params.timeout_ms,
                }
            )

        try:
            status_data = decode_resp_status(status_resp["payload"])
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.UNKNOWN, f"Bad status context: {exc}").to_dict()
            )

        # 2. Query Channels
        try:
            channels_resp = await bridge.query(
                encode_query_channels(), RESP_CHANNELS, params.timeout_ms
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        if channels_resp is None:
            return format_result(
                {
                    "error": "TIMEOUT",
                    "message": "Failed to get channel rack context.",
                    "timeout_ms": params.timeout_ms,
                }
            )

        try:
            channels_data = decode_resp_channels(channels_resp["payload"])
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.UNKNOWN, f"Bad channel context: {exc}").to_dict()
            )

        # 3. Query Notes
        try:
            notes_resp = await bridge.query(
                encode_get_notes(), RESP_NOTES, params.timeout_ms
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        if notes_resp is None:
            return format_result(
                {
                    "error": "TIMEOUT",
                    "message": "Failed to get active pattern notes context.",
                    "timeout_ms": params.timeout_ms,
                }
            )

        try:
            notes_data = decode_resp_notes(notes_resp["payload"])
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.UNKNOWN, f"Bad notes context: {exc}").to_dict()
            )

        return format_result(
            {
                "status": status_data,
                "channels": channels_data,
                "notes": notes_data,
                "source": "fl_studio",
            }
        )

    @mcp.tool(
        name="fl_set_pattern_length",
        annotations={
            "title": "Set Pattern Length",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_set_pattern_length(params: SetPatternLengthInput) -> str:
        """Modify the length of a pattern in FL Studio (in beats).

        Sends CMD_SET_PATTERN_LENGTH SysEx to the bridge script, which calls
        patterns.setPatternLength(index, length).

        Requires fl_connect to have been called first.

        Args:
            params (SetPatternLengthInput):
                - pattern_index (int 0-999): Zero-based pattern index.
                - length_beats (int 1-999): Target length in beats.

        Returns:
            str: JSON confirmation
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_set_pattern_length(params.pattern_index, params.length_beats)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["pattern_index"] = params.pattern_index
        result["length_beats"] = params.length_beats
        result["command"] = "SET_PATTERN_LENGTH"
        return format_result(result)

    @mcp.tool(
        name="fl_rename_channel",
        annotations={
            "title": "Rename Channel",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_rename_channel(params: RenameChannelInput) -> str:
        """Rename a channel rack slot in FL Studio.

        Sends CMD_RENAME_CHANNEL SysEx to the bridge script, which calls
        channels.setChannelName(index, name).

        Requires fl_connect to have been called first.

        Args:
            params (RenameChannelInput):
                - channel_index (int 0-127): Zero-based channel rack slot.
                - name (str 1-14 chars): New name (7-bit ASCII only).

        Returns:
            str: JSON confirmation
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_rename_channel(params.channel_index, params.name)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["channel_index"] = params.channel_index
        result["name"] = params.name
        result["command"] = "RENAME_CHANNEL"
        return format_result(result)

    @mcp.tool(
        name="fl_rename_pattern",
        annotations={
            "title": "Rename Pattern",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_rename_pattern(params: RenamePatternInput) -> str:
        """Rename a pattern slot in FL Studio.

        Sends CMD_RENAME_PATTERN SysEx to the bridge script, which calls
        patterns.setPatternName(index, name).

        Requires fl_connect to have been called first.

        Args:
            params (RenamePatternInput):
                - pattern_index (int 0-999): Zero-based pattern index.
                - name (str 1-14 chars): New name (7-bit ASCII only).

        Returns:
            str: JSON confirmation
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_rename_pattern(params.pattern_index, params.name)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["pattern_index"] = params.pattern_index
        result["name"] = params.name
        result["command"] = "RENAME_PATTERN"
        return format_result(result)
