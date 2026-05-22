from mcp.server.fastmcp import FastMCP
from ..bridge import format_result, send_command_sync
from ..automation import get_automation
from ..protocol import encode_show_window
import asyncio


async def _with_retry(
    func, *args, max_retries: int = 2, delay_ms: int = 200, **kwargs
) -> bool:
    """Helper to retry inherently flaky GUI automation calls."""
    for attempt in range(max_retries + 1):
        if func(*args, **kwargs):
            return True
        if attempt < max_retries:
            await asyncio.sleep(delay_ms / 1000.0)
    return False


def register(mcp: FastMCP) -> None:
    """Register GUI automation tools with FastMCP."""

    @mcp.tool(
        name="fl_click_at",
        annotations={
            "title": "Click at Coordinates",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def fl_click_at(
        x: int, y: int, delay_ms: int = 100, relative: bool = True
    ) -> str:
        """Simulate a mouse click at specific coordinates to control custom VST elements or preset selectors.

        Args:
            x: X-coordinate in pixels.
            y: Y-coordinate in pixels.
            delay_ms: Milliseconds delay after focusing but before clicking.
            relative: If True, coordinates are relative to the active FL Studio window (default: True).

        Returns:
            str: JSON indicating success or failure.
        """
        automation = get_automation()
        success = await _with_retry(automation.click_at, x, y, delay_ms, relative)
        return format_result(
            {
                "success": success,
                "action": "click_at",
                "coordinates": {"x": x, "y": y},
                "delay_ms": delay_ms,
                "relative": relative,
            }
        )

    @mcp.tool(
        name="fl_reset_ui",
        annotations={
            "title": "Reset UI Layout",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def fl_reset_ui(layout: str = "default") -> str:
        """Reset/arrange the FL Studio windows to a standardized/default layout (e.g. Shift+Ctrl+H).

        Args:
            layout: Layout name (currently "default").

        Returns:
            str: JSON indicating success or failure.
        """
        automation = get_automation()
        success = await _with_retry(automation.reset_ui, layout)
        return format_result(
            {"success": success, "action": "reset_ui", "layout": layout}
        )

    @mcp.tool(
        name="fl_dismiss_popup",
        annotations={
            "title": "Dismiss Popup Dialog",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def fl_dismiss_popup(action: str = "confirm") -> str:
        """Dismiss an active pop-up or modal dialog window in FL Studio.

        Args:
            action: Either "confirm" (presses Enter) or "cancel" (presses Escape).

        Returns:
            str: JSON indicating success or failure.
        """
        automation = get_automation()
        success = await _with_retry(automation.dismiss_popup, action)
        return format_result(
            {"success": success, "action": "dismiss_popup", "action_type": action}
        )

    @mcp.tool(
        name="fl_show_window",
        annotations={
            "title": "Show FL Studio Window",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def fl_show_window(window: str, channel_index: int = 0) -> str:
        """Show a specific FL Studio internal window (Mixer, Channel Rack, Playlist, Piano Roll, Browser, or Plugin).

        Args:
            window: One of "mixer", "channel_rack", "playlist", "piano_roll", "browser", "plugin".
            channel_index: Used only if window="plugin", specifies which channel's plugin to show.

        Returns:
            str: JSON indicating success or failure.
        """
        mapping = {
            "mixer": 0,
            "channel_rack": 1,
            "playlist": 2,
            "piano_roll": 3,
            "browser": 4,
            "plugin": 5
        }
        window_id = mapping.get(window.lower())
        if window_id is None:
            return format_result({"error": f"Unknown window type '{window}'. Valid types: {list(mapping.keys())}"})
            
        try:
            # We don't use encode_show_window since send_command_sync abstracts the payload manually for now, 
            # wait, I can just use send_command_sync with the raw cmd from protocol.
            # Let's import CMD_SHOW_WINDOW and use it
            from ..protocol import CMD_SHOW_WINDOW
            payload = [window_id]
            if window_id == 5:
                payload.append(channel_index & 0x7F)
            
            success = send_command_sync(CMD_SHOW_WINDOW, payload)
            return format_result({"success": success, "action": "show_window", "window": window})
        except Exception as exc:
            return format_result({"error": str(exc)})

    @mcp.tool(
        name="fl_browser_nav",
        annotations={
            "title": "FL Browser Navigation",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    def fl_browser_nav(action: str) -> str:
        """Navigate the FL Studio Browser programmatically.

        Args:
            action: The navigation action. Must be one of "up", "down", "left", "right", or "enter".

        Returns:
            str: JSON indicating success or failure.
        """
        mapping = {
            "up": 0,
            "down": 1,
            "left": 2,
            "right": 3,
            "enter": 4
        }
        action_id = mapping.get(action.lower())
        if action_id is None:
            return format_result({"error": f"Unknown action '{action}'. Valid actions: {list(mapping.keys())}"})
            
        try:
            from ..protocol import CMD_BROWSER_NAV
            from ..bridge import send_command_sync
            
            payload = [action_id]
            success = send_command_sync(CMD_BROWSER_NAV, payload)
            return format_result({"success": success, "action": "browser_nav", "nav_action": action})
        except Exception as exc:
            return format_result({"error": str(exc)})
