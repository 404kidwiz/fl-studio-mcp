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
    def click_at(
        self, x: int, y: int, delay_ms: int = 100, relative: bool = True
    ) -> bool:
        """Move the mouse cursor to (x, y) and perform a left click.

        Args:
            x: X-coordinate in pixels.
            y: Y-coordinate in pixels.
            delay_ms: Delay in milliseconds after moving but before clicking.
            relative: If True, coordinates are relative to active FL Studio window.

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

    def _with_retry(self, func, *args, retries: int = 2, delay_ms: int = 200, **kwargs) -> bool:
        """Execute a function with retries and exponential backoff if it returns False or raises an exception."""
        import time
        import logging
        logger = logging.getLogger(__name__)
        
        current_delay = delay_ms / 1000.0
        for attempt in range(retries + 1):
            try:
                # Resolve method name if passed as string
                if isinstance(func, str):
                    target_func = getattr(self, func)
                else:
                    target_func = func
                
                if target_func(*args, **kwargs):
                    return True
            except Exception as exc:
                logger.warning(f"Attempt {attempt} of {func} failed with exception: {exc}")
            
            if attempt < retries:
                logger.info(f"Retrying {func} in {current_delay:.2f}s (attempt {attempt + 1}/{retries})...")
                time.sleep(current_delay)
                current_delay *= 2  # Exponential backoff
        return False

    def _sanitize_string(self, text: str) -> str:
        """Sanitize strings intended for OS automation to prevent injection or syntax breaking."""
        clean = text.replace("\r", "").replace("\n", "")
        # Strip potentially risky control characters
        for char in ['"', "'", "\\", "`", "$"]:
            clean = clean.replace(char, "")
        return clean


