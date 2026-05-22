from mcp.server.fastmcp import FastMCP
from ..protocol import (
    encode_set_plugin_param,
    encode_get_plugin_param,
    decode_resp_plugin_param,
    RESP_PLUGIN_PARAM,
)
from ..bridge import FLStudioBridge, send_command_sync, format_result
from ..errors import FLMCPError


def register(mcp: FastMCP) -> None:
    """Register plugin parameter automation tools with FastMCP."""

    @mcp.tool(
        name="fl_set_plugin_param",
        annotations={
            "title": "Set Plugin Parameter",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def fl_set_plugin_param(
        target_type: int, track_or_chan_idx: int, slot_idx: int, param_index: int, value: float
    ) -> str:
        """Set a parameter value for a plugin on a channel or mixer track.

        Args:
            target_type: 0 for Mixer Effect, 1 for Channel Generator.
            track_or_chan_idx: Mixer track index (if 0) or channel index (if 1).
            slot_idx: Mixer slot index (0-9). Ignored if target_type is 1.
            param_index: Index of the parameter to automate.
            value: Parameter value, from 0.0 to 1.0.

        Returns:
            str: JSON with success status.
        """
        try:
            cmd_bytes = encode_set_plugin_param(
                target_type, track_or_chan_idx, slot_idx, param_index, value
            )
            # cmd_bytes[2] is CMD_SET_PLUGIN_PARAM, but send_command_sync needs cmd and payload
            # Wait, send_command_sync signature: send_command_sync(cmd: int, payload: list[int])
            cmd = cmd_bytes[2]
            payload = list(cmd_bytes[3:-1])
            success = send_command_sync(cmd, payload)
            
            return format_result(
                {
                    "success": success,
                    "action": "set_plugin_param",
                    "target_type": target_type,
                    "index": track_or_chan_idx,
                    "slot": slot_idx,
                    "param": param_index,
                    "value": value,
                }
            )
        except Exception as exc:
            return format_result({"error": str(exc)})

    @mcp.tool(
        name="fl_get_plugin_param",
        annotations={
            "title": "Get Plugin Parameter",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_get_plugin_param(
        target_type: int, track_or_chan_idx: int, slot_idx: int, param_index: int
    ) -> str:
        """Get the current parameter value for a plugin.

        Args:
            target_type: 0 for Mixer Effect, 1 for Channel Generator.
            track_or_chan_idx: Mixer track index (if 0) or channel index (if 1).
            slot_idx: Mixer slot index (0-9). Ignored if target_type is 1.
            param_index: Index of the parameter to query.

        Returns:
            str: JSON containing the parameter value (0.0 to 1.0).
        """
        bridge = FLStudioBridge.get()
        if bridge.dry_run:
            return format_result({"value": 0.5, "dry_run": True})

        try:
            cmd_bytes = encode_get_plugin_param(
                target_type, track_or_chan_idx, slot_idx, param_index
            )
            response = await bridge.query(cmd_bytes, RESP_PLUGIN_PARAM, timeout_ms=2000)
            
            if response is None:
                return format_result({"error": "Timeout waiting for plugin parameter response."})
                
            value = decode_resp_plugin_param(response["payload"])
            return format_result(
                {
                    "action": "get_plugin_param",
                    "target_type": target_type,
                    "index": track_or_chan_idx,
                    "slot": slot_idx,
                    "param": param_index,
                    "value": value,
                }
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except Exception as exc:
            return format_result({"error": str(exc)})
