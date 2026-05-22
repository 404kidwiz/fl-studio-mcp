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

    def _run_applescript_with_output(self, script: str) -> tuple[bool, str]:
        try:
            res = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                check=False
            )
            return res.returncode == 0, res.stdout.strip()
        except Exception as e:
            return False, str(e)

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

    def click_at(self, x: int, y: int, delay_ms: int = 100, relative: bool = True) -> bool:
        if not self.focus_fl_studio():
            return False
        
        click_x, click_y = x, y
        if relative:
            pos_script = (
                'tell application "System Events"\n'
                '    tell process "FL Studio"\n'
                '        try\n'
                '            set win to window 1\n'
                '            set {winX, winY} to position of win\n'
                '            return "" & winX & "," & winY\n'
                '        on error\n'
                '            return "0,0"\n'
                '        end try\n'
                '    end tell\n'
                'end tell'
            )
            success, output = self._run_applescript_with_output(pos_script)
            if success and output and "," in output:
                try:
                    parts = output.split(",")
                    if len(parts) == 2:
                        win_x, win_y = int(parts[0].strip()), int(parts[1].strip())
                        click_x = win_x + x
                        click_y = win_y + y
                except Exception:
                    pass

        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
        script = (
            'tell application "System Events"\n'
            f'    click at {{{click_x}, {click_y}}}\n'
            'end tell'
        )
        return self._run_applescript(script)

    def reset_ui(self, layout: str = "default") -> bool:
        if not self.focus_fl_studio():
            return False
        script = (
            'tell application "System Events"\n'
            '    key code 4 using {shift down, command down}\n'
            'end tell'
        )
        return self._run_applescript(script)

    def dismiss_popup(self, action: str = "confirm") -> bool:
        if not self.focus_fl_studio():
            return False
        code = 36 if action == "confirm" else 53
        script = (
            'tell application "System Events"\n'
            f'    key code {code}\n'
            'end tell'
        )
        return self._run_applescript(script)

