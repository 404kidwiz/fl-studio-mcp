"""Tools: fl_list_patterns."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import ErrorCode, FLMCPError
from ..models import ListPatternsInput
from ..protocol import (
    RESP_PATTERNS,
    decode_resp_patterns,
    encode_query_patterns,
)

_NO_LISTENER_HINT = (
    "No MIDI input port active. Reconnect with fl_connect to auto-start the listener."
)

_TIMEOUT_HINT = (
    "FL Studio did not respond. Ensure the FL MCP Bridge controller script is "
    "loaded in FL Studio → MIDI Settings and the IAC Driver input is enabled."
)


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="fl_list_patterns",
        annotations={
            "title": "List FL Studio Patterns",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_list_patterns(params: ListPatternsInput) -> str:
        """List all patterns in the FL Studio project.

        Sends CMD_QUERY_PATTERNS (F0 7D 0C F7) and waits for RESP_PATTERNS
        (F0 7D 12 ...) from the FL MCP Bridge controller script.

        Use fl_select_pattern to switch to a specific pattern by index.

        Requires fl_connect (with listening) and the bridge script loaded.

        Args:
            params (ListPatternsInput):
                - timeout_ms (int): Wait timeout in ms. Default 2000.

        Returns:
            str: JSON with keys:
                - patterns (list[str]): Pattern names in order
                - count (int): Total number of patterns
                - source (str): "fl_studio" | "dry_run_preview"

            On timeout / no listener: {"error": ..., "hint": ...}
        """
        bridge = FLStudioBridge.get()

        try:
            response = await bridge.query(encode_query_patterns(), RESP_PATTERNS, params.timeout_ms)
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        if bridge.dry_run:
            mock = ["Pattern 1", "Verse", "Chorus", "Bridge", "Outro"]
            return format_result({"dry_run": True, "patterns": mock, "count": len(mock), "source": "dry_run_preview"})

        if response is None and not bridge.listening:
            return format_result({"error": ErrorCode.NOT_CONNECTED.value, "hint": _NO_LISTENER_HINT})

        if response is None:
            return format_result({"error": "TIMEOUT", "hint": _TIMEOUT_HINT, "timeout_ms": params.timeout_ms})

        pattern_names = decode_resp_patterns(response["payload"])
        return format_result({"patterns": pattern_names, "count": len(pattern_names), "source": "fl_studio"})
