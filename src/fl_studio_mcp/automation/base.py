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
