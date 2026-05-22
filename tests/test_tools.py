"""Integration tests for MCP tools — exercise tool handlers end-to-end in dry-run.

These tests call the tool functions directly (bypassing the MCP transport layer)
so no stdio / MCP client is needed. The dry-run fixture ensures no MIDI hardware
is required.
"""

import json

import pytest

from fl_studio_mcp.models import (
    AddChordProgressionInput,
    ChordQuality,
    ChordStep,
    ConnectInput,
    InsertNotesInput,
    Note,
    PlayStopInput,
    SaveProjectInput,
    SetTempoInput,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse(result: str) -> dict:
    """Parse JSON tool response."""
    return json.loads(result)


# ---------------------------------------------------------------------------
# Import the actual tool functions after patching the bridge
# ---------------------------------------------------------------------------

# We import tool modules lazily inside tests so the conftest reset_bridge
# fixture has already cleared the singleton before any tool code runs.


class TestListMidiPorts:
    async def test_returns_port_lists(self):
        from fl_studio_mcp.tools.midi_ports import register
        from mcp.server.fastmcp import FastMCP

        _mcp = FastMCP("test")
        register(_mcp)

        # Get the registered tool function
        tools = {t.name: t for t in _mcp._tool_manager.list_tools()}
        tool_fn = tools["fl_list_midi_ports"].fn

        result = parse(await tool_fn())
        assert "outputs" in result
        assert "inputs" in result
        assert "platform_hint" in result
        assert isinstance(result["outputs"], list)

    async def test_recommended_output_is_string_or_null(self):
        from fl_studio_mcp.tools.midi_ports import register
        from mcp.server.fastmcp import FastMCP

        _mcp = FastMCP("test")
        register(_mcp)
        tools = {t.name: t for t in _mcp._tool_manager.list_tools()}
        result = parse(await tools["fl_list_midi_ports"].fn())
        rec = result["recommended_output"]
        assert rec is None or isinstance(rec, str)


class TestConnect:
    async def test_dry_run_connect_succeeds(self):
        from fl_studio_mcp.tools.connection import register
        from mcp.server.fastmcp import FastMCP

        _mcp = FastMCP("test")
        register(_mcp)
        tools = {t.name: t for t in _mcp._tool_manager.list_tools()}
        fn = tools["fl_connect"].fn

        result = parse(await fn(ConnectInput(port_name="IAC Driver", dry_run=True)))
        assert result["connected"] is True
        assert result["dry_run"] is True

    async def test_bad_port_returns_error_json(self):
        from fl_studio_mcp.tools.connection import register
        from mcp.server.fastmcp import FastMCP

        _mcp = FastMCP("test")
        register(_mcp)
        tools = {t.name: t for t in _mcp._tool_manager.list_tools()}
        fn = tools["fl_connect"].fn

        result = parse(
            await fn(ConnectInput(port_name="__nonexistent__", dry_run=False))
        )
        # Should return a structured error, not raise
        assert "error" in result
        assert result["error"] == "MIDI_PORT_NOT_FOUND"


class TestTransportControl:
    async def test_play_dry_run(self, dry_bridge):
        from fl_studio_mcp.tools.transport_control import register
        from mcp.server.fastmcp import FastMCP

        _mcp = FastMCP("test")
        register(_mcp)
        tools = {t.name: t for t in _mcp._tool_manager.list_tools()}

        result = parse(await tools["fl_play_transport"].fn(PlayStopInput()))
        assert result["dry_run"] is True
        assert result["command"] == "MMC_PLAY"
        # MMC play is F0 7F 7F 06 02 F7
        assert "F0 7F 7F 06 02 F7" in result["would_send_bytes"]

    async def test_stop_dry_run(self, dry_bridge):
        from fl_studio_mcp.tools.transport_control import register
        from mcp.server.fastmcp import FastMCP

        _mcp = FastMCP("test")
        register(_mcp)
        tools = {t.name: t for t in _mcp._tool_manager.list_tools()}

        result = parse(await tools["fl_stop_transport"].fn(PlayStopInput()))
        assert result["dry_run"] is True
        assert result["command"] == "MMC_STOP"
        assert "F0 7F 7F 06 01 F7" in result["would_send_bytes"]

    async def test_not_connected_returns_error(self):
        from fl_studio_mcp.tools.transport_control import register
        from mcp.server.fastmcp import FastMCP

        _mcp = FastMCP("test")
        register(_mcp)
        tools = {t.name: t for t in _mcp._tool_manager.list_tools()}

        result = parse(await tools["fl_play_transport"].fn(PlayStopInput()))
        assert "error" in result
        assert result["error"] == "NOT_CONNECTED"


class TestSetTempo:
    async def test_set_tempo_dry_run(self, dry_bridge):
        from fl_studio_mcp.tools.tempo import register
        from mcp.server.fastmcp import FastMCP

        _mcp = FastMCP("test")
        register(_mcp)
        fn = {t.name: t for t in _mcp._tool_manager.list_tools()}["fl_set_tempo"].fn

        result = parse(await fn(SetTempoInput(bpm=128)))
        assert result["dry_run"] is True
        assert result["bpm"] == 128

    @pytest.mark.parametrize("bpm", [20, 60, 120, 140, 180, 999])
    async def test_various_bpms(self, dry_bridge, bpm):
        from fl_studio_mcp.tools.tempo import register
        from mcp.server.fastmcp import FastMCP

        _mcp = FastMCP("test")
        register(_mcp)
        fn = {t.name: t for t in _mcp._tool_manager.list_tools()}["fl_set_tempo"].fn

        result = parse(await fn(SetTempoInput(bpm=bpm)))
        assert result["bpm"] == bpm

    async def test_sysex_starts_with_f0_7d_03(self, dry_bridge):
        from fl_studio_mcp.tools.tempo import register
        from mcp.server.fastmcp import FastMCP

        _mcp = FastMCP("test")
        register(_mcp)
        fn = {t.name: t for t in _mcp._tool_manager.list_tools()}["fl_set_tempo"].fn

        result = parse(await fn(SetTempoInput(bpm=120)))
        assert result["would_send_bytes"].startswith("F0 7D 03")


class TestInsertNotes:
    def _tool(self):
        from fl_studio_mcp.tools.notes import register
        from mcp.server.fastmcp import FastMCP

        _mcp = FastMCP("test")
        register(_mcp)
        tools = {t.name: t for t in _mcp._tool_manager.list_tools()}
        return tools["fl_insert_notes"].fn, tools["fl_add_chord_progression"].fn

    async def test_single_note_dry_run(self, dry_bridge):
        insert_fn, _ = self._tool()
        result = parse(await insert_fn(InsertNotesInput(notes=[Note(pitch=60)])))
        assert result["dry_run"] is True
        assert result["note_count"] == 1
        assert result["notes_preview"][0]["pitch"] == 60

    async def test_multiple_notes(self, dry_bridge):
        insert_fn, _ = self._tool()
        notes = [
            Note(pitch=p, start_tick=i * 96) for i, p in enumerate([60, 62, 64, 65])
        ]
        result = parse(await insert_fn(InsertNotesInput(notes=notes)))
        assert result["note_count"] == 4

    async def test_preview_capped_at_8(self, dry_bridge):
        insert_fn, _ = self._tool()
        notes = [Note(pitch=60 + i) for i in range(20)]
        result = parse(await insert_fn(InsertNotesInput(notes=notes)))
        assert result["note_count"] == 20
        assert len(result["notes_preview"]) == 8

    async def test_sysex_is_f0_7d_04(self, dry_bridge):
        insert_fn, _ = self._tool()
        result = parse(await insert_fn(InsertNotesInput(notes=[Note(pitch=60)])))
        assert result["would_send_bytes"].startswith("F0 7D 04")

    async def test_chord_progression(self, dry_bridge):
        _, chord_fn = self._tool()
        chords = [
            ChordStep(
                root_pitch=60,
                quality=ChordQuality.MAJOR,
                start_tick=0,
                duration_ticks=384,
            ),
            ChordStep(
                root_pitch=67,
                quality=ChordQuality.MAJOR,
                start_tick=384,
                duration_ticks=384,
            ),
            ChordStep(
                root_pitch=69,
                quality=ChordQuality.MINOR,
                start_tick=768,
                duration_ticks=384,
            ),
            ChordStep(
                root_pitch=65,
                quality=ChordQuality.MAJOR,
                start_tick=1152,
                duration_ticks=384,
            ),
        ]
        result = parse(await chord_fn(AddChordProgressionInput(chords=chords)))
        assert result["chord_count"] == 4
        assert result["total_notes"] == 12  # 3 notes × 4 chords
        assert len(result["progression_preview"]) == 4

    async def test_dom7_chord_has_4_notes(self, dry_bridge):
        _, chord_fn = self._tool()
        chords = [ChordStep(root_pitch=60, quality=ChordQuality.DOM7)]
        result = parse(await chord_fn(AddChordProgressionInput(chords=chords)))
        assert result["total_notes"] == 4


class TestSaveProject:
    async def test_save_dry_run(self, dry_bridge):
        from fl_studio_mcp.tools.project import register
        from mcp.server.fastmcp import FastMCP

        _mcp = FastMCP("test")
        register(_mcp)
        fn = {t.name: t for t in _mcp._tool_manager.list_tools()}["fl_save_project"].fn

        result = parse(await fn(SaveProjectInput(confirm=True)))
        assert result["dry_run"] is True
        assert result["command"] == "SAVE"
        assert result["would_send_bytes"].startswith("F0 7D 05")

    async def test_save_requires_confirm(self, dry_bridge):
        from fl_studio_mcp.tools.project import register
        from mcp.server.fastmcp import FastMCP

        _mcp = FastMCP("test")
        register(_mcp)
        fn = {t.name: t for t in _mcp._tool_manager.list_tools()}["fl_save_project"].fn

        result = parse(await fn(SaveProjectInput(confirm=False)))
        assert "error" in result
        assert "explicitly set 'confirm': true" in result["error"]
