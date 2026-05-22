import os
import tempfile
import subprocess
from fl_studio_mcp.automation.base import GUIAutomation

class WindowsAutomation(GUIAutomation):
    """Windows implementation of FL Studio GUI/keystroke automation using VBScript."""

    def _run_vbscript(self, script_content: str) -> bool:
        temp_file = None
        try:
            # Create a temporary VBScript file
            fd, temp_file = tempfile.mkstemp(suffix=".vbs", text=True)
            with os.fdopen(fd, 'w') as f:
                f.write(script_content)

            # Run with cscript, imposing a safety timeout of 5 seconds to avoid hangs
            res = subprocess.run(
                ["cscript", "//nologo", temp_file],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=5.0,
                check=False
            )
            # If the script output contains '1', consider it successful
            return res.returncode == 0 and "1" in (res.stdout or "").strip()
        except subprocess.TimeoutExpired:
            # Handle subprocess hang gracefully
            return False
        except Exception:
            return False
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

    def focus_fl_studio(self) -> bool:
        # VBScript AppActivate matches partial titles too
        script = (
            'Set WshShell = WScript.CreateObject("WScript.Shell")\n'
            'Dim success\n'
            'success = WshShell.AppActivate("FL Studio")\n'
            'If success Then\n'
            '    WScript.StdOut.Write "1"\n'
            'Else\n'
            '    WScript.StdOut.Write "0"\n'
            'End If\n'
        )
        return self._run_vbscript(script)

    def load_plugin(self, name: str) -> bool:
        script = (
            'Set WshShell = WScript.CreateObject("WScript.Shell")\n'
            'Dim success\n'
            'success = WshShell.AppActivate("FL Studio")\n'
            'If success Then\n'
            '    WScript.Sleep 200\n'
            '    WshShell.SendKeys "{F8}"\n' # Open Plugin Picker
            '    WScript.Sleep 200\n'
            f'    WshShell.SendKeys "{name}"\n' # Type plugin name
            '    WScript.Sleep 200\n'
            '    WshShell.SendKeys "{ENTER}"\n' # Hit Enter
            '    WScript.StdOut.Write "1"\n'
            'Else\n'
            '    WScript.StdOut.Write "0"\n'
            'End If\n'
        )
        return self._run_vbscript(script)

    def open_file(self, filepath: str) -> bool:
        try:
            # os.startfile opens file with default registered application
            if hasattr(os, "startfile"):
                os.startfile(filepath)
                return True
            else:
                res = subprocess.run(
                    ["cmd", "/c", "start", filepath],
                    capture_output=True,
                    check=False
                )
                return res.returncode == 0
        except Exception:
            return False

    def click_at(self, x: int, y: int, delay_ms: int = 100) -> bool:
        if not self.focus_fl_studio():
            return False
        
        # Construct powershell script
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -AssemblyName System.Drawing; "
            "$signature = '[DllImport(\"user32.dll\")] public static extern void mouse_event(int flags, int dx, int dy, int cButtons, int dwExtraInfo);'; "
            "Add-Type -MemberDefinition $signature -Name Mouse -Namespace Win32; "
            f"[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({x}, {y}); "
            f"Start-Sleep -Milliseconds {delay_ms}; "
            "[Win32.Mouse]::mouse_event(0x02, 0, 0, 0, 0); " # MOUSEEVENTF_LEFTDOWN = 0x02
            "[Win32.Mouse]::mouse_event(0x04, 0, 0, 0, 0);"  # MOUSEEVENTF_LEFTUP = 0x04
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=5.0,
                check=False
            )
            return res.returncode == 0
        except Exception:
            return False

    def reset_ui(self, layout: str = "default") -> bool:
        script = (
            'Set WshShell = WScript.CreateObject("WScript.Shell")\n'
            'Dim success\n'
            'success = WshShell.AppActivate("FL Studio")\n'
            'If success Then\n'
            '    WScript.Sleep 200\n'
            '    WshShell.SendKeys "^+H"\n' # Send Ctrl+Shift+H
            '    WScript.StdOut.Write "1"\n'
            'Else\n'
            '    WScript.StdOut.Write "0"\n'
            'End If\n'
        )
        return self._run_vbscript(script)

    def dismiss_popup(self, action: str = "confirm") -> bool:
        key = "{ENTER}" if action == "confirm" else "{ESC}"
        script = (
            'Set WshShell = WScript.CreateObject("WScript.Shell")\n'
            'Dim success\n'
            'success = WshShell.AppActivate("FL Studio")\n'
            'If success Then\n'
            '    WScript.Sleep 200\n'
            f'    WshShell.SendKeys "{key}"\n'
            '    WScript.StdOut.Write "1"\n'
            'Else\n'
            '    WScript.StdOut.Write "0"\n'
            'End If\n'
        )
        return self._run_vbscript(script)

