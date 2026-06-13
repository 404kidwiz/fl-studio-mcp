"""Tools: fl_panic, fl_mute_channel, fl_solo_channel, fl_set_mixer_volume, fl_set_mixer_pan, fl_route_to_mixer, fl_get_mixer_state."""

import logging

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
    GetTrackPeaksInput,
    AutoMixInput,
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

logger = logging.getLogger(__name__)

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
            return format_result(
                {
                    "dry_run": True,
                    "messages_sent": len(msgs),
                    "channels_cleared": 16,
                    "note": "Would send All Notes Off + All Sound Off + Reset All Controllers × 16 channels",
                }
            )

        try:
            for raw in msgs:
                bridge.send_raw(raw)
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        return format_result(
            {
                "sent": True,
                "messages_sent": len(msgs),
                "channels_cleared": 16,
            }
        )

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
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

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
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

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
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

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
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

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
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

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
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        if bridge.dry_run:
            return format_result(
                {
                    "dry_run": True,
                    "start_track": params.start_track,
                    "end_track": params.end_track,
                    "tracks": [
                        {
                            "volume": 100,
                            "pan": 64,
                            "name": "Master" if i == 0 else f"Insert {i}",
                        }
                        for i in range(params.start_track, params.end_track + 1)
                    ],
                    "source": "dry_run_preview",
                }
            )

        if response is None and not bridge.listening:
            return format_result(
                {
                    "error": ErrorCode.NOT_CONNECTED.value,
                    "message": "No MIDI input listener active.",
                    "hint": _NO_LISTENER_HINT,
                }
            )

        if response is None:
            return format_result(
                {
                    "error": "TIMEOUT",
                    "message": "FL Studio did not respond.",
                    "hint": _TIMEOUT_HINT,
                    "timeout_ms": params.timeout_ms,
                }
            )

        try:
            state = decode_resp_mixer_state(response["payload"])
        except ValueError as exc:
            return format_result(
                FLMCPError(
                    ErrorCode.UNKNOWN, f"Bad mixer state response: {exc}"
                ).to_dict()
            )

        state["source"] = "fl_studio"
        return format_result(state)

    @mcp.tool(
        name="fl_get_track_peaks",
        annotations={
            "title": "Get Mixer Track Peaks",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_get_track_peaks(params: GetTrackPeaksInput) -> str:
        """Get the current Left and Right audio peak levels for a mixer track.

        Args:
            params (GetTrackPeaksInput):
                - track_index (int): The mixer track index (0=Master, 1-125=Inserts).

        Returns:
            str: JSON with 'l_peak' and 'r_peak' as floats (0.0 to 1.0).
        """
        try:
            from ..protocol import decode_resp_peaks, encode_get_peaks, RESP_PEAKS
        except ImportError:
            return format_result({"error": "Protocol extensions not found"})
        
        bridge = FLStudioBridge.get()
        try:
            sysex = encode_get_peaks(params.track_index)
            response = await bridge.query(sysex, RESP_PEAKS, timeout_ms=2000)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
            
        if bridge.dry_run:
            return format_result({"dry_run": True, "l_peak": 0.5, "r_peak": 0.5})

        if response is None:
            return format_result({"error": "TIMEOUT", "message": "No response from FL Studio."})

        try:
            l_peak, r_peak = decode_resp_peaks(response["payload"])
            return format_result({
                "track_index": params.track_index,
                "l_peak": l_peak,
                "r_peak": r_peak
            })
        except Exception as exc:
            return format_result({"error": str(exc)})

    @mcp.tool(
        name="fl_auto_mix",
        annotations={
            "title": "Dynamic Mixer Assistant",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_auto_mix(params: AutoMixInput) -> str:
        """Perform automated gain staging/level balancing on selected mixer tracks.

        Queries the peak level of each specified track using fl_get_track_peaks,
        converts the linear amplitude to decibels (dB), calculates required fader
        adjustment to reach the target dB level (incorporating headroom), and
        sends corrective MIDI volume commands to FL Studio.

        Excellent for dynamic studio mixing sessions to establish initial gain structure.

        Args:
            params (AutoMixInput):
                - tracks (list[int]): Mixer tracks to balance (e.g. [1, 2, 3]).
                - target_db (float): Target peak level in dB (default -12.0).
                - headroom_db (float): Scaled headroom margin (default -3.0).

        Returns:
            str: JSON log showing initial levels, dB differences, fader calculations, and actions taken.
        """
        import math
        from ..protocol import decode_resp_peaks, encode_get_peaks, RESP_PEAKS

        bridge = FLStudioBridge.get()
        results = []
        overall_success = True

        effective_target = params.target_db + params.headroom_db

        for track in params.tracks:
            # Step 1: Read peaks
            l_peak, r_peak = 0.0, 0.0
            peak_success = False
            
            if bridge.dry_run:
                import random
                base_peak = 0.7 if track in [1, 2, 3] else 0.4
                l_peak = base_peak + random.uniform(-0.15, 0.15)
                r_peak = base_peak + random.uniform(-0.15, 0.15)
                peak_success = True
            else:
                try:
                    sysex = encode_get_peaks(track)
                    response = await bridge.query(sysex, RESP_PEAKS, timeout_ms=1000)
                    if response is not None:
                        l_peak, r_peak = decode_resp_peaks(response["payload"])
                        peak_success = True
                except Exception as e:
                    logger.warning(f"Could not read peak for track {track}: {e}")

            if not peak_success:
                results.append({
                    "track_index": track,
                    "success": False,
                    "error": "Could not retrieve peak level metering from FL Studio."
                })
                continue

            max_peak = max(l_peak, r_peak)
            
            # Step 2: Convert linear peak to dB
            if max_peak > 0.0001:
                current_db = 20 * math.log10(max_peak)
            else:
                current_db = -96.0

            # Step 3: Calculate gain delta
            gain_delta_db = effective_target - current_db

            # Read current fader volume or default to 100.
            current_vol = 100
            if not bridge.dry_run:
                try:
                    state_sysex = encode_query_mixer_state(track, track)
                    resp = await bridge.query(state_sysex, RESP_MIXER_STATE, timeout_ms=500)
                    if resp:
                        state_data = decode_resp_mixer_state(resp["payload"])
                        if state_data and "tracks" in state_data and len(state_data["tracks"]) > 0:
                            current_vol = state_data["tracks"][0].get("volume", 100)
                except Exception:
                    pass

            db_per_step = 0.25
            vol_delta = int(round(gain_delta_db / db_per_step))
            target_vol = max(0, min(127, current_vol + vol_delta))

            # Step 4: Apply volume fader change in FL Studio
            volume_sent = False
            try:
                vol_sysex = encode_set_mixer_vol(track, target_vol)
                bridge.send_raw(vol_sysex)
                volume_sent = True
            except Exception as e:
                logger.error(f"Failed to set volume for track {track}: {e}")
                overall_success = False

            results.append({
                "track_index": track,
                "success": volume_sent,
                "input_peaks": {"L": round(l_peak, 3), "R": round(r_peak, 3)},
                "current_peak_db": round(current_db, 2),
                "target_peak_db": round(effective_target, 2),
                "gain_adjustment_db": round(gain_delta_db, 2),
                "previous_fader_vol": current_vol,
                "new_fader_vol": target_vol,
            })

        return format_result({
            "success": overall_success,
            "tracks_processed": results,
            "target_db": params.target_db,
            "headroom_db": params.headroom_db,
            "effective_target_db": effective_target,
        })
