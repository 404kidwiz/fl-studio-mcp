import sys
from fl_studio_mcp.automation.base import GUIAutomation
from fl_studio_mcp.automation.macos import MacOSAutomation
from fl_studio_mcp.automation.windows import WindowsAutomation

class FallbackAutomation(GUIAutomation):
    """Fallback GUI automation for unsupported platforms."""
    def focus_fl_studio(self) -> bool:
        return False
    def load_plugin(self, name: str) -> bool:
        return False
    def open_file(self, filepath: str) -> bool:
        return False
    def click_at(self, x: int, y: int, delay_ms: int = 100) -> bool:
        return False
    def reset_ui(self, layout: str = "default") -> bool:
        return False
    def dismiss_popup(self, action: str = "confirm") -> bool:
        return False

def get_automation() -> GUIAutomation:
    """Get the platform-specific GUIAutomation implementation.

    Returns:
        GUIAutomation instance.
    """
    if sys.platform == "darwin":
        return MacOSAutomation()
    elif sys.platform == "win32":
        return WindowsAutomation()
    else:
        return FallbackAutomation()
