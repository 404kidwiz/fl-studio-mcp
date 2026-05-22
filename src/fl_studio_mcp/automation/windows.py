import os
import tempfile
import subprocess
import logging
from fl_studio_mcp.automation.base import GUIAutomation

logger = logging.getLogger(__name__)


class WindowsAutomation(GUIAutomation):
    """Windows implementation of FL Studio GUI/keystroke automation using VBScript."""

    def _run_vbscript(self, script_content: str) -> bool:
        temp_file = None
        try:
            # Create a temporary VBScript file
            fd, temp_file = tempfile.mkstemp(suffix=".vbs", text=True)
            with os.fdopen(fd, "w") as f:
                f.write(script_content)

            # Run with cscript, imposing a safety timeout of 5 seconds to avoid hangs
            res = subprocess.run(
                ["cscript", "//nologo", temp_file],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=5.0,
                check=False,
            )
            # If the script output contains '1', consider it successful
            if res.returncode != 0:
                logger.error(
                    f"VBScript failed with code {res.returncode}. stderr: {res.stderr.strip()}"
                )
            elif "1" not in (res.stdout or "").strip():
                logger.debug(
                    f"VBScript did not output success code. stdout: {res.stdout.strip()}"
                )

            return res.returncode == 0 and "1" in (res.stdout or "").strip()
        except subprocess.TimeoutExpired:
            logger.warning("VBScript execution timed out")
            # Handle subprocess hang gracefully
            return False
        except Exception:
            logger.exception("Failed to execute VBScript")
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
            "Dim success\n"
            'success = WshShell.AppActivate("FL Studio")\n'
            "If success Then\n"
            '    WScript.StdOut.Write "1"\n'
            "Else\n"
            '    WScript.StdOut.Write "0"\n'
            "End If\n"
        )
        return self._run_vbscript(script)

    def load_plugin(self, name: str) -> bool:
        # First perform basic sanitization
        clean_name = self._sanitize_string(name)
        # Escape for VBScript string literal and SendKeys special chars
        safe_name = clean_name.replace('"', '""')
        for char in ["+", "^", "%", "~", "(", ")", "[", "]", "{", "}"]:
            safe_name = safe_name.replace(char, f"{{{char}}}")

        script = (
            'Set WshShell = WScript.CreateObject("WScript.Shell")\n'
            "Dim success\n"
            'success = WshShell.AppActivate("FL Studio")\n'
            "If success Then\n"
            "    WScript.Sleep 200\n"
            '    WshShell.SendKeys "{F8}"\n'  # Open Plugin Picker
            "    WScript.Sleep 200\n"
            f'    WshShell.SendKeys "{safe_name}"\n'  # Type plugin name
            "    WScript.Sleep 200\n"
            '    WshShell.SendKeys "{ENTER}"\n'  # Hit Enter
            '    WScript.StdOut.Write "1"\n'
            "Else\n"
            '    WScript.StdOut.Write "0"\n'
            "End If\n"
        )
        return self._with_retry(self._run_vbscript, script)


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
                    text=True,
                    check=False,
                )
                if res.returncode != 0:
                    logger.error(
                        f"Failed to open file on Windows: {res.stderr.strip()}"
                    )
                return res.returncode == 0
        except Exception:
            logger.exception("Exception while opening file on Windows")
            return False

    def click_at(
        self, x: int, y: int, delay_ms: int = 100, relative: bool = True
    ) -> bool:
        if not self.focus_fl_studio():
            return False

        # Use PowerShell to find FL Studio window position (TFruityLoopsInstance),
        # apply DPI scaling factor, and perform the click using relative coordinates.
        relative_val = "$true" if relative else "$false"
        ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms;
Add-Type -AssemblyName System.Drawing;
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class Win32 {{
    [DllImport("user32.dll")]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")]
    public static extern void mouse_event(int flags, int dx, int dy, int cButtons, int dwExtraInfo);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {{
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }}
}}
"@;
$hWnd = [Win32]::FindWindow("TFruityLoopsInstance", $null);
if ($hWnd -eq [IntPtr]::Zero) {{
    $proc = Get-Process -Name "FL Studio*" -ErrorAction SilentlyContinue | Select-Object -First 1;
    if ($proc) {{ $hWnd = $proc.MainWindowHandle; }}
}}
if ($hWnd -eq [IntPtr]::Zero) {{
    $hWnd = [Win32]::FindWindow($null, "FL Studio");
}}
$graphics = [System.Drawing.Graphics]::FromHwnd([IntPtr]::Zero);
$scale = $graphics.DpiX / 96.0;
$graphics.Dispose();
$left = 0; $top = 0;
if ($hWnd -ne [IntPtr]::Zero) {{
    $rect = New-Object Win32+RECT;
    if ([Win32]::GetWindowRect($hWnd, [ref]$rect)) {{
        $left = $rect.Left;
        $top = $rect.Top;
    }}
}}
if ({relative_val}) {{
    $click_x = $left + [int]({x} * $scale);
    $click_y = $top + [int]({y} * $scale);
}} else {{
    $click_x = {x};
    $click_y = {y};
}}
[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($click_x, $click_y);
Start-Sleep -Milliseconds {delay_ms};
[Win32]::mouse_event(0x02, 0, 0, 0, 0);
[Win32]::mouse_event(0x04, 0, 0, 0, 0);
"""
        try:
            res = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    ps_script,
                ],
                capture_output=True,
                text=True,
                timeout=5.0,
                check=False,
            )
            if res.returncode != 0:
                logger.error(
                    f"PowerShell click_at failed. stderr: {res.stderr.strip()}"
                )
            return res.returncode == 0
        except subprocess.TimeoutExpired:
            logger.warning("PowerShell click_at timed out")
            return False
        except Exception:
            logger.exception("Exception in PowerShell click_at")
            return False

    def reset_ui(self, layout: str = "default") -> bool:
        script = (
            'Set WshShell = WScript.CreateObject("WScript.Shell")\n'
            "Dim success\n"
            'success = WshShell.AppActivate("FL Studio")\n'
            "If success Then\n"
            "    WScript.Sleep 200\n"
            '    WshShell.SendKeys "^+H"\n'  # Send Ctrl+Shift+H
            '    WScript.StdOut.Write "1"\n'
            "Else\n"
            '    WScript.StdOut.Write "0"\n'
            "End If\n"
        )
        return self._run_vbscript(script)

    def dismiss_popup(self, action: str = "confirm") -> bool:
        key = "{ENTER}" if action == "confirm" else "{ESC}"
        script = (
            'Set WshShell = WScript.CreateObject("WScript.Shell")\n'
            "Dim success\n"
            'success = WshShell.AppActivate("FL Studio")\n'
            "If success Then\n"
            "    WScript.Sleep 200\n"
            f'    WshShell.SendKeys "{key}"\n'
            '    WScript.StdOut.Write "1"\n'
            "Else\n"
            '    WScript.StdOut.Write "0"\n'
            "End If\n"
        )
        return self._run_vbscript(script)
