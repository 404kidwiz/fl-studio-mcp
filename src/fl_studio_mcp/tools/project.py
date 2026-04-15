"""Tool: save_project_as — trigger a project save inside FL Studio."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import FLMCPError
from ..models import SaveProjectAsInput
from ..protocol import encode_save_as


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="fl_save_project_as",
        annotations={
            "title": "Save Project As",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_save_project_as(params: SaveProjectAsInput) -> str:
        """Trigger a project save in FL Studio.

        Sends a CMD_SAVE_AS SysEx message (F0 7D 05 <filename bytes> F7) to
        the FL MCP Bridge controller script, which calls ui.save() in FL Studio.

        Note on filename: The filename is passed as metadata in the SysEx
        payload so FL Studio can use it for display/logging, but the actual
        save path is determined by FL Studio's current project path. For a
        true "save as new name", you can pre-name your project in FL Studio
        before calling this tool.

        Requires fl_connect to have been called first.
        Requires the FL MCP Bridge controller script to be loaded in FL Studio.

        Args:
            params (SaveProjectAsInput):
                - filename (str): Project filename (no extension, no path
                  separators). Allowed characters: letters, numbers, spaces,
                  dashes, underscores, dots. Max 255 chars.

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - filename (str): filename sent in the SysEx payload
                - bytes (str): hex of the SysEx message
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_save_as(params.filename)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            from ..errors import ErrorCode
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["filename"] = params.filename
        return format_result(result)
