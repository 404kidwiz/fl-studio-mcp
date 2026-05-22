"""Tests for bidirectional protocol and the 5 new tools.

All tests run in dry-run mode — no MIDI hardware required.
Bidirectional tests use a mock queue injection to simulate FL Studio responses.
"""

import asyncio
import json
import queue as thread_queue

import pytest

from fl_studio_mcp.bridge import FLStudioBridge
from fl_studio_mcp.models import (
    CreatePatternInput,
    GetStatusInput,
    ListChannelsInput,
    SelectPatternInput,
    SetChannelVolumeInput,
)
from fl_studio_mcp.protocol import (
    RESP_CHANNELS,
    RESP_STATUS,
    decode_resp_channels,
    decode_resp_status,
    encode_new_pattern,
    encode_query_channels,
    encode_query_status,
    encode_resp_channels,
    encode_resp_status,
    encode_select_pattern,
    encode_set_channel_vol,
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
    """Import a tool module and return its registered function."""
    import importlib
    from mcp.server.fastmcp import FastMCP

    mod = importlib.import_module(f"fl_studio_mcp.tools.{module_name}")
    _mcp = FastMCP("test")
    mod.register(_mcp)
    return {t.name: t for t in _mcp._tool_manager.list_tools()}[tool_name].fn


# ---------------------------------------------------------------------------
# Protocol: new encoders
# ---------------------------------------------------------------------------


class TestNewProtocolEncoders:
    def test_query_status_framing(self):
        raw = encode_query_status()
        assert raw == bytes([0xF0, 0x7D, 0x06, 0xF7])

    def test_query_channels_framing(self):
        raw = encode_query_channels()
        assert raw == bytes([0xF0, 0x7D, 0x07, 0xF7])

    def test_set_channel_vol(self):
        raw = encode_set_channel_vol(3, 100)
        assert raw[2] == 0x08
        assert raw[3] == 3
        assert raw[4] == 100

    def test_set_channel_vol_bounds(self):
        with pytest.raises(ValueError):
            encode_set_channel_vol(128, 100)
        with pytest.raises(ValueError):
            encode_set_channel_vol(0, 128)

    def test_new_pattern_framing(self):
        raw = encode_new_pattern()
        assert raw == bytes([0xF0, 0x7D, 0x09, 0xF7])

    def test_select_pattern(self):
        raw = encode_select_pattern(5)
        assert raw[2] == 0x0A
        assert raw[3] == 5

    def test_select_pattern_bounds(self):
        with pytest.raises(ValueError):
            encode_select_pattern(128)


class TestResponseEncoderDecoder:
    def test_resp_status_roundtrip(self):
        raw = encode_resp_status(
            playing=True, bpm=140, pattern_index=2, channel_count=8
        )
        from fl_studio_mcp.protocol import decode_sysex

        cmd, payload = decode_sysex(raw)
        assert cmd == RESP_STATUS
        result = decode_resp_status(payload)
        assert result == {
            "playing": True,
            "bpm": 140,
            "pattern_index": 2,
            "channel_count": 8,
        }

    def test_resp_status_not_playing(self):
        raw = encode_resp_status(False, 120, 0, 0)
        from fl_studio_mcp.protocol import decode_sysex

        _, payload = decode_sysex(raw)
        result = decode_resp_status(payload)
        assert result["playing"] is False
        assert result["bpm"] == 120

    def test_resp_channels_roundtrip(self):
        names = ["Kick", "Snare", "Hi-Hat", "Bass", "Lead"]
        raw = encode_resp_channels(names)
        from fl_studio_mcp.protocol import decode_sysex

        cmd, payload = decode_sysex(raw)
        assert cmd == RESP_CHANNELS
        decoded = decode_resp_channels(payload)
        assert decoded == names

    def test_resp_channels_empty(self):
        raw = encode_resp_channels([])
        from fl_studio_mcp.protocol import decode_sysex

        _, payload = decode_sysex(raw)
        assert decode_resp_channels(payload) == []

    def test_resp_channels_long_name_truncated(self):
        long_name = "A" * 20
        raw = encode_resp_channels([long_name])
        from fl_studio_mcp.protocol import decode_sysex

        _, payload = decode_sysex(raw)
        decoded = decode_resp_channels(payload)
        assert len(decoded[0]) <= 14

    def test_resp_status_short_payload_raises(self):
        with pytest.raises(ValueError):
            decode_resp_status([1, 0])  # too short


# ---------------------------------------------------------------------------
# Bridge: queue injection and query timeout
# ---------------------------------------------------------------------------


class TestBridgeQuery:
    async def test_dry_run_query_returns_none(self, dry_bridge):
        result = await dry_bridge.query(
            encode_query_status(), RESP_STATUS, timeout_ms=200
        )
        assert result is None  # dry-run always returns None

    async def test_no_listener_property(self, dry_bridge):
        # In dry-run the listener is never started — verify bridge reports it
        assert dry_bridge.listening is False

    async def test_dry_run_connected_but_no_listener(self, dry_bridge):
        # query() returns None in dry-run regardless of listener state
        result = await dry_bridge.query(
            encode_query_status(), RESP_STATUS, timeout_ms=100
        )
        assert result is None

    async def test_injected_response_received(self, dry_bridge):
        """Inject a status response directly into the queue and verify retrieval."""
        # Build a valid status payload
        status_raw = encode_resp_status(True, 128, 1, 4)
        from fl_studio_mcp.protocol import decode_sysex

        _, payload = decode_sysex(status_raw)

        # Inject into queue — simulates FL Studio sending back
        _inject_response(dry_bridge, RESP_STATUS, payload)

        # Manually poll without sending (simulates post-send wait)
        import time

        deadline = time.monotonic() + 1.0
        found = None
        while time.monotonic() < deadline:
            try:
                item = dry_bridge._response_queue.get_nowait()
                if item["cmd"] == RESP_STATUS:
                    found = item
                    break
            except thread_queue.Empty:
                await asyncio.sleep(0.02)

        assert found is not None
        result = decode_resp_status(found["payload"])
        assert result["playing"] is True
        assert result["bpm"] == 128


# ---------------------------------------------------------------------------
# Tool: fl_get_status
# ---------------------------------------------------------------------------


class TestGetStatus:
    async def test_dry_run_returns_preview(self, dry_bridge):
        fn = _tool("status", "fl_get_status")
        result = parse(await fn(GetStatusInput()))
        assert result["dry_run"] is True
        assert result["source"] == "dry_run_preview"
        assert "bpm" in result
        assert "playing" in result

    async def test_not_connected_returns_error(self):
        fn = _tool("status", "fl_get_status")
        result = parse(await fn(GetStatusInput()))
        assert "error" in result


# ---------------------------------------------------------------------------
# Tool: fl_list_channels
# ---------------------------------------------------------------------------


class TestListChannels:
    async def test_dry_run_returns_mock(self, dry_bridge):
        fn = _tool("channels", "fl_list_channels")
        result = parse(await fn(ListChannelsInput()))
        assert result["dry_run"] is True
        assert isinstance(result["channels"], list)
        assert len(result["channels"]) > 0
        assert result["source"] == "dry_run_preview"

    async def test_not_connected_returns_error(self):
        fn = _tool("channels", "fl_list_channels")
        result = parse(await fn(ListChannelsInput()))
        assert "error" in result


# ---------------------------------------------------------------------------
# Tool: fl_set_channel_volume
# ---------------------------------------------------------------------------


class TestSetChannelVolume:
    async def test_dry_run(self, dry_bridge):
        fn = _tool("channels", "fl_set_channel_volume")
        result = parse(await fn(SetChannelVolumeInput(channel_index=0, volume=100)))
        assert result["dry_run"] is True
        assert result["channel_index"] == 0
        assert result["volume"] == 100

    async def test_sysex_bytes(self, dry_bridge):
        fn = _tool("channels", "fl_set_channel_volume")
        result = parse(await fn(SetChannelVolumeInput(channel_index=2, volume=80)))
        # F0 7D 08 02 50 F7  (0x50 = 80)
        assert "F0 7D 08 02 50 F7" in result["would_send_bytes"]

    async def test_not_connected_returns_error(self):
        fn = _tool("channels", "fl_set_channel_volume")
        result = parse(await fn(SetChannelVolumeInput(channel_index=0, volume=100)))
        assert "error" in result


# ---------------------------------------------------------------------------
# Tool: fl_create_pattern
# ---------------------------------------------------------------------------


class TestCreatePattern:
    async def test_dry_run(self, dry_bridge):
        fn = _tool("patterns", "fl_create_pattern")
        result = parse(await fn(CreatePatternInput()))
        assert result["dry_run"] is True
        assert result["command"] == "NEW_PATTERN"

    async def test_sysex_bytes(self, dry_bridge):
        fn = _tool("patterns", "fl_create_pattern")
        result = parse(await fn(CreatePatternInput()))
        assert "F0 7D 09 F7" in result["would_send_bytes"]

    async def test_not_connected_returns_error(self):
        fn = _tool("patterns", "fl_create_pattern")
        result = parse(await fn(CreatePatternInput()))
        assert "error" in result


# ---------------------------------------------------------------------------
# Tool: fl_select_pattern
# ---------------------------------------------------------------------------


class TestSelectPattern:
    async def test_dry_run(self, dry_bridge):
        fn = _tool("patterns", "fl_select_pattern")
        result = parse(await fn(SelectPatternInput(pattern_index=3)))
        assert result["dry_run"] is True
        assert result["pattern_index"] == 3
        assert result["command"] == "SELECT_PATTERN"

    async def test_sysex_bytes(self, dry_bridge):
        fn = _tool("patterns", "fl_select_pattern")
        result = parse(await fn(SelectPatternInput(pattern_index=7)))
        # F0 7D 0A 07 F7
        assert "F0 7D 0A 07 F7" in result["would_send_bytes"]

    async def test_not_connected_returns_error(self):
        fn = _tool("patterns", "fl_select_pattern")
        result = parse(await fn(SelectPatternInput(pattern_index=0)))
        assert "error" in result
