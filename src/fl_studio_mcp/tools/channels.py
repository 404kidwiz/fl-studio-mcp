"""Tools: fl_list_channels, fl_set_channel_volume."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import ErrorCode, FLMCPError
from ..models import ListChannelsInput, SetChannelVolumeInput
from ..protocol import (
    RESP_CHANNELS,
    decode_resp_channels,
    encode_query_channels,
    encode_set_channel_vol,
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
        name="fl_list_channels",
        annotations={
            "title": "List FL Studio Channels",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_list_channels(params: ListChannelsInput) -> str:
        """List all channels (instruments) in FL Studio's channel rack.

        Sends CMD_QUERY_CHANNELS (F0 7D 07 F7) and waits for RESP_CHANNELS
        (F0 7D 11 ...) from the FL MCP Bridge controller script.

        Requires fl_connect (with listening) and the bridge script loaded.

        Args:
            params (ListChannelsInput):
                - timeout_ms (int): Wait timeout in ms. Default 2000.

        Returns:
            str: JSON with keys:
                - channels (list[str]): Channel names in rack order
                - count (int): Total number of channels
                - source (str): "fl_studio" | "dry_run_preview"

            On timeout / no listener: {"error": ..., "hint": ...}
        """
        bridge = FLStudioBridge.get()

        try:
            response = await bridge.query(encode_query_channels(), RESP_CHANNELS, params.timeout_ms)
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        if bridge.dry_run:
            mock = ["Kick", "Snare", "Hi-Hat", "Bass", "Synth Lead"]
            return format_result({"dry_run": True, "channels": mock, "count": len(mock), "source": "dry_run_preview"})

        if response is None and not bridge.listening:
            return format_result({"error": ErrorCode.NOT_CONNECTED.value, "hint": _NO_LISTENER_HINT})

        if response is None:
            return format_result({"error": "TIMEOUT", "hint": _TIMEOUT_HINT, "timeout_ms": params.timeout_ms})

        channels = decode_resp_channels(response["payload"])
        return format_result({"channels": channels, "count": len(channels), "source": "fl_studio"})

    @mcp.tool(
        name="fl_set_channel_volume",
        annotations={
            "title": "Set Channel Volume",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_set_channel_volume(params: SetChannelVolumeInput) -> str:
        """Set the volume of a channel rack slot in FL Studio.

        Sends CMD_SET_CHANNEL_VOL (F0 7D 08 ch_idx volume F7) to the bridge
        script, which calls channels.setChannelVolume(index, volume).

        Use fl_list_channels first to discover channel indices.

        Requires fl_connect to have been called first.

        Args:
            params (SetChannelVolumeInput):
                - channel_index (int 0-127): Channel rack slot (0-based).
                - volume (int 0-127): Volume level. 100 = unity gain (FL default).

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - channel_index (int)
                - volume (int)
                - bytes (str): hex of SysEx sent
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_set_channel_vol(params.channel_index, params.volume)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict())

        result["channel_index"] = params.channel_index
        result["volume"] = params.volume
        return format_result(result)
