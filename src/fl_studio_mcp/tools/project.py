"""Tool: fl_save_project — trigger a project save inside FL Studio."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import FLMCPError
from ..models import SaveProjectInput
from ..protocol import encode_save


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
