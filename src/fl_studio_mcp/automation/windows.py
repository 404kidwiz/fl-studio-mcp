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

            # Run with cscript
            res = subprocess.run(
                ["cscript", "//nologo", temp_file],
                capture_output=True,
                text=True,
                check=False
            )
            # If the script output contains '1', consider it successful
            return res.returncode == 0 and "1" in res.stdout
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
