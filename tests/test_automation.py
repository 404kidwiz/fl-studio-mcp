import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from mcp.server.fastmcp import FastMCP

from fl_studio_mcp.automation import get_automation, FallbackAutomation
from fl_studio_mcp.automation.macos import MacOSAutomation
from fl_studio_mcp.automation.windows import WindowsAutomation
from fl_studio_mcp.tools.vst_scanner import (
    get_fl_user_data_path,
    scan_plugin_database,
    scan_system_plugins,
    register as register_vst
)
from fl_studio_mcp.tools.library import scan_user_library, register as register_library
from fl_studio_mcp.tools.gui_automation import register as register_gui

def test_automation_factory():
    """Test that the automation factory returns the correct class per platform."""
    with patch("sys.platform", "darwin"):
        auto = get_automation()
        assert isinstance(auto, MacOSAutomation)

    with patch("sys.platform", "win32"):
        auto = get_automation()
        assert isinstance(auto, WindowsAutomation)

    with patch("sys.platform", "linux"):
        auto = get_automation()
        assert isinstance(auto, FallbackAutomation)

def test_macos_automation_methods():
    """Test MacOSAutomation AppleScript generation and commands."""
    auto = MacOSAutomation()
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="success")
        
        # Test focus
        assert auto.focus_fl_studio() is True
        mock_run.assert_called_with(
            ["osascript", "-e", 'tell application "FL Studio" to activate'],
            capture_output=True,
            text=True,
            check=False
        )

        # Test load plugin
        assert auto.load_plugin("Serum") is True
        # Verify AppleScript contains Serum and the key codes
        args = mock_run.call_args[0][0]
        assert "osascript" in args
        assert "-e" in args
        script_arg = args[2]
        assert "Serum" in script_arg
        assert "key code 100" in script_arg # F8
        assert "key code 36" in script_arg # Enter

        # Test open file
        assert auto.open_file("/path/to/project.flp") is True
        mock_run.assert_called_with(
            ["open", "-a", "FL Studio", "/path/to/project.flp"],
            capture_output=True,
            check=False
        )

        # Test click_at
        assert auto.click_at(100, 200, delay_ms=0) is True
        args = mock_run.call_args[0][0]
        assert "click at {100, 200}" in args[2]

        # Test reset_ui
        assert auto.reset_ui() is True
        args = mock_run.call_args[0][0]
        assert "key code 4 using {shift down, command down}" in args[2]

        # Test dismiss_popup confirm
        assert auto.dismiss_popup("confirm") is True
        args = mock_run.call_args[0][0]
        assert "key code 36" in args[2]

        # Test dismiss_popup cancel
        assert auto.dismiss_popup("cancel") is True
        args = mock_run.call_args[0][0]
        assert "key code 53" in args[2]

def test_windows_automation_methods():
    """Test WindowsAutomation VBScript generation and cscript execution."""
    auto = WindowsAutomation()
    
    with patch("tempfile.mkstemp") as mock_mkstemp, \
         patch("os.fdopen") as mock_fdopen, \
         patch("subprocess.run") as mock_run, \
         patch("os.path.exists") as mock_exists, \
         patch("os.remove") as mock_remove:
         
        mock_mkstemp.return_value = (99, "temp.vbs")
        mock_file = MagicMock()
        mock_fdopen.return_value.__enter__.return_value = mock_file
        mock_run.return_value = MagicMock(returncode=0, stdout="1")
        mock_exists.return_value = True

        # Test focus
        assert auto.focus_fl_studio() is True
        mock_file.write.assert_called_once()
        assert "AppActivate(\"FL Studio\")" in mock_file.write.call_args[0][0]
        mock_run.assert_called_with(
            ["cscript", "//nologo", "temp.vbs"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=5.0,
            check=False
        )
        mock_remove.assert_called_with("temp.vbs")

        # Test load plugin
        mock_file.reset_mock()
        assert auto.load_plugin("Harmless") is True
        assert "SendKeys \"Harmless\"" in mock_file.write.call_args[0][0]
        assert "SendKeys \"{F8}\"" in mock_file.write.call_args[0][0]
        assert "SendKeys \"{ENTER}\"" in mock_file.write.call_args[0][0]

        # Test click_at
        mock_run.reset_mock()
        assert auto.click_at(150, 250, delay_ms=50) is True
        assert mock_run.call_args[0][0][0] == "powershell"
        ps_cmd = mock_run.call_args[0][0][5]
        assert "150" in ps_cmd
        assert "250" in ps_cmd
        assert "Start-Sleep -Milliseconds 50" in ps_cmd

        # Test reset_ui
        mock_file.reset_mock()
        assert auto.reset_ui() is True
        assert "SendKeys \"^+H\"" in mock_file.write.call_args[0][0]

        # Test dismiss_popup confirm
        mock_file.reset_mock()
        assert auto.dismiss_popup("confirm") is True
        assert "SendKeys \"{ENTER}\"" in mock_file.write.call_args[0][0]

        # Test dismiss_popup cancel
        mock_file.reset_mock()
        assert auto.dismiss_popup("cancel") is True
        assert "SendKeys \"{ESC}\"" in mock_file.write.call_args[0][0]

def test_windows_open_file():
    """Test WindowsAutomation open_file handles os.startfile or cmd shell fallback."""
    auto = WindowsAutomation()
    
    with patch("os.startfile", create=True) as mock_startfile:
        assert auto.open_file("my_project.flp") is True
        mock_startfile.assert_called_once_with("my_project.flp")

    # If os.startfile doesn't exist
    orig_hasattr = hasattr
    def mock_hasattr(obj, name):
        if obj is os and name == "startfile":
            return False
        return orig_hasattr(obj, name)

    with patch("builtins.hasattr", side_effect=mock_hasattr), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert auto.open_file("my_project.flp") is True
        mock_run.assert_called_once_with(
            ["cmd", "/c", "start", "my_project.flp"],
            capture_output=True,
            check=False
        )


def test_path_resolution(tmp_path):
    """Test get_fl_user_data_path handles windows/mac folders correctly."""
    # Test macOS
    with patch("sys.platform", "darwin"), \
         patch("pathlib.Path.home") as mock_home:
        mock_home.return_value = tmp_path
        expected = tmp_path / "Documents" / "Image-Line" / "FL Studio"
        assert get_fl_user_data_path() == expected

    # Test Windows standard path
    mock_ctypes = MagicMock()
    mock_buf = MagicMock(value=str(tmp_path))
    mock_ctypes.create_unicode_buffer.return_value = mock_buf
    with patch("sys.platform", "win32"), \
         patch.dict("sys.modules", {"ctypes": mock_ctypes}):
        expected = tmp_path / "Image-Line" / "FL Studio"
        assert get_fl_user_data_path() == expected
        mock_ctypes.windll.shell32.SHGetFolderPathW.assert_called_once()


def test_vst_scanner(tmp_path):
    """Test scan_plugin_database parses .fst files correctly in categorized folders."""
    # Setup mock user documents dir
    fl_user = tmp_path / "Image-Line" / "FL Studio"
    db_path = fl_user / "Presets" / "Plugin database"
    os.makedirs(db_path / "Generators" / "Synths", exist_ok=True)
    os.makedirs(db_path / "Effects" / "Reverbs", exist_ok=True)

    # Write dummy files
    Path(db_path / "Generators" / "Synths" / "Serum.fst").touch()
    Path(db_path / "Effects" / "Reverbs" / "Valhalla.fst").touch()

    with patch("fl_studio_mcp.tools.vst_scanner.get_fl_user_data_path") as mock_get_path:
        mock_get_path.return_value = fl_user
        
        result = scan_plugin_database()
        
        assert len(result["generators"]) == 1
        assert result["generators"][0]["name"] == "Serum"
        assert result["generators"][0]["category"] == "Synths"

        assert len(result["effects"]) == 1
        assert result["effects"][0]["name"] == "Valhalla"
        assert result["effects"][0]["category"] == "Reverbs"

def test_library_scanner(tmp_path):
    """Test scan_user_library indexes templates and scores correctly."""
    fl_user = tmp_path / "Image-Line" / "FL Studio"
    scores_path = fl_user / "Presets" / "Scores" / "Chords"
    os.makedirs(scores_path, exist_ok=True)
    Path(scores_path / "Major.fsc").touch()

    with patch("fl_studio_mcp.tools.library.get_fl_user_data_path") as mock_get_path:
        mock_get_path.return_value = fl_user
        
        result = scan_user_library("scores")
        assert "scores" in result
        assert len(result["scores"]) == 1
        assert result["scores"][0]["name"] == "Major"
        assert result["scores"][0]["category"] == "Chords"

@pytest.mark.asyncio
async def test_tools_registration():
    """Verify tool registration works with FastMCP instances."""
    mcp = FastMCP("test_mcp")
    register_vst(mcp)
    register_library(mcp)
    register_gui(mcp)

    tools = getattr(mcp, "_tools", None) or getattr(mcp._tool_manager, "_tools", {})
    assert "fl_list_installed_plugins" in tools
    assert "fl_load_plugin" in tools
    assert "fl_list_library" in tools
    assert "fl_load_file" in tools
    assert "fl_click_at" in tools
    assert "fl_reset_ui" in tools
    assert "fl_dismiss_popup" in tools

