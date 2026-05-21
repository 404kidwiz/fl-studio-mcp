"""Tools: fl_panic, fl_mute_channel, fl_solo_channel, fl_set_mixer_volume, fl_set_mixer_pan, fl_route_to_mixer, fl_get_mixer_state."""

import mido
from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import ErrorCode, FLMCPError
from ..models import (
    MuteChannelInput,
    PanicInput,
    SoloChannelInput,
    SetMixerVolumeInput,
    SetMixerPanInput,
    RouteToMixerInput,
    GetMixerStateInput,
)
from ..protocol import (
    encode_mute_channel,
    encode_solo_channel,
    panic_messages,
    encode_set_mixer_vol,
    encode_set_mixer_pan,
    encode_route_to_mixer,
    encode_query_mixer_state,
    decode_resp_mixer_state,
    RESP_MIXER_STATE,
)

_NO_LISTENER_HINT = (
    "No MIDI input port is listening. "
    "Reconnect with fl_connect — the input port is auto-detected from the same "
    "port name hint, or pass input_port_name explicitly."
)

_TIMEOUT_HINT = (
    "FL Studio did not respond within the timeout. "
    "Check that: (1) the FL MCP Bridge controller script is loaded in FL Studio's "
    "MIDI Settings, (2) the IAC Driver input is enabled in FL Studio, "
    "(3) FL Studio is open and not frozen."
)



def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="fl_panic",
        annotations={
            "title": "MIDI Panic (All Notes Off)",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_panic(params: PanicInput) -> str:
        """Send MIDI panic — immediately silence all stuck or hanging notes.

        Sends CC 123 (All Notes Off), CC 120 (All Sound Off), and CC 121
        (Reset All Controllers) on every MIDI channel (0-15).

        Unlike other tools, panic works WITHOUT the FL MCP Bridge controller
        script — it sends standard MIDI CC messages directly to the IAC port
        and FL Studio handles them natively.

        Use this any time notes get stuck, after a crash, or before starting
        a new recording session to ensure a clean slate.

        Requires fl_connect to have been called first.

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - messages_sent (int): total CC messages sent (48 = 3 × 16 ch)
                - channels_cleared (int): always 16
        """
        bridge = FLStudioBridge.get()
        msgs = panic_messages()

        if bridge.dry_run:
            bridge._require_connection()  # still check connected in dry-run
            return format_result({
                "dry_run": True,
                "messages_sent": len(msgs),
                "channels_cleared": 16,
                "note": "Would send All Notes Off + All Sound Off + Reset All Controllers × 16 channels",
            })

        try:
            for raw in msgs:
                bridge.send_raw(raw)
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        return format_result({
            "sent": True,
            "messages_sent": len(msgs),
            "channels_cleared": 16,
        })

    @mcp.tool(
        name="fl_mute_channel",
        annotations={
            "title": "Mute Channel",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_mute_channel(params: MuteChannelInput) -> str:
        """Mute or unmute a channel in FL Studio's channel rack.

        Sends CMD_MUTE_CHANNEL (F0 7D 0D ch_idx muted F7) to the bridge
        script, which calls channels.muteChannel(index, value).

        Use fl_list_channels to discover channel indices by name.
        Use fl_get_status to see current channel count.

        Requires fl_connect and the FL MCP Bridge script loaded.

        Args:
            params (MuteChannelInput):
                - channel_index (int 0-127): Channel rack slot (0-based).
                - muted (bool): True to mute, False to unmute. Default True.

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - channel_index (int)
                - muted (bool)
                - bytes (str): hex of SysEx sent
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_mute_channel(params.channel_index, params.muted)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict())

        result["channel_index"] = params.channel_index
        result["muted"] = params.muted
        return format_result(result)

    @mcp.tool(
        name="fl_solo_channel",
        annotations={
            "title": "Solo Channel",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_solo_channel(params: SoloChannelInput) -> str:
        """Solo or un-solo a channel in FL Studio's channel rack.

        Sends CMD_SOLO_CHANNEL (F0 7D 0E ch_idx soloed F7) to the bridge
        script, which calls channels.soloChannel(index).

        Note: In FL Studio, solo is a toggle per channel. Calling solo on an
        already-soloed channel will un-solo it. The soloed=False parameter
        sends the same command so FL can toggle accordingly.

        Requires fl_connect and the FL MCP Bridge script loaded.

        Args:
            params (SoloChannelInput):
                - channel_index (int 0-127): Channel rack slot (0-based).
                - soloed (bool): True to solo, False to un-solo. Default True.

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - channel_index (int)
                - soloed (bool)
                - bytes (str): hex of SysEx sent
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_solo_channel(params.channel_index, params.soloed)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict())

        result["channel_index"] = params.channel_index
        result["soloed"] = params.soloed
        return format_result(result)

    @mcp.tool(
        name="fl_set_mixer_volume",
        annotations={
            "title": "Set Mixer Volume",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_set_mixer_volume(params: SetMixerVolumeInput) -> str:
        """Set volume of a mixer track.

        Sends CMD_SET_MIXER_VOL (F0 7D 19 track_idx volume F7) to the bridge
        script, which calls mixer.setTrackVolume(track_idx, volume / 127.0).

        Args:
            params (SetMixerVolumeInput):
                - track_index (int 0-127): Mixer track index (0 is Master).
                - volume (int 0-127): Volume level (100 = unity gain).

        Returns:
            str: JSON description of result.
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_set_mixer_vol(params.track_index, params.volume)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict())

        result["track_index"] = params.track_index
        result["volume"] = params.volume
        return format_result(result)

    @mcp.tool(
        name="fl_set_mixer_pan",
        annotations={
            "title": "Set Mixer Pan",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_set_mixer_pan(params: SetMixerPanInput) -> str:
        """Set panning of a mixer track.

        Sends CMD_SET_MIXER_PAN (F0 7D 1A track_idx pan F7) to the bridge
        script, which calls mixer.setTrackPan(track_idx, (pan - 64) / 64.0).

        Args:
            params (SetMixerPanInput):
                - track_index (int 0-127): Mixer track index (0 is Master).
                - pan (int 0-127): Pan position (0=L, 64=C, 127=R).

        Returns:
            str: JSON description of result.
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_set_mixer_pan(params.track_index, params.pan)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict())

        result["track_index"] = params.track_index
        result["pan"] = params.pan
        return format_result(result)

    @mcp.tool(
        name="fl_route_to_mixer",
        annotations={
            "title": "Route Channel to Mixer",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_route_to_mixer(params: RouteToMixerInput) -> str:
        """Route a channel to a mixer track.

        Sends CMD_ROUTE_TO_MIXER (F0 7D 1B channel_idx track_idx F7) to the bridge
        script, which calls channels.setTargetTrack(channel_index, track_index).

        Args:
            params (RouteToMixerInput):
                - channel_index (int 0-127): Channel rack index.
                - track_index (int 0-127): Mixer track index.

        Returns:
            str: JSON description of result.
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_route_to_mixer(params.channel_index, params.track_index)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict())

        result["channel_index"] = params.channel_index
        result["track_index"] = params.track_index
        return format_result(result)

    @mcp.tool(
        name="fl_get_mixer_state",
        annotations={
            "title": "Get Mixer State",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_get_mixer_state(params: GetMixerStateInput) -> str:
        """Query state (volume, pan, name) of a range of mixer tracks.

        Sends CMD_QUERY_MIXER_STATE (F0 7D 1C start_track end_track F7) and waits
        for a RESP_MIXER_STATE reply.

        Args:
            params (GetMixerStateInput):
                - start_track (int 0-127): Start track (default 0).
                - end_track (int 0-127): End track (default 16, max range 32).
                - timeout_ms (int 100-10000): Response timeout.

        Returns:
            str: JSON containing track info or error.
        """
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_query_mixer_state(params.start_track, params.end_track)
            response = await bridge.query(sysex, RESP_MIXER_STATE, params.timeout_ms)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict())

        if bridge.dry_run:
            return format_result({
                "dry_run": True,
                "start_track": params.start_track,
                "end_track": params.end_track,
                "tracks": [
                    {
                        "volume": 100,
                        "pan": 64,
                        "name": "Master" if i == 0 else f"Insert {i}"
                    }
                    for i in range(params.start_track, params.end_track + 1)
                ],
                "source": "dry_run_preview",
            })

        if response is None and not bridge.listening:
            return format_result({
                "error": ErrorCode.NOT_CONNECTED.value,
                "message": "No MIDI input listener active.",
                "hint": _NO_LISTENER_HINT,
            })

        if response is None:
            return format_result({
                "error": "TIMEOUT",
                "message": "FL Studio did not respond.",
                "hint": _TIMEOUT_HINT,
                "timeout_ms": params.timeout_ms,
            })

        try:
            state = decode_resp_mixer_state(response["payload"])
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.UNKNOWN, f"Bad mixer state response: {exc}").to_dict()
            )

        state["source"] = "fl_studio"
        return format_result(state)

