from abc import ABC, abstractmethod

class GUIAutomation(ABC):
    """Abstract base class for cross-platform FL Studio GUI and keystroke automation."""

    @abstractmethod
    def focus_fl_studio(self) -> bool:
        """Bring FL Studio to the foreground.

        Returns:
            bool: True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def load_plugin(self, name: str) -> bool:
        """Focus FL Studio, open the Plugin Picker (F8), search for the plugin name,
        and press Enter to instantiate it.

        Args:
            name: The name of the VST/AU plugin to load.

        Returns:
            bool: True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def open_file(self, filepath: str) -> bool:
        """Open a preset (.fst) or project (.flp) file directly in FL Studio.

        Args:
            filepath: Absolute path to the file to open.

        Returns:
            bool: True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def click_at(self, x: int, y: int, delay_ms: int = 100) -> bool:
        """Move the mouse cursor to (x, y) and perform a left click.

        Args:
            x: X-coordinate in pixels from top-left.
            y: Y-coordinate in pixels from top-left.
            delay_ms: Delay in milliseconds after moving but before clicking.

        Returns:
            bool: True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def reset_ui(self, layout: str = "default") -> bool:
        """Reset the FL Studio window arrangement (e.g. Shift+Ctrl+H).

        Args:
            layout: Layout name (currently "default").

        Returns:
            bool: True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def dismiss_popup(self, action: str = "confirm") -> bool:
        """Dismiss an open FL Studio popup or dialog.

        Args:
            action: Either "confirm" (presses Enter) or "cancel" (presses Escape).

        Returns:
            bool: True if successful, False otherwise.
        """
        pass
