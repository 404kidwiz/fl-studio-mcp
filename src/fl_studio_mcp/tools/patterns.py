"""Tools: fl_create_pattern, fl_select_pattern, fl_clear_pattern."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import ErrorCode, FLMCPError
from ..models import ClearPatternInput, CreatePatternInput, SelectPatternInput
from ..protocol import encode_clear_pattern, encode_new_pattern, encode_select_pattern


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="fl_create_pattern",
        annotations={
            "title": "Create New Pattern",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_create_pattern(params: CreatePatternInput) -> str:
        """Create a new empty pattern in FL Studio.

        Sends CMD_NEW_PATTERN (F0 7D 09 F7) to the FL MCP Bridge script,
        which calls patterns.jumpToPattern(patterns.patternCount()) to
        navigate to a new empty slot.

        Requires fl_connect to have been called first.

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - command (str): "NEW_PATTERN"
                - bytes (str): hex of SysEx sent
        """
        bridge = FLStudioBridge.get()
        try:
            result = bridge.send_raw(encode_new_pattern())
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        result["command"] = "NEW_PATTERN"
        return format_result(result)

    @mcp.tool(
        name="fl_select_pattern",
        annotations={
            "title": "Select Pattern",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_select_pattern(params: SelectPatternInput) -> str:
        """Jump to a specific pattern in FL Studio's playlist/pattern picker.

        Sends CMD_SELECT_PATTERN (F0 7D 0A pat_idx F7) to the bridge script,
        which calls patterns.jumpToPattern(index).

        Use fl_get_status to check the current pattern_index first.

        Requires fl_connect to have been called first.

        Args:
            params (SelectPatternInput):
                - pattern_index (int 0-127): Zero-based pattern index to select.

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - pattern_index (int): the index sent
                - command (str): "SELECT_PATTERN"
                - bytes (str): hex of SysEx sent
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_select_pattern(params.pattern_index)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict())

        result["pattern_index"] = params.pattern_index
        result["command"] = "SELECT_PATTERN"
        return format_result(result)

    @mcp.tool(
        name="fl_clear_pattern",
        annotations={
            "title": "Clear Current Pattern",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_clear_pattern(params: ClearPatternInput) -> str:
        """Erase all notes from the currently selected pattern in FL Studio.

        Sends CMD_CLEAR_PATTERN (F0 7D 0F F7) to the bridge script, which
        calls patterns.clearCurrentPattern() to wipe all notes.

        Use this before fl_insert_notes or fl_add_chord_progression when you
        want to replace rather than accumulate. Without clearing first, every
        insert call adds on top of existing notes.

        Tip: pair with fl_select_pattern to clear a specific pattern:
          1. fl_select_pattern(pattern_index=2)
          2. fl_clear_pattern()
          3. fl_insert_notes(...)

        ⚠️  Destructive — cannot be undone via MCP. FL Studio's own Ctrl+Z
        still works manually after this call.

        Requires fl_connect and the FL MCP Bridge script loaded.

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - command (str): "CLEAR_PATTERN"
                - bytes (str): hex of SysEx sent
        """
        bridge = FLStudioBridge.get()
        try:
            result = bridge.send_raw(encode_clear_pattern())
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        result["command"] = "CLEAR_PATTERN"
        return format_result(result)
