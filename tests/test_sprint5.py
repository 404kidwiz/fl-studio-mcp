"""Tests for Sprint 5: Undo, Redo, Ping, and Write-ACK validation.

Includes protocol tests, MCP tool behaviors, and Click CLI commands.
"""

import json
import pytest
import unittest.mock
from click.testing import CliRunner

from fl_studio_mcp.bridge import FLStudioBridge
from fl_studio_mcp.cli import main
from fl_studio_mcp.models import PingInput, UndoInput, RedoInput
from fl_studio_mcp.protocol import (
    CMD_PING,
    CMD_UNDO,
    CMD_REDO,
    RESP_ACK,
    encode_ping,
    encode_undo,
    encode_redo,
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


def _tool(module_name: str, tool_name: str):
    """Import the connection/project tool module and return its registered function."""
    from mcp.server.fastmcp import FastMCP

    if module_name == "connection":
        from fl_studio_mcp.tools import connection as mod
    else:
        from fl_studio_mcp.tools import project as mod
    _mcp = FastMCP("test")
    mod.register(_mcp)
    return {t.name: t for t in _mcp._tool_manager.list_tools()}[tool_name].fn


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    """Isolate CLI tests from the real ~/.fl_studio_mcp.json file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# 1. Protocol Tests
# ---------------------------------------------------------------------------


class TestSprint5Protocol:
    def test_encode_ping(self):
        raw = encode_ping(42)
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x18  # CMD_PING
        assert raw[3] == 42  # challenge
        assert raw[-1] == 0xF7

    def test_encode_ping_bounds(self):
        with pytest.raises(ValueError):
            encode_ping(-1)
        with pytest.raises(ValueError):
            encode_ping(128)

    def test_encode_undo(self):
        raw = encode_undo()
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x1D  # CMD_UNDO
        assert raw[-1] == 0xF7

    def test_encode_redo(self):
        raw = encode_redo()
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x1E  # CMD_REDO
        assert raw[-1] == 0xF7


# ---------------------------------------------------------------------------
# 2. MCP Tool Tests
# ---------------------------------------------------------------------------


class TestSprint5Tools:
    async def test_fl_ping_dry_run(self, dry_bridge):
        fn = _tool("connection", "fl_ping")
        result = parse(await fn(PingInput(challenge=55)))
        assert result["dry_run"] is True
        assert result["success"] is True
        assert result["challenge"] == 55

    async def test_fl_ping_live_success(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        def mock_send(msg):
            cmd, payload = decode_sysex(msg.bytes())
            if cmd == CMD_PING:
                # Echo challenge back
                _inject_response(dry_bridge, CMD_PING, [payload[0]])

        dry_bridge._output_port.send = mock_send

        fn = _tool("connection", "fl_ping")
        result = parse(await fn(PingInput(challenge=7, timeout_ms=500)))
        assert result["success"] is True
        assert result["challenge"] == 7
        assert "response_time_ms" in result

        # Restore
        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_ping_timeout(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        fn = _tool("connection", "fl_ping")
        result = parse(await fn(PingInput(challenge=7, timeout_ms=100)))
        assert result["error"] == "TIMEOUT"

        # Restore
        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_undo_dry_run(self, dry_bridge):
        fn = _tool("project", "fl_undo")
        result = parse(await fn(UndoInput(ack=False)))
        assert result["dry_run"] is True
        assert result["command"] == "UNDO"
        assert "F0 7D 1D F7" in result["would_send_bytes"]

    async def test_fl_undo_live_with_ack(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        def mock_send(msg):
            cmd, _ = decode_sysex(msg.bytes())
            if cmd == CMD_UNDO:
                # Send RESP_ACK (0x1F) with CMD_UNDO in payload
                _inject_response(dry_bridge, RESP_ACK, [CMD_UNDO])

        dry_bridge._output_port.send = mock_send

        fn = _tool("project", "fl_undo")
        result = parse(await fn(UndoInput(ack=True, timeout_ms=500)))
        assert result["sent"] is True
        assert result["command"] == "UNDO"
        assert result["ack_received"] is True

        # Restore
        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_redo_live_with_ack(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        def mock_send(msg):
            cmd, _ = decode_sysex(msg.bytes())
            if cmd == CMD_REDO:
                # Send RESP_ACK (0x1F) with CMD_REDO in payload
                _inject_response(dry_bridge, RESP_ACK, [CMD_REDO])

        dry_bridge._output_port.send = mock_send

        fn = _tool("project", "fl_redo")
        result = parse(await fn(RedoInput(ack=True, timeout_ms=500)))
        assert result["sent"] is True
        assert result["command"] == "REDO"
        assert result["ack_received"] is True

        # Restore
        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None


# ---------------------------------------------------------------------------
# 3. CLI Command Tests
# ---------------------------------------------------------------------------


class TestSprint5CLI:
    def test_cli_ping_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

        result = runner.invoke(main, ["ping", "--challenge", "88"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["success"] is True
        assert data["challenge"] == 88

    def test_cli_undo_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

        result = runner.invoke(main, ["undo"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True

    def test_cli_redo_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])

        result = runner.invoke(main, ["redo"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
