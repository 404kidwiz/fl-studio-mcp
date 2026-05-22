from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import ErrorCode, FLMCPError
from ..models import UiNavigateInput
from ..protocol import encode_ui_navigate

def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="fl_ui_navigate",
        annotations={
            "title": "FL Studio UI Navigator",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_ui_navigate(params: UiNavigateInput) -> str:
        """Simulate UI navigation and focus actions within FL Studio.
        
        This tool executes blind keystrokes or focus commands. Valid actions:
        - 'up', 'down', 'left', 'right'
        - 'enter', 'escape'
        - 'focus_browser', 'focus_channel_rack', 'focus_mixer', 'focus_playlist'
        
        Args:
            params (UiNavigateInput): Action to perform.
        """
        action_map = {
            "up": 0,
            "down": 1,
            "left": 2,
            "right": 3,
            "enter": 4,
            "escape": 5,
            "focus_browser": 6,
            "focus_channel_rack": 7,
            "focus_mixer": 8,
            "focus_playlist": 9
        }
        
        action_id = action_map.get(params.action.lower())
        if action_id is None:
            return format_result(
                FLMCPError(
                    ErrorCode.INVALID_PARAMS, 
                    f"Invalid action '{params.action}'. Must be one of: {list(action_map.keys())}"
                ).to_dict()
            )

        bridge = FLStudioBridge.get()
        try:
            sysex = encode_ui_navigate(action_id)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict())
            
        result["action"] = params.action
        return format_result(result)
