"""Tests for the MIDI bridge — connection management and dry-run send paths."""

import pytest

from fl_studio_mcp.bridge import FLStudioBridge
from fl_studio_mcp.errors import ErrorCode, FLMCPError
from fl_studio_mcp.protocol import encode_tempo, mmc_play, mmc_stop


class TestBridgeDryRun:
    """All these tests run without any MIDI hardware."""

    def test_not_connected_by_default(self):
        bridge = FLStudioBridge.get()
        assert not bridge.connected

    def test_dry_run_connect(self, dry_bridge):
        assert dry_bridge.connected
        assert dry_bridge.dry_run
        assert dry_bridge.port_name == "(dry-run)"

    def test_send_raw_dry_run(self, dry_bridge):
        result = dry_bridge.send_raw(mmc_play())
        assert result["dry_run"] is True
        assert "F0" in result["would_send_bytes"]
        assert result["byte_count"] == 6

    def test_send_stop_dry_run(self, dry_bridge):
        result = dry_bridge.send_raw(mmc_stop())
        assert result["dry_run"] is True
        assert "F7" in result["would_send_bytes"]

    def test_send_tempo_dry_run(self, dry_bridge):
        sysex = encode_tempo(140)
        result = dry_bridge.send_raw(sysex)
        assert result["dry_run"] is True
        assert result["byte_count"] == len(sysex)

    def test_send_without_connect_raises(self):
        bridge = FLStudioBridge.get()
        with pytest.raises(FLMCPError) as exc_info:
            bridge.send_raw(mmc_play())
        assert exc_info.value.code == ErrorCode.NOT_CONNECTED

    def test_status_dict(self, dry_bridge):
        status = dry_bridge.status()
        assert status["connected"] is True
        assert status["dry_run"] is True
        assert "port" in status
        assert "platform_transport" in status

    def test_reconnect_idempotent(self, dry_bridge):
        # Calling connect again should not raise
        dry_bridge.connect("another-port", dry_run=True)
        assert dry_bridge.connected

    def test_singleton(self):
        b1 = FLStudioBridge.get()
        b2 = FLStudioBridge.get()
        assert b1 is b2

    def test_no_port_found_error(self):
        bridge = FLStudioBridge.get()
        # Attempting to connect to a nonexistent port should raise ValueError
        # (resolve_port raises it; connect wraps it as FLMCPError)
        with pytest.raises((FLMCPError, ValueError)):
            bridge.connect("__port_that_does_not_exist__", dry_run=False)
