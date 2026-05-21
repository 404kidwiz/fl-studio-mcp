"""Tests for Sprint 4: Mixer & Routing.

Includes protocol tests, MCP tool behaviors, and Click CLI commands.
"""

import asyncio
import json
import pytest
import unittest.mock
from click.testing import CliRunner

from fl_studio_mcp.bridge import FLStudioBridge
from fl_studio_mcp.cli import main
from fl_studio_mcp.models import (
    SetMixerVolumeInput,
    SetMixerPanInput,
    RouteToMixerInput,
    GetMixerStateInput,
)
from fl_studio_mcp.protocol import (
    RESP_MIXER_STATE,
    encode_set_mixer_vol,
    encode_set_mixer_pan,
    encode_route_to_mixer,
    encode_query_mixer_state,
    decode_resp_mixer_state,
    encode_resp_mixer_state,
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
    """Import the mixing tool module and return its registered function."""
    from mcp.server.fastmcp import FastMCP
    from fl_studio_mcp.tools import mixing
    _mcp = FastMCP("test")
    mixing.register(_mcp)
    return {t.name: t for t in _mcp._tool_manager.list_tools()}[tool_name].fn


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    """Isolate CLI tests from the real ~/.fl_studio_mcp.json file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# 1. Protocol Tests
# ---------------------------------------------------------------------------

class TestSprint4Protocol:
    def test_encode_set_mixer_vol(self):
        # Track 5, Volume 100
        raw = encode_set_mixer_vol(5, 100)
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x19  # CMD_SET_MIXER_VOL
        assert raw[3] == 5     # track_idx
        assert raw[4] == 100   # volume
        assert raw[-1] == 0xF7

    def test_encode_set_mixer_vol_bounds(self):
        with pytest.raises(ValueError):
            encode_set_mixer_vol(-1, 100)
        with pytest.raises(ValueError):
            encode_set_mixer_vol(128, 100)
        with pytest.raises(ValueError):
            encode_set_mixer_vol(5, -1)
        with pytest.raises(ValueError):
            encode_set_mixer_vol(5, 128)

    def test_encode_set_mixer_pan(self):
        # Track 10, Pan 64
        raw = encode_set_mixer_pan(10, 64)
        assert raw[2] == 0x1A  # CMD_SET_MIXER_PAN
        assert raw[3] == 10
        assert raw[4] == 64
        
    def test_encode_set_mixer_pan_bounds(self):
        with pytest.raises(ValueError):
            encode_set_mixer_pan(-1, 64)
        with pytest.raises(ValueError):
            encode_set_mixer_pan(128, 64)
        with pytest.raises(ValueError):
            encode_set_mixer_pan(10, -1)
        with pytest.raises(ValueError):
            encode_set_mixer_pan(10, 128)

    def test_encode_route_to_mixer(self):
        # Channel 3, Track 12
        raw = encode_route_to_mixer(3, 12)
        assert raw[2] == 0x1B  # CMD_ROUTE_TO_MIXER
        assert raw[3] == 3
        assert raw[4] == 12

    def test_encode_route_to_mixer_bounds(self):
        with pytest.raises(ValueError):
            encode_route_to_mixer(-1, 12)
        with pytest.raises(ValueError):
            encode_route_to_mixer(128, 12)
        with pytest.raises(ValueError):
            encode_route_to_mixer(3, -1)
        with pytest.raises(ValueError):
            encode_route_to_mixer(3, 128)

    def test_encode_query_mixer_state(self):
        # Start 0, End 15 (16 tracks total)
        raw = encode_query_mixer_state(0, 15)
        assert raw[2] == 0x1C  # CMD_QUERY_MIXER_STATE
        assert raw[3] == 0
        assert raw[4] == 15

    def test_encode_query_mixer_state_bounds(self):
        with pytest.raises(ValueError):
            encode_query_mixer_state(-1, 15)
        with pytest.raises(ValueError):
            encode_query_mixer_state(0, 128)
        with pytest.raises(ValueError):
            # start > end
            encode_query_mixer_state(10, 5)
        with pytest.raises(ValueError):
            # > 32 range
            encode_query_mixer_state(0, 32)

    def test_mixer_state_response_roundtrip(self):
        tracks = [
            {"volume": 100, "pan": 64, "name": "Master"},
            {"volume": 90, "pan": 32, "name": "Kick"},
            {"volume": 85, "pan": 96, "name": "Snare"},
        ]
        raw = encode_resp_mixer_state(0, 2, tracks)
        cmd, payload = decode_sysex(raw)
        assert cmd == RESP_MIXER_STATE
        decoded = decode_resp_mixer_state(payload)
        
        assert decoded["start_track"] == 0
        assert decoded["end_track"] == 2
        assert len(decoded["tracks"]) == 3
        assert decoded["tracks"][0] == {"volume": 100, "pan": 64, "name": "Master"}
        assert decoded["tracks"][1] == {"volume": 90, "pan": 32, "name": "Kick"}
        assert decoded["tracks"][2] == {"volume": 85, "pan": 96, "name": "Snare"}


# ---------------------------------------------------------------------------
# 2. MCP Tool Tests
# ---------------------------------------------------------------------------

class TestSprint4Tools:
    async def test_fl_set_mixer_volume_dry_run(self, dry_bridge):
        fn = _tool("fl_set_mixer_volume")
        result = parse(await fn(SetMixerVolumeInput(track_index=1, volume=90)))
        assert result["dry_run"] is True
        assert result["track_index"] == 1
        assert result["volume"] == 90
        assert "would_send_bytes" in result
        assert "F0 7D 19 01 5A F7" in result["would_send_bytes"]

    async def test_fl_set_mixer_pan_dry_run(self, dry_bridge):
        fn = _tool("fl_set_mixer_pan")
        result = parse(await fn(SetMixerPanInput(track_index=2, pan=32)))
        assert result["dry_run"] is True
        assert result["track_index"] == 2
        assert result["pan"] == 32
        assert "would_send_bytes" in result
        assert "F0 7D 1A 02 20 F7" in result["would_send_bytes"]

    async def test_fl_route_to_mixer_dry_run(self, dry_bridge):
        fn = _tool("fl_route_to_mixer")
        result = parse(await fn(RouteToMixerInput(channel_index=0, track_index=4)))
        assert result["dry_run"] is True
        assert result["channel_index"] == 0
        assert result["track_index"] == 4
        assert "would_send_bytes" in result
        assert "F0 7D 1B 00 04 F7" in result["would_send_bytes"]

    async def test_fl_get_mixer_state_dry_run(self, dry_bridge):
        fn = _tool("fl_get_mixer_state")
        result = parse(await fn(GetMixerStateInput(start_track=0, end_track=4)))
        assert result["dry_run"] is True
        assert result["start_track"] == 0
        assert result["end_track"] == 4
        assert len(result["tracks"]) == 5
        assert result["tracks"][0]["name"] == "Master"
        assert result["tracks"][1]["name"] == "Insert 1"

    async def test_fl_get_mixer_state_live_success(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        # Simulated response payload
        tracks = [
            {"volume": 100, "pan": 64, "name": "Master"},
            {"volume": 90, "pan": 40, "name": "Kick"},
        ]
        raw = encode_resp_mixer_state(0, 1, tracks)
        _, payload = decode_sysex(raw)

        def mock_send(msg):
            cmd, _ = decode_sysex(msg.bytes())
            if cmd == 0x1C:  # CMD_QUERY_MIXER_STATE
                _inject_response(dry_bridge, RESP_MIXER_STATE, payload)
        dry_bridge._output_port.send = mock_send

        fn = _tool("fl_get_mixer_state")
        result = parse(await fn(GetMixerStateInput(start_track=0, end_track=1, timeout_ms=500)))
        assert result["source"] == "fl_studio"
        assert result["start_track"] == 0
        assert result["end_track"] == 1
        assert len(result["tracks"]) == 2
        assert result["tracks"][0] == {"volume": 100, "pan": 64, "name": "Master"}
        assert result["tracks"][1] == {"volume": 90, "pan": 40, "name": "Kick"}

        # Restore
        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_get_mixer_state_timeout(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        fn = _tool("fl_get_mixer_state")
        result = parse(await fn(GetMixerStateInput(start_track=0, end_track=2, timeout_ms=100)))
        assert result["error"] == "TIMEOUT"

        # Restore
        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None


# ---------------------------------------------------------------------------
# 3. CLI Command Tests
# ---------------------------------------------------------------------------

class TestSprint4CLI:
    def test_cli_mixer_volume_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

        result = runner.invoke(main, ["mixer", "volume", "3", "110"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["track_index"] == 3
        assert data["volume"] == 110

    def test_cli_mixer_pan_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

        result = runner.invoke(main, ["mixer", "pan", "2", "30"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["track_index"] == 2
        assert data["pan"] == 30

    def test_cli_mixer_route_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

        result = runner.invoke(main, ["mixer", "route", "1", "4"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["channel_index"] == 1
        assert data["track_index"] == 4

    def test_cli_mixer_state_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

        result = runner.invoke(main, ["mixer", "state", "--start", "0", "--end", "3"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["start_track"] == 0
        assert data["end_track"] == 3
        assert len(data["tracks"]) == 4

    def test_cli_mixer_state_invalid_range(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

        # Range > 32
        result = runner.invoke(main, ["mixer", "state", "--start", "0", "--end", "40"])
        assert result.exit_code != 0
        assert "exceeds maximum of 32" in result.output

        # Start > End
        result = runner.invoke(main, ["mixer", "state", "--start", "10", "--end", "5"])
        assert result.exit_code != 0
        assert "cannot be greater than" in result.output
