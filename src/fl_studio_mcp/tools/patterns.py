"""Tools: fl_create_pattern, fl_select_pattern."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import ErrorCode, FLMCPError
from ..models import CreatePatternInput, SelectPatternInput
from ..protocol import encode_new_pattern, encode_select_pattern


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
