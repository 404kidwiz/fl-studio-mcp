import subprocess
import time
from fl_studio_mcp.automation.base import GUIAutomation

class MacOSAutomation(GUIAutomation):
    """macOS implementation of FL Studio GUI/keystroke automation using AppleScript."""

    def _run_applescript(self, script: str) -> bool:
        try:
            res = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                check=False
            )
            return res.returncode == 0
        except Exception:
            return False

    def focus_fl_studio(self) -> bool:
        script = 'tell application "FL Studio" to activate'
        # Fallback query to find running FL Studio versions like "FL Studio 21" or "FL Studio 24"
        success = self._run_applescript(script)
        if not success:
            fallback = (
                'tell application "System Events"\n'
                '    set flList to every process whose name contains "FL Studio"\n'
                '    if (count of flList) > 0 then\n'
                '        set frontmost of (item 1 of flList) to true\n'
                '        return true\n'
                '    end if\n'
                '    return false\n'
                'end tell'
            )
            success = self._run_applescript(fallback)
        return success

    def load_plugin(self, name: str) -> bool:
        if not self.focus_fl_studio():
            return False
        
        # Keystroke script:
        # 1. Bring FL Studio to focus
        # 2. Press F8 (key code 100) to open Plugin Picker
        # 3. Delay to let UI render
        # 4. Keystroke the plugin name
        # 5. Delay to let search complete
        # 6. Press Return (key code 36) to load it
        script = (
            'tell application "FL Studio" to activate\n'
            'delay 0.2\n'
            'tell application "System Events"\n'
            '    key code 100\n' # F8
            '    delay 0.3\n'
            f'    keystroke "{name}"\n'
            '    delay 0.3\n'
            '    key code 36\n' # Enter
            'end tell'
        )
        return self._run_applescript(script)

    def open_file(self, filepath: str) -> bool:
        try:
            # Open file specifically with FL Studio
            res = subprocess.run(
                ["open", "-a", "FL Studio", filepath],
                capture_output=True,
                check=False
            )
            if res.returncode != 0:
                # Fallback to system default open handler
                res = subprocess.run(
                    ["open", filepath],
                    capture_output=True,
                    check=False
                )
            return res.returncode == 0
        except Exception:
            return False
