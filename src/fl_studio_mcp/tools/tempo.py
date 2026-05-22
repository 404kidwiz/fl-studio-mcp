"""Tool: set_tempo — send a BPM change to FL Studio via custom SysEx."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import FLMCPError
from ..models import SetTempoInput
from ..protocol import encode_tempo


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="fl_set_tempo",
        annotations={
            "title": "Set Tempo",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_set_tempo(params: SetTempoInput) -> str:
        """Set FL Studio's project tempo (BPM).

        Sends a custom SysEx message (F0 7D 03 HI LO F7) to the bridge script,
        which calls transport.setTempo(bpm) in FL Studio's Python API.

        Requires fl_connect to have been called first.
        Requires the FL MCP Bridge controller script to be loaded in FL Studio.

        Args:
            params (SetTempoInput):
                - bpm (int): Target BPM, 20–999.

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - bpm (int): the value sent
                - bytes (str): hex of SysEx message
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_tempo(params.bpm)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            from ..errors import ErrorCode

            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["bpm"] = params.bpm
        return format_result(result)
