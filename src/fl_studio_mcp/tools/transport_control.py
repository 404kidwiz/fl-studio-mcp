"""Tools: play_transport, stop_transport — MMC transport control."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import FLMCPError
from ..models import PlayStopInput
from ..protocol import mmc_play, mmc_stop


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="fl_play_transport",
        annotations={
            "title": "Play Transport",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_play_transport(params: PlayStopInput) -> str:
        """Start FL Studio playback via MMC (MIDI Machine Control).

        Equivalent to pressing Play in FL Studio. FL Studio must have MIDI
        input enabled on the connected port and the controller script loaded.

        Requires fl_connect to have been called first.

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - bytes (str): hex representation of the MMC message sent
                - command (str): "MMC_PLAY"
        """
        bridge = FLStudioBridge.get()
        try:
            result = bridge.send_raw(mmc_play())
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        result["command"] = "MMC_PLAY"
        return format_result(result)

    @mcp.tool(
        name="fl_stop_transport",
        annotations={
            "title": "Stop Transport",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_stop_transport(params: PlayStopInput) -> str:
        """Stop FL Studio playback via MMC (MIDI Machine Control).

        Equivalent to pressing Stop in FL Studio.

        Requires fl_connect to have been called first.

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - bytes (str): hex representation of the MMC message sent
                - command (str): "MMC_STOP"
        """
        bridge = FLStudioBridge.get()
        try:
            result = bridge.send_raw(mmc_stop())
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        result["command"] = "MMC_STOP"
        return format_result(result)
