"""Tests for Option 1: Live Windows Integration & loopMIDI Deployment.

Exercises loopMIDI transport discovery and VBScript-based GUI automation on Windows
using robust cross-platform mock environments.
"""

import os
import sys
import subprocess
from unittest.mock import MagicMock, patch
import pytest

import mido
from fl_studio_mcp.automation.windows import WindowsAutomation
from fl_studio_mcp.transports.windows import WindowsMIDITransport


class TestWindowsAutomationFortification:
    """Tests to verify VBScript GUI automation, timeout guards, and encoding safety."""

    def test_vbscript_execution_success(self):
        """Verify standard VBScript run generates code and executes cleanly."""
        auto = WindowsAutomation()
        
        with patch("tempfile.mkstemp") as mock_mkstemp, \
             patch("os.fdopen") as mock_fdopen, \
             patch("subprocess.run") as mock_run, \
             patch("os.path.exists") as mock_exists, \
             patch("os.remove") as mock_remove:
            
            mock_mkstemp.return_value = (101, "test_file.vbs")
            mock_file = MagicMock()
            mock_fdopen.return_value.__enter__.return_value = mock_file
            # Simulate cscript returning "  1 \r\n"
            mock_run.return_value = MagicMock(returncode=0, stdout="  1 \r\n")
            mock_exists.return_value = True

            # Call focus
            res = auto.focus_fl_studio()
            
            assert res is True
            mock_file.write.assert_called_once()
            script_content = mock_file.write.call_args[0][0]
            assert 'AppActivate("FL Studio")' in script_content
            
            # Check subprocess call has timeout=5.0 and errors="replace"
            mock_run.assert_called_once_with(
                ["cscript", "//nologo", "test_file.vbs"],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=5.0,
                check=False
            )
            mock_remove.assert_called_once_with("test_file.vbs")

    def test_vbscript_timeout_graceful_recovery(self):
        """Verify that VBScript hangs trigger TimeoutExpired and fail gracefully."""
        auto = WindowsAutomation()
        
        with patch("tempfile.mkstemp") as mock_mkstemp, \
             patch("os.fdopen") as mock_fdopen, \
             patch("subprocess.run") as mock_run, \
             patch("os.path.exists") as mock_exists, \
             patch("os.remove") as mock_remove:
            
            mock_mkstemp.return_value = (101, "hang.vbs")
            mock_file = MagicMock()
            mock_fdopen.return_value.__enter__.return_value = mock_file
            
            # Simulate subprocess raising TimeoutExpired
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["cscript", "//nologo", "hang.vbs"],
                timeout=5.0
            )
            mock_exists.return_value = True

            # Call focus and verify it catches exception and returns False
            res = auto.focus_fl_studio()
            
            assert res is False
            mock_remove.assert_called_once_with("hang.vbs")

    def test_vbscript_unhandled_exception_graceful_recovery(self):
        """Verify that general script execution errors are caught cleanly."""
        auto = WindowsAutomation()
        
        with patch("tempfile.mkstemp") as mock_mkstemp, \
             patch("os.fdopen") as mock_fdopen, \
             patch("subprocess.run") as mock_run:
            
            mock_mkstemp.return_value = (101, "err.vbs")
            mock_file = MagicMock()
            mock_fdopen.return_value.__enter__.return_value = mock_file
            
            # Simulate standard Exception
            mock_run.side_effect = RuntimeError("Disk full")

            res = auto.load_plugin("Serum")
            assert res is False

    def test_windows_open_file_fallbacks(self):
        """Verify that open_file uses startfile or starts a shell wrapper on Windows."""
        auto = WindowsAutomation()
        
        # Scenario 1: startfile exists (default Windows)
        with patch("os.startfile", create=True) as mock_startfile:
            res = auto.open_file("my_project.flp")
            assert res is True
            mock_startfile.assert_called_once_with("my_project.flp")

        # Scenario 2: startfile missing, falls back to cmd start
        orig_hasattr = hasattr
        def mock_hasattr(obj, name):
            if obj is os and name == "startfile":
                return False
            return orig_hasattr(obj, name)

        with patch("builtins.hasattr", side_effect=mock_hasattr), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            res = auto.open_file("my_project.flp")
            
            assert res is True
            mock_run.assert_called_once_with(
                ["cmd", "/c", "start", "my_project.flp"],
                capture_output=True,
                check=False
            )


class TestWindowsMIDITransport:
    """Tests to verify loopMIDI discovery, custom naming overrides, and I/O."""

    def test_default_hint_without_override(self):
        """Verify the loopMIDI default port name is 'FL Studio Bus'."""
        transport = WindowsMIDITransport()
        assert transport.default_output_hint == "FL Studio Bus"

    def test_default_hint_with_env_override(self):
        """Verify the loopMIDI default port name respects the FL_MCP_PORT environment variable."""
        transport = WindowsMIDITransport()
        
        with patch.dict(os.environ, {"FL_MCP_PORT": "Custom Virtual Bus"}):
            assert transport.default_output_hint == "Custom Virtual Bus"

    def test_midi_port_listing(self):
        """Verify listing of input and output ports calls mido correctly."""
        transport = WindowsMIDITransport()
        
        with patch("mido.get_input_names") as mock_inputs, \
             patch("mido.get_output_names") as mock_outputs:
            mock_inputs.return_value = ["Input Port A", "FL Studio Bus"]
            mock_outputs.return_value = ["Output Port A", "FL Studio Bus"]

            assert transport.list_input_ports() == ["Input Port A", "FL Studio Bus"]
            assert transport.list_output_ports() == ["Output Port A", "FL Studio Bus"]

    def test_midi_port_opening(self):
        """Verify opening input and output ports invokes mido."""
        transport = WindowsMIDITransport()
        
        with patch("mido.open_input") as mock_open_in, \
             patch("mido.open_output") as mock_open_out:
            
            mock_input_port = MagicMock()
            mock_output_port = MagicMock()
            mock_open_in.return_value = mock_input_port
            mock_open_out.return_value = mock_output_port

            # Test Output Port
            out_port = transport.open_output("FL Studio Bus")
            assert out_port == mock_output_port
            mock_open_out.assert_called_once_with("FL Studio Bus")

            # Test Input Port without callback
            in_port = transport.open_input("FL Studio Bus")
            assert in_port == mock_input_port
            mock_open_in.assert_called_with("FL Studio Bus")

            # Test Input Port with callback
            callback_fn = lambda msg: None
            in_port_cb = transport.open_input("FL Studio Bus", callback=callback_fn)
            assert in_port_cb == mock_input_port
            mock_open_in.assert_called_with("FL Studio Bus", callback=callback_fn)
