"""Tools: fl_list_channels, fl_set_channel_volume, fl_set_channel_pan."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import ErrorCode, FLMCPError
from ..models import (
    ListChannelsInput,
    SetChannelVolumeInput,
    SetChannelPanInput,
    SetGridBitInput,
    SetChannelColorInput,
    SetChannelNameInput,
    SetChannelMixerTrackInput,
)
from ..protocol import (
    RESP_CHANNELS,
    decode_resp_channels,
    encode_query_channels,
    encode_set_channel_pan,
    encode_set_channel_vol,
    encode_set_grid_bit,
    encode_set_channel_color,
    encode_set_channel_name,
    encode_set_channel_mixer_track,
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
            response = await bridge.query(
                encode_query_channels(), RESP_CHANNELS, params.timeout_ms
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        if bridge.dry_run:
            mock = ["Kick", "Snare", "Hi-Hat", "Bass", "Synth Lead"]
            return format_result(
                {
                    "dry_run": True,
                    "channels": mock,
                    "count": len(mock),
                    "source": "dry_run_preview",
                }
            )

        if response is None and not bridge.listening:
            return format_result(
                {"error": ErrorCode.NOT_CONNECTED.value, "hint": _NO_LISTENER_HINT}
            )

        if response is None:
            return format_result(
                {
                    "error": "TIMEOUT",
                    "hint": _TIMEOUT_HINT,
                    "timeout_ms": params.timeout_ms,
                }
            )

        channels = decode_resp_channels(response["payload"])
        return format_result(
            {"channels": channels, "count": len(channels), "source": "fl_studio"}
        )

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
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["channel_index"] = params.channel_index
        result["volume"] = params.volume
        return format_result(result)

    @mcp.tool(
        name="fl_set_channel_pan",
        annotations={
            "title": "Set Channel Pan",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_set_channel_pan(params: SetChannelPanInput) -> str:
        """Set the stereo panning of a channel rack slot in FL Studio.

        Sends CMD_SET_CHANNEL_PAN (F0 7D 13 ch_idx pan F7) to the bridge
        script, which calls channels.setChannelPan(index, normalised).

        Pan scale: 0 = full left, 64 = centre (default), 127 = full right.
        FL Studio maps this to -1.0 → 0.0 → +1.0 internally.

        Use fl_list_channels to discover channel indices by name.

        Requires fl_connect and the FL MCP Bridge script loaded.

        Args:
            params (SetChannelPanInput):
                - channel_index (int 0-127): Channel rack slot (0-based).
                - pan (int 0-127): Pan position. 64 = centre. Default 64.

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - channel_index (int)
                - pan (int)
                - bytes (str): hex of SysEx sent
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_set_channel_pan(params.channel_index, params.pan)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["channel_index"] = params.channel_index
        result["pan"] = params.pan
        return format_result(result)


    @mcp.tool(
        name="fl_set_step_sequence",
        annotations={
            "title": "Set Step Sequencer Grid Bit",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_set_step_sequence(params: SetGridBitInput) -> str:
        """Set a single step on or off in the classic FL Studio step sequencer.
        
        Requires FL Studio to be connected.
        
        Args:
            params (SetGridBitInput):
                - channel_index (int): Channel rack slot index.
                - step_index (int): Step number (0-based, e.g. 0-15 for 16-step grid).
                - value (int): 1 to enable, 0 to disable.
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_set_grid_bit(params.channel_index, params.step_index, params.value)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict())
            
        result["channel_index"] = params.channel_index
        result["step_index"] = params.step_index
        result["value"] = params.value
        return format_result(result)

    @mcp.tool(
        name="fl_set_channel_color",
        annotations={
            "title": "Set Channel Color",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_set_channel_color(params: SetChannelColorInput) -> str:
        """Set the display color of a channel in the channel rack.
        
        Args:
            params (SetChannelColorInput):
                - channel_index (int): Channel rack slot index.
                - r (int 0-255): Red component.
                - g (int 0-255): Green component.
                - b (int 0-255): Blue component.
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_set_channel_color(params.channel_index, params.r, params.g, params.b)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict())
            
        result["channel_index"] = params.channel_index
        result["color"] = [params.r, params.g, params.b]
        return format_result(result)


    @mcp.tool(
        name="fl_set_channel_name",
        annotations={
            "title": "Set Channel Name",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_set_channel_name(params: SetChannelNameInput) -> str:
        """Rename a channel in the channel rack.
        
        Args:
            params (SetChannelNameInput):
                - channel_index (int): Channel index.
                - name (str): The new name.
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_set_channel_name(params.channel_index, params.name)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict())
            
        result["channel_idx"] = params.channel_index
        result["name"] = params.name
        return format_result(result)


    @mcp.tool(
        name="fl_set_channel_mixer_track",
        annotations={
            "title": "Set Channel Mixer Track",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_set_channel_mixer_track(params: SetChannelMixerTrackInput) -> str:
        """Route a channel rack channel to a specific mixer insert track.
        
        Args:
            params (SetChannelMixerTrackInput):
                - channel_index (int): Channel index.
                - track_index (int): Mixer track number (0 = Master, 1-125 = Inserts).
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_set_channel_mixer_track(params.channel_index, params.track_index)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict())
            
        result["channel_idx"] = params.channel_index
        result["track_index"] = params.track_index
        return format_result(result)
