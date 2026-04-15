"""Tools: fl_panic, fl_mute_channel, fl_solo_channel."""

import mido
from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import ErrorCode, FLMCPError
from ..models import MuteChannelInput, PanicInput, SoloChannelInput
from ..protocol import encode_mute_channel, encode_solo_channel, panic_messages


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
