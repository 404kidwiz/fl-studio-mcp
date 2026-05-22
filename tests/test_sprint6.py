"""Tests for Sprint 6: Composition and Music Theory helpers.

Includes music theory generator unit tests, composition tools tests, and modifiers.
"""

import json
import pytest
from fl_studio_mcp.bridge import FLStudioBridge
from fl_studio_mcp.models import (
    InsertScaleInput,
    InsertArpeggioInput,
    InsertDrumPatternInput,
    InsertNotesInput,
    Note,
)
from fl_studio_mcp.theory import (
    rhythm_to_ticks,
    generate_scale_notes,
    generate_chord_pitches,
    apply_composition_modifiers,
)


def parse(result: str) -> dict:
    return json.loads(result)


def _tool(module_name: str, tool_name: str):
    """Import the tool module and return its registered function."""
    from mcp.server.fastmcp import FastMCP
    if module_name == "composition":
        from fl_studio_mcp.tools import composition as mod
    else:
        from fl_studio_mcp.tools import notes as mod
    _mcp = FastMCP("test")
    mod.register(_mcp)
    return {t.name: t for t in _mcp._tool_manager.list_tools()}[tool_name].fn


# ---------------------------------------------------------------------------
# 1. Music Theory & Modifier Unit Tests
# ---------------------------------------------------------------------------

class TestSprint6Theory:
    def test_rhythm_to_ticks(self):
        assert rhythm_to_ticks("whole") == 384
        assert rhythm_to_ticks("quarter") == 96
        assert rhythm_to_ticks("sixteenth") == 24
        assert rhythm_to_ticks("48") == 48
        with pytest.raises(ValueError):
            rhythm_to_ticks("invalid_rhythm")

    def test_generate_scale_notes(self):
        # C5 major = C5, D5, E5, F5, G5, A5, B5, C6 (pitches 72, 74, 76, 77, 79, 81, 83, 84)
        pitches = generate_scale_notes("C5", "major", octaves=1)
        assert pitches == [72, 74, 76, 77, 79, 81, 83, 84]

        # A4 minor = A4, B4, C5, D5, E5, F5, G5, A5 (69, 71, 72, 74, 76, 77, 79, 81)
        pitches_minor = generate_scale_notes("A4", "minor", octaves=1)
        assert pitches_minor == [69, 71, 72, 74, 76, 77, 79, 81]

    def test_generate_chord_pitches(self):
        # C5 major triad = C5, E5, G5 (72, 76, 79)
        pitches = generate_chord_pitches("C5", "major", octaves=1)
        assert pitches == [72, 76, 79]

        # A4 minor7 = A4, C5, E5, G5 (69, 72, 76, 79)
        pitches_m7 = generate_chord_pitches("A4", "minor7", octaves=1)
        assert pitches_m7 == [69, 72, 76, 79]

    def test_apply_composition_modifiers_velocity(self):
        notes = [{"pitch": 60, "velocity": 100, "start_tick": 0}]
        # humanize
        res_human = apply_composition_modifiers(notes, "humanize", 0.0)
        assert 1 <= res_human[0]["velocity"] <= 127

        # crescendo
        notes_multi = [
            {"pitch": 60, "velocity": 100, "start_tick": 0},
            {"pitch": 62, "velocity": 100, "start_tick": 24},
            {"pitch": 64, "velocity": 100, "start_tick": 48},
        ]
        res_cres = apply_composition_modifiers(notes_multi, "crescendo", 0.0)
        assert res_cres[0]["velocity"] == 50
        assert res_cres[-1]["velocity"] == 127

        # decrescendo
        res_decres = apply_composition_modifiers(notes_multi, "decrescendo", 0.0)
        assert res_decres[0]["velocity"] == 127
        assert res_decres[-1]["velocity"] == 50

    def test_apply_composition_modifiers_swing(self):
        # Tick 24 is Step 1 (offbeat 16th step), which should be shifted by swing
        # Swing = 0.5 -> 0.5 * 12 = 6 ticks shift -> 24 + 6 = 30
        notes = [
            {"pitch": 60, "velocity": 100, "start_tick": 0},  # Step 0 (no shift)
            {"pitch": 62, "velocity": 100, "start_tick": 24}, # Step 1 (even step index in 16th steps, shifts)
            {"pitch": 64, "velocity": 100, "start_tick": 48}, # Step 2 (no shift)
            {"pitch": 66, "velocity": 100, "start_tick": 72}, # Step 3 (shifts)
        ]
        res = apply_composition_modifiers(notes, "none", swing=0.5)
        assert res[0]["start_tick"] == 0
        assert res[1]["start_tick"] == 30
        assert res[2]["start_tick"] == 48
        assert res[3]["start_tick"] == 78


# ---------------------------------------------------------------------------
# 2. Composition MCP Tools Tests
# ---------------------------------------------------------------------------

class TestSprint6Tools:
    async def test_fl_insert_scale_dry_run(self, dry_bridge):
        fn = _tool("composition", "fl_insert_scale")
        res = parse(await fn(InsertScaleInput(
            root="C5",
            scale="major",
            octaves=1,
            rhythm="quarter",
            channel_index=2,
            start_tick=0,
            velocity_curve="crescendo",
            swing=0.0,
        )))

        assert res["dry_run"] is True
        assert res["note_count"] == 8
        assert len(res["notes_preview"]) == 8
        assert res["notes_preview"][0]["pitch"] == 72
        assert res["notes_preview"][0]["velocity"] == 50
        assert res["notes_preview"][-1]["pitch"] == 84
        assert res["notes_preview"][-1]["velocity"] == 127

    async def test_fl_insert_arpeggio_dry_run_chord(self, dry_bridge):
        fn = _tool("composition", "fl_insert_arpeggio")
        res = parse(await fn(InsertArpeggioInput(
            root="C5",
            chord_type="major",
            style="up",
            rate="sixteenth",
            octaves=1,
            channel_index=0,
            start_tick=0,
            duration_beats=4.0,
            velocity_curve="none",
            swing=0.0,
        )))

        # 4 beats * 96 PPQ = 384 ticks
        # sixteenth = 24 ticks -> 384 / 24 = 16 notes generated
        assert res["dry_run"] is True
        assert res["note_count"] == 16
        # C5 major triad = 72, 76, 79. Up style repeats: 72, 76, 79, 72, 76, 79...
        assert res["notes_preview"][0]["pitch"] == 72
        assert res["notes_preview"][1]["pitch"] == 76
        assert res["notes_preview"][2]["pitch"] == 79
        assert res["notes_preview"][3]["pitch"] == 72

    async def test_fl_insert_arpeggio_dry_run_list(self, dry_bridge):
        fn = _tool("composition", "fl_insert_arpeggio")
        res = parse(await fn(InsertArpeggioInput(
            root="C5, E5, G5, B5",
            style="down",
            rate="eighth",
            octaves=2,
            channel_index=1,
            start_tick=0,
            duration_beats=2.0,
            velocity_curve="none",
            swing=0.0,
        )))

        # 2 beats * 96 PPQ = 192 ticks
        # eighth = 48 ticks -> 192 / 48 = 4 notes generated
        assert res["dry_run"] is True
        assert res["note_count"] == 4
        # Sorted reverse: C5(72), E5(76), G5(79), B5(83) + octave 2: C6(84), E6(88), G6(91), B6(95)
        # pitches to order: [72, 76, 79, 83, 84, 88, 91, 95]
        # ordered descending: 95, 91, 88, 84...
        assert res["notes_preview"][0]["pitch"] == 95
        assert res["notes_preview"][1]["pitch"] == 91
        assert res["notes_preview"][2]["pitch"] == 88

    async def test_fl_insert_drum_pattern_dry_run(self, dry_bridge):
        fn = _tool("composition", "fl_insert_drum_pattern")
        mapping = '{"0": [1, 0, 0, 1], "1": [0, 1, 0, 0]}'
        res = parse(await fn(InsertDrumPatternInput(
            mapping=mapping,
            rhythm="sixteenth",
            start_tick=0,
            velocity_curve="none",
            swing=0.0,
        )))

        assert res["dry_run"] is True
        # hits: 2 hits on channel 0, 1 hit on channel 1 -> 3 notes
        assert res["note_count"] == 3
        # Notes sorted in order of sequence steps
        assert res["notes_preview"][0]["channel"] == 0
        assert res["notes_preview"][0]["start_tick"] == 0
        assert res["notes_preview"][1]["channel"] == 1
        assert res["notes_preview"][1]["start_tick"] == 24
        assert res["notes_preview"][2]["channel"] == 0
        assert res["notes_preview"][2]["start_tick"] == 72

    async def test_fl_insert_drum_pattern_invalid_mapping(self, dry_bridge):
        fn = _tool("composition", "fl_insert_drum_pattern")
        res = parse(await fn(InsertDrumPatternInput(
            mapping="{invalid_json}",
            rhythm="sixteenth",
        )))
        assert "error" in res
        assert res["error"] == "INVALID_PARAMS"


# ---------------------------------------------------------------------------
# 3. Notes Modifiers Integration Tests
# ---------------------------------------------------------------------------

class TestSprint6NotesModifiers:
    async def test_fl_insert_notes_with_swing_and_curve(self, dry_bridge):
        fn = _tool("notes", "fl_insert_notes")
        notes = [
            Note(pitch=60, start_tick=0),
            Note(pitch=62, start_tick=24),
            Note(pitch=64, start_tick=48),
        ]
        res = parse(await fn(InsertNotesInput(
            notes=notes,
            velocity_curve="crescendo",
            swing=1.0,  # 1.0 * 12 = 12 ticks shift on step 1 (24 ticks)
        )))

        assert res["dry_run"] is True
        assert res["note_count"] == 3
        assert res["notes_preview"][0]["velocity"] == 50
        assert res["notes_preview"][-1]["velocity"] == 127
        assert res["notes_preview"][0]["start_tick"] == 0
        assert res["notes_preview"][1]["start_tick"] == 36  # 24 + 12 = 36
        assert res["notes_preview"][2]["start_tick"] == 48
