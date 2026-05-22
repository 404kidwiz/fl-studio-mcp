"""Tools: play_transport, stop_transport — MMC transport control."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import FLMCPError
from ..models import PlayStopInput, SetTimeSelectionInput
from ..protocol import mmc_play, mmc_stop, encode_set_time_selection


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


    @mcp.tool(
        name="fl_set_time_selection",
        annotations={
            "title": "Set Time Selection",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_set_time_selection(params: SetTimeSelectionInput) -> str:
        """Set the loop / time selection in the FL Studio arrangement.
        
        Args:
            params (SetTimeSelectionInput):
                - start_bar (int): Start bar of the loop (1-based generally, but test 0-based in FL API).
                - end_bar (int): End bar of the loop.
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_set_time_selection(params.start_bar, params.end_bar)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict())
            
        result["start_bar"] = params.start_bar
        result["end_bar"] = params.end_bar
        return format_result(result)
