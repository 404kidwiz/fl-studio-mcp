"""Tests for Sprint 3: Bidirectional Read & Pattern Control.

Includes protocol roundtrips, MCP tool behaviors, and Click CLI commands in dry-run mode.
"""

import asyncio
import json
import pytest
from click.testing import CliRunner

from fl_studio_mcp.bridge import FLStudioBridge
from fl_studio_mcp.cli import main, get_config_path
from fl_studio_mcp.models import (
    GetNotesInput,
    GetContextInput,
    SetPatternLengthInput,
    RenameChannelInput,
    RenamePatternInput,
)
from fl_studio_mcp.protocol import (
    RESP_NOTES,
    RESP_STATUS,
    RESP_CHANNELS,
    encode_get_notes,
    encode_set_pattern_length,
    encode_rename_channel,
    encode_rename_pattern,
    decode_resp_notes,
    encode_resp_notes,
    encode_resp_status,
    encode_resp_channels,
    decode_sysex,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse(result: str) -> dict:
    return json.loads(result)


def _inject_response(bridge: FLStudioBridge, cmd: int, payload: list) -> None:
    """Directly place a simulated FL Studio response into the bridge queue."""
    bridge._response_queue.put_nowait({"cmd": cmd, "payload": payload})


def _tool(tool_name: str):
    """Import the pattern_control tool module and return its registered function."""
    from mcp.server.fastmcp import FastMCP
    from fl_studio_mcp.tools import pattern_control
    _mcp = FastMCP("test")
    pattern_control.register(_mcp)
    return {t.name: t for t in _mcp._tool_manager.list_tools()}[tool_name].fn


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    """Isolate CLI tests from the real ~/.fl_studio_mcp.json file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# 1. Protocol Tests
# ---------------------------------------------------------------------------

class TestSprint3Protocol:
    def test_encode_get_notes(self):
        raw = encode_get_notes()
        assert raw == bytes([0xF0, 0x7D, 0x14, 0xF7])

    def test_encode_set_pattern_length(self):
        # Index 10 (hi=0, lo=10), Length 16 (hi=0, lo=16)
        raw = encode_set_pattern_length(10, 16)
        assert raw[2] == 0x15
        assert raw[3] == 0  # pat_hi
        assert raw[4] == 10  # pat_lo
        assert raw[5] == 0  # len_hi
        assert raw[6] == 16  # len_lo

        # Index 150 (hi=1, lo=22), Length 200 (hi=1, lo=72)
        raw2 = encode_set_pattern_length(150, 200)
        assert raw2[3] == 1
        assert raw2[4] == 22
        assert raw2[5] == 1
        assert raw2[6] == 72

    def test_encode_set_pattern_length_bounds(self):
        with pytest.raises(ValueError):
            encode_set_pattern_length(-1, 4)
        with pytest.raises(ValueError):
            encode_set_pattern_length(1000, 4)
        with pytest.raises(ValueError):
            encode_set_pattern_length(0, 0)
        with pytest.raises(ValueError):
            encode_set_pattern_length(0, 1000)

    def test_rename_channel(self):
        # index 5, name "Piano"
        raw = encode_rename_channel(5, "Piano")
        assert raw[2] == 0x16
        assert raw[3] == 5
        assert raw[4] == 5  # len("Piano")
        assert bytes(raw[5:-1]).decode("ascii") == "Piano"

    def test_rename_channel_bounds(self):
        with pytest.raises(ValueError):
            encode_rename_channel(-1, "Piano")
        with pytest.raises(ValueError):
            encode_rename_channel(128, "Piano")

    def test_rename_pattern(self):
        # pat_idx 150 (hi=1, lo=22), name "Drums"
        raw = encode_rename_pattern(150, "Drums")
        assert raw[2] == 0x17
        assert raw[3] == 1
        assert raw[4] == 22
        assert raw[5] == 5  # len("Drums")
        assert bytes(raw[6:-1]).decode("ascii") == "Drums"

    def test_rename_pattern_bounds(self):
        with pytest.raises(ValueError):
            encode_rename_pattern(-1, "Drums")
        with pytest.raises(ValueError):
            encode_rename_pattern(1000, "Drums")

    def test_resp_notes_roundtrip(self):
        notes = [
            {"pitch": 60, "velocity": 100, "channel": 0, "start_tick": 0, "duration_ticks": 96},
            {"pitch": 64, "velocity": 90, "channel": 1, "start_tick": 96, "duration_ticks": 192},
        ]
        raw = encode_resp_notes(notes)
        cmd, payload = decode_sysex(raw)
        assert cmd == RESP_NOTES
        decoded = decode_resp_notes(payload)
        assert decoded == notes


# ---------------------------------------------------------------------------
# 2. MCP Tool Tests
# ---------------------------------------------------------------------------

class TestSprint3Tools:
    async def test_fl_get_notes_dry_run(self, dry_bridge):
        fn = _tool("fl_get_notes")
        result = parse(await fn(GetNotesInput()))
        assert result["dry_run"] is True
        assert result["source"] == "dry_run_preview"
        assert len(result["notes"]) == 3

    async def test_fl_get_notes_not_connected(self):
        fn = _tool("fl_get_notes")
        result = parse(await fn(GetNotesInput()))
        assert "error" in result

    async def test_fl_get_notes_live_timeout(self, dry_bridge):
        # temporarily make bridge look not dry-run to trigger live query path
        import unittest.mock
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()
        fn = _tool("fl_get_notes")
        result = parse(await fn(GetNotesInput(timeout_ms=100)))
        assert result["error"] == "TIMEOUT"
        # restore
        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_get_notes_live_success(self, dry_bridge):
        import unittest.mock
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()
        
        # Prepare response
        mock_notes = [{"pitch": 60, "velocity": 100, "channel": 0, "start_tick": 0, "duration_ticks": 96}]
        raw = encode_resp_notes(mock_notes)
        _, payload = decode_sysex(raw)
        
        def mock_send(msg):
            cmd, _ = decode_sysex(msg.bytes())
            if cmd == 0x14:  # CMD_GET_NOTES
                _inject_response(dry_bridge, RESP_NOTES, payload)
        dry_bridge._output_port.send = mock_send

        fn = _tool("fl_get_notes")
        result = parse(await fn(GetNotesInput(timeout_ms=500)))
        assert result["notes"] == mock_notes
        assert result["source"] == "fl_studio"
        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_get_context_dry_run(self, dry_bridge):
        fn = _tool("fl_get_context")
        result = parse(await fn(GetContextInput()))
        assert result["dry_run"] is True
        assert "status" in result
        assert "channels" in result
        assert "notes" in result

    async def test_fl_get_context_live_success(self, dry_bridge):
        import unittest.mock
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        # Inject Status Response
        status_raw = encode_resp_status(True, 120, 2, 4)
        _, status_payload = decode_sysex(status_raw)

        # Inject Channels Response
        channels_raw = encode_resp_channels(["Kick", "Snare"])
        _, channels_payload = decode_sysex(channels_raw)

        # Inject Notes Response
        notes_raw = encode_resp_notes([])
        _, notes_payload = decode_sysex(notes_raw)

        def mock_send(msg):
            cmd, _ = decode_sysex(msg.bytes())
            if cmd == 0x06:  # CMD_QUERY_STATUS
                _inject_response(dry_bridge, RESP_STATUS, status_payload)
            elif cmd == 0x07:  # CMD_QUERY_CHANNELS
                _inject_response(dry_bridge, RESP_CHANNELS, channels_payload)
            elif cmd == 0x14:  # CMD_GET_NOTES
                _inject_response(dry_bridge, RESP_NOTES, notes_payload)
        dry_bridge._output_port.send = mock_send

        fn = _tool("fl_get_context")
        result = parse(await fn(GetContextInput(timeout_ms=500)))
        assert result["status"]["bpm"] == 120
        assert result["channels"] == ["Kick", "Snare"]
        assert result["notes"] == []
        assert result["source"] == "fl_studio"
        
        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_set_pattern_length(self, dry_bridge):
        fn = _tool("fl_set_pattern_length")
        result = parse(await fn(SetPatternLengthInput(pattern_index=1, length_beats=16)))
        assert result["dry_run"] is True
        assert result["pattern_index"] == 1
        assert result["length_beats"] == 16
        assert "F0 7D 15 00 01 00 10 F7" in result["would_send_bytes"]

    async def test_fl_rename_channel(self, dry_bridge):
        fn = _tool("fl_rename_channel")
        result = parse(await fn(RenameChannelInput(channel_index=2, name="Bassline")))
        assert result["dry_run"] is True
        assert result["channel_index"] == 2
        assert result["name"] == "Bassline"
        # F0 7D 16 02 08 (len) + ords("Bassline") + F7
        assert "F0 7D 16 02 08" in result["would_send_bytes"]

    async def test_fl_rename_pattern(self, dry_bridge):
        fn = _tool("fl_rename_pattern")
        result = parse(await fn(RenamePatternInput(pattern_index=10, name="Verse")))
        assert result["dry_run"] is True
        assert result["pattern_index"] == 10
        assert result["name"] == "Verse"
        # F0 7D 17 00 0A 05 (len) + ords("Verse") + F7
        assert "F0 7D 17 00 0A 05" in result["would_send_bytes"]


# ---------------------------------------------------------------------------
# 3. CLI Command Tests
# ---------------------------------------------------------------------------

class TestSprint3CLI:
    def test_cli_patterns_notes_dry_run(self, mock_home):
        runner = CliRunner()
        # Connect dry run first
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

        result = runner.invoke(main, ["patterns", "notes"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert len(data["notes"]) == 3

    def test_cli_patterns_length_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

        result = runner.invoke(main, ["patterns", "length", "5", "8"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["pattern_index"] == 5
        assert data["length_beats"] == 8

    def test_cli_patterns_rename_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

        result = runner.invoke(main, ["patterns", "rename", "3", "Chorus"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["pattern_index"] == 3
        assert data["name"] == "Chorus"

    def test_cli_patterns_rename_non_ascii_fails(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

        result = runner.invoke(main, ["patterns", "rename", "3", "Chörus"])
        assert result.exit_code != 0
        assert "7-bit ASCII" in result.output

    def test_cli_channels_rename_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

        result = runner.invoke(main, ["channels", "rename", "0", "KickOut"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["channel_index"] == 0
        assert data["name"] == "KickOut"

    def test_cli_context_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

        result = runner.invoke(main, ["context"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert "status" in data
        assert "channels" in data
        assert "notes" in data
