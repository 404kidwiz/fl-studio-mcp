"""Tests for fl_panic, fl_mute_channel, fl_solo_channel.

All tests run in dry-run mode — no MIDI hardware required.
"""

import json

import pytest

from fl_studio_mcp.bridge import FLStudioBridge
from fl_studio_mcp.models import MuteChannelInput, PanicInput, SoloChannelInput
from fl_studio_mcp.protocol import (
    encode_mute_channel,
    encode_solo_channel,
    panic_messages,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse(result: str) -> dict:
    return json.loads(result)


def _tool(tool_name: str):
    import importlib
    from mcp.server.fastmcp import FastMCP
    mod = importlib.import_module("fl_studio_mcp.tools.mixing")
    _mcp = FastMCP("test")
    mod.register(_mcp)
    return {t.name: t for t in _mcp._tool_manager.list_tools()}[tool_name].fn


# ---------------------------------------------------------------------------
# Protocol: panic_messages
# ---------------------------------------------------------------------------

class TestPanicMessages:
    def test_returns_48_messages(self):
        msgs = panic_messages()
        assert len(msgs) == 48  # 3 CC × 16 channels

    def test_all_channels_covered(self):
        msgs = panic_messages()
        # Extract status bytes
        channels_seen = set()
        for m in msgs:
            channels_seen.add(m[0] & 0x0F)
        assert channels_seen == set(range(16))

    def test_cc_numbers(self):
        msgs = panic_messages()
        cc_numbers = {m[1] for m in msgs}
        assert cc_numbers == {120, 121, 123}  # All Sound Off, Reset, All Notes Off

    def test_all_values_zero(self):
        msgs = panic_messages()
        for m in msgs:
            assert m[2] == 0  # all CC values are 0


# ---------------------------------------------------------------------------
# Protocol: encode_mute_channel / encode_solo_channel
# ---------------------------------------------------------------------------

class TestMixingProtocol:
    def test_mute_channel_cmd(self):
        raw = encode_mute_channel(3, True)
        assert raw[2] == 0x0D  # CMD_MUTE_CHANNEL
        assert raw[3] == 3
        assert raw[4] == 1  # muted=True → 1

    def test_unmute_channel(self):
        raw = encode_mute_channel(5, False)
        assert raw[4] == 0  # muted=False → 0

    def test_mute_channel_bounds(self):
        with pytest.raises(ValueError):
            encode_mute_channel(128, True)

    def test_solo_channel_cmd(self):
        raw = encode_solo_channel(7, True)
        assert raw[2] == 0x0E  # CMD_SOLO_CHANNEL
        assert raw[3] == 7
        assert raw[4] == 1

    def test_unsolo_channel(self):
        raw = encode_solo_channel(0, False)
        assert raw[4] == 0

    def test_solo_channel_bounds(self):
        with pytest.raises(ValueError):
            encode_solo_channel(128, False)

    def test_sysex_framing(self):
        raw = encode_mute_channel(0, True)
        assert raw[0] == 0xF0
        assert raw[-1] == 0xF7
        assert raw[1] == 0x7D  # manufacturer ID


# ---------------------------------------------------------------------------
# Tool: fl_panic
# ---------------------------------------------------------------------------

class TestFlPanic:
    async def test_dry_run(self, dry_bridge):
        fn = _tool("fl_panic")
        result = parse(await fn(PanicInput()))
        assert result["dry_run"] is True
        assert result["messages_sent"] == 48
        assert result["channels_cleared"] == 16

    async def test_not_connected_returns_error(self):
        fn = _tool("fl_panic")
        result = parse(await fn(PanicInput()))
        assert "error" in result

    async def test_messages_sent_count(self, dry_bridge):
        fn = _tool("fl_panic")
        result = parse(await fn(PanicInput()))
        # 3 CCs × 16 channels = 48
        assert result["messages_sent"] == 48

    async def test_channels_cleared_always_16(self, dry_bridge):
        fn = _tool("fl_panic")
        result = parse(await fn(PanicInput()))
        assert result["channels_cleared"] == 16


# ---------------------------------------------------------------------------
# Tool: fl_mute_channel
# ---------------------------------------------------------------------------

class TestFlMuteChannel:
    async def test_dry_run_mute(self, dry_bridge):
        fn = _tool("fl_mute_channel")
        result = parse(await fn(MuteChannelInput(channel_index=0, muted=True)))
        assert result["dry_run"] is True
        assert result["channel_index"] == 0
        assert result["muted"] is True

    async def test_dry_run_unmute(self, dry_bridge):
        fn = _tool("fl_mute_channel")
        result = parse(await fn(MuteChannelInput(channel_index=2, muted=False)))
        assert result["muted"] is False
        assert result["channel_index"] == 2

    async def test_sysex_bytes(self, dry_bridge):
        fn = _tool("fl_mute_channel")
        result = parse(await fn(MuteChannelInput(channel_index=4, muted=True)))
        # F0 7D 0D 04 01 F7
        assert "F0 7D 0D 04 01 F7" in result["would_send_bytes"]

    async def test_unmute_bytes(self, dry_bridge):
        fn = _tool("fl_mute_channel")
        result = parse(await fn(MuteChannelInput(channel_index=1, muted=False)))
        # F0 7D 0D 01 00 F7
        assert "F0 7D 0D 01 00 F7" in result["would_send_bytes"]

    async def test_not_connected_returns_error(self):
        fn = _tool("fl_mute_channel")
        result = parse(await fn(MuteChannelInput(channel_index=0)))
        assert "error" in result

    async def test_channel_index_preserved(self, dry_bridge):
        fn = _tool("fl_mute_channel")
        result = parse(await fn(MuteChannelInput(channel_index=15, muted=True)))
        assert result["channel_index"] == 15


# ---------------------------------------------------------------------------
# Tool: fl_solo_channel
# ---------------------------------------------------------------------------

class TestFlSoloChannel:
    async def test_dry_run_solo(self, dry_bridge):
        fn = _tool("fl_solo_channel")
        result = parse(await fn(SoloChannelInput(channel_index=0, soloed=True)))
        assert result["dry_run"] is True
        assert result["channel_index"] == 0
        assert result["soloed"] is True

    async def test_dry_run_unsolo(self, dry_bridge):
        fn = _tool("fl_solo_channel")
        result = parse(await fn(SoloChannelInput(channel_index=3, soloed=False)))
        assert result["soloed"] is False

    async def test_sysex_bytes(self, dry_bridge):
        fn = _tool("fl_solo_channel")
        result = parse(await fn(SoloChannelInput(channel_index=2, soloed=True)))
        # F0 7D 0E 02 01 F7
        assert "F0 7D 0E 02 01 F7" in result["would_send_bytes"]

    async def test_not_connected_returns_error(self):
        fn = _tool("fl_solo_channel")
        result = parse(await fn(SoloChannelInput(channel_index=0)))
        assert "error" in result

    async def test_channel_index_preserved(self, dry_bridge):
        fn = _tool("fl_solo_channel")
        result = parse(await fn(SoloChannelInput(channel_index=10, soloed=True)))
        assert result["channel_index"] == 10
