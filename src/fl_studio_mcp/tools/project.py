"""Tool: fl_save_project — trigger a project save inside FL Studio."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import FLMCPError
from ..models import SaveProjectInput, UndoInput, RedoInput
from ..protocol import encode_save, encode_undo, encode_redo


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="fl_save_project",
        annotations={
            "title": "Save Project",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_save_project(params: SaveProjectInput) -> str:
        """Save the current project in FL Studio (Ctrl+S equivalent).

        Sends CMD_SAVE (F0 7D 05 F7) to the FL MCP Bridge controller script,
        which calls ui.save() in FL Studio.

        Important: FL Studio's ui.save() saves to the current project filename.
        If the project has never been saved, FL Studio will show its native
        Save dialog and the user must choose a filename manually.

        No filename can be set programmatically from a MIDI controller script.

        Requires fl_connect to have been called first.
        Requires the FL MCP Bridge controller script to be loaded in FL Studio.

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - command (str): "SAVE"
                - bytes (str): hex of the SysEx message
        """
        bridge = FLStudioBridge.get()
        try:
            result = bridge.send_raw(encode_save())
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        result["command"] = "SAVE"
        return format_result(result)

    @mcp.tool(
        name="fl_undo",
        annotations={
            "title": "Undo Action",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_undo(params: UndoInput) -> str:
        """Step backward in FL Studio's history stack (Undo).

        Sends CMD_UNDO (0x1D) to the FL MCP Bridge controller script,
        which calls general.undoUp() in FL Studio.

        Optional ACK support is available to block and verify execution.

        Args:
            params (UndoInput):
                - ack (bool): Whether to wait for ACK from FL Studio. Defaults to False.
                - timeout_ms (int): How long to wait for ACK in ms. Defaults to 200.

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - command (str): "UNDO"
                - bytes (str): hex of the SysEx message
                - ack_received (bool, optional)
        """
        from ..protocol import CMD_UNDO
        bridge = FLStudioBridge.get()
        try:
            result = await bridge.send_write(
                encode_undo(),
                cmd_byte=CMD_UNDO,
                ack=params.ack,
                timeout_ms=params.timeout_ms,
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        result["command"] = "UNDO"
        return format_result(result)

    @mcp.tool(
        name="fl_redo",
        annotations={
            "title": "Redo Action",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_redo(params: RedoInput) -> str:
        """Step forward in FL Studio's history stack (Redo).

        Sends CMD_REDO (0x1E) to the FL MCP Bridge controller script,
        which calls general.undoDown() in FL Studio.

        Optional ACK support is available to block and verify execution.

        Args:
            params (RedoInput):
                - ack (bool): Whether to wait for ACK from FL Studio. Defaults to False.
                - timeout_ms (int): How long to wait for ACK in ms. Defaults to 200.

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - command (str): "REDO"
                - bytes (str): hex of the SysEx message
                - ack_received (bool, optional)
        """
        from ..protocol import CMD_REDO
        bridge = FLStudioBridge.get()
        try:
            result = await bridge.send_write(
                encode_redo(),
                cmd_byte=CMD_REDO,
                ack=params.ack,
                timeout_ms=params.timeout_ms,
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        result["command"] = "REDO"
        return format_result(result)
