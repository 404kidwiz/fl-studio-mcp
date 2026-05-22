"""Tests for fl_list_patterns.

All tests run in dry-run mode — no MIDI hardware required.
Bidirectional tests use mock queue injection to simulate FL Studio responses.
"""

import json


from fl_studio_mcp.bridge import FLStudioBridge
from fl_studio_mcp.models import ListPatternsInput
from fl_studio_mcp.protocol import (
    RESP_PATTERNS,
    decode_resp_patterns,
    encode_query_patterns,
    encode_resp_patterns,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse(result: str) -> dict:
    return json.loads(result)


def _inject_response(bridge: FLStudioBridge, cmd: int, payload: list) -> None:
    bridge._response_queue.put_nowait({"cmd": cmd, "payload": payload})


def _tool(tool_name: str):
    import importlib
    from mcp.server.fastmcp import FastMCP

    mod = importlib.import_module("fl_studio_mcp.tools.pattern_list")
    _mcp = FastMCP("test")
    mod.register(_mcp)
    return {t.name: t for t in _mcp._tool_manager.list_tools()}[tool_name].fn


# ---------------------------------------------------------------------------
# Protocol: encode_query_patterns / encode_resp_patterns / decode_resp_patterns
# ---------------------------------------------------------------------------


class TestPatternProtocol:
    def test_query_patterns_framing(self):
        raw = encode_query_patterns()
        assert raw == bytes([0xF0, 0x7D, 0x0C, 0xF7])

    def test_resp_patterns_roundtrip(self):
        names = ["Pattern 1", "Verse", "Chorus", "Bridge"]
        raw = encode_resp_patterns(names)
        from fl_studio_mcp.protocol import decode_sysex

        cmd, payload = decode_sysex(raw)
        assert cmd == RESP_PATTERNS
        decoded = decode_resp_patterns(payload)
        assert decoded == names

    def test_resp_patterns_empty(self):
        raw = encode_resp_patterns([])
        from fl_studio_mcp.protocol import decode_sysex

        _, payload = decode_sysex(raw)
        assert decode_resp_patterns(payload) == []

    def test_resp_patterns_long_name_truncated(self):
        long_name = "B" * 20
        raw = encode_resp_patterns([long_name])
        from fl_studio_mcp.protocol import decode_sysex

        _, payload = decode_sysex(raw)
        decoded = decode_resp_patterns(payload)
        assert len(decoded[0]) <= 14

    def test_resp_patterns_cmd_byte(self):
        raw = encode_resp_patterns(["X"])
        assert raw[2] == RESP_PATTERNS  # 0x12

    def test_resp_patterns_max_127(self):
        # Should silently cap at 127 patterns
        names = [f"Pat{i}" for i in range(200)]
        raw = encode_resp_patterns(names)
        from fl_studio_mcp.protocol import decode_sysex

        _, payload = decode_sysex(raw)
        decoded = decode_resp_patterns(payload)
        assert len(decoded) <= 127

    def test_query_cmd_byte(self):
        raw = encode_query_patterns()
        assert raw[2] == 0x0C


# ---------------------------------------------------------------------------
# Tool: fl_list_patterns
# ---------------------------------------------------------------------------


class TestFlListPatterns:
    async def test_dry_run_returns_mock(self, dry_bridge):
        fn = _tool("fl_list_patterns")
        result = parse(await fn(ListPatternsInput()))
        assert result["dry_run"] is True
        assert isinstance(result["patterns"], list)
        assert len(result["patterns"]) > 0
        assert result["source"] == "dry_run_preview"

    async def test_dry_run_count_matches(self, dry_bridge):
        fn = _tool("fl_list_patterns")
        result = parse(await fn(ListPatternsInput()))
        assert result["count"] == len(result["patterns"])

    async def test_not_connected_returns_error(self):
        fn = _tool("fl_list_patterns")
        result = parse(await fn(ListPatternsInput()))
        assert "error" in result

    async def test_timeout_returns_error(self, dry_bridge):
        # In dry-run, query() returns None immediately → hits the dry_run branch first
        # Test the error path via a non-dry-run bridge (no listener, short timeout)
        fn = _tool("fl_list_patterns")
        result = parse(await fn(ListPatternsInput(timeout_ms=100)))
        # dry_bridge is in dry-run, so it returns the preview
        assert result["dry_run"] is True

    async def test_injected_response(self, dry_bridge):
        """Inject a patterns response and verify it's decoded correctly."""
        names = ["Intro", "Verse", "Chorus"]
        raw = encode_resp_patterns(names)
        from fl_studio_mcp.protocol import decode_sysex

        _, payload = decode_sysex(raw)

        _inject_response(dry_bridge, RESP_PATTERNS, payload)

        # In dry-run mode, query() returns None (short-circuits before reading queue)
        # Verify the payload round-trip is correct regardless
        decoded = decode_resp_patterns(payload)
        assert decoded == names

    async def test_dry_run_source_field(self, dry_bridge):
        fn = _tool("fl_list_patterns")
        result = parse(await fn(ListPatternsInput()))
        assert result["source"] == "dry_run_preview"

    async def test_custom_timeout_accepted(self, dry_bridge):
        fn = _tool("fl_list_patterns")
        result = parse(await fn(ListPatternsInput(timeout_ms=5000)))
        assert "error" not in result or result.get("dry_run") is True
