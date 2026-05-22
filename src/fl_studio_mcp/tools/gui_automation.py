from mcp.server.fastmcp import FastMCP
from ..bridge import format_result
from ..automation import get_automation

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
    async def fl_click_at(x: int, y: int, delay_ms: int = 100, relative: bool = True) -> str:
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
        success = automation.click_at(x, y, delay_ms, relative)
        return format_result({
            "success": success,
            "action": "click_at",
            "coordinates": {"x": x, "y": y},
            "delay_ms": delay_ms,
            "relative": relative
        })

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
        success = automation.reset_ui(layout)
        return format_result({
            "success": success,
            "action": "reset_ui",
            "layout": layout
        })

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
        success = automation.dismiss_popup(action)
        return format_result({
            "success": success,
            "action": "dismiss_popup",
            "action_type": action
        })
