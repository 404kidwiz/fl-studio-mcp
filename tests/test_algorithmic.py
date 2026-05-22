import json
import pytest
from mcp.server.fastmcp import FastMCP

from fl_studio_mcp.models import (
    InsertEuclideanDrumsInput,
    GenerateMarkovMelodyInput,
    InsertVoiceLedProgressionInput,
)
from fl_studio_mcp.theory import (
    generate_euclidean_rhythm,
    generate_markov_melody,
    optimize_voice_leading,
)
from fl_studio_mcp.tools.algorithmic import (
    register as register_algorithmic,
    parse_chord_string,
)


def parse(result: str) -> dict:
    return json.loads(result)


def _tool(tool_name: str):
    mcp = FastMCP("test")
    register_algorithmic(mcp)
    tools = getattr(mcp, "_tools", None) or getattr(mcp._tool_manager, "_tools", {})
    if hasattr(mcp, "_tool_manager"):
        # standard FastMCP
        return {t.name: t for t in mcp._tool_manager.list_tools()}[tool_name].fn
    else:
        return tools[tool_name]


# ===========================================================================
# Math & Logic Unit Tests
# ===========================================================================


def test_euclidean_rhythm_distribution():
    # 4 hits in 8 steps -> [1, 0, 1, 0, 1, 0, 1, 0]
    pattern = generate_euclidean_rhythm(hits=4, steps=8)
    assert pattern == [1, 0, 1, 0, 1, 0, 1, 0]

    # 5 hits in 16 steps
    pattern_5_16 = generate_euclidean_rhythm(hits=5, steps=16)
    assert len(pattern_5_16) == 16
    assert sum(pattern_5_16) == 5

    # 0 hits in 8 steps
    assert generate_euclidean_rhythm(hits=0, steps=8) == [0] * 8

    # Steps <= 0
    assert generate_euclidean_rhythm(hits=2, steps=0) == []

    # Rotation
    pattern_rot = generate_euclidean_rhythm(hits=4, steps=8, rotation=1)
    # original [1, 0, 1, 0, 1, 0, 1, 0] rotated right by 1 -> [0, 1, 0, 1, 0, 1, 0, 1]
    assert pattern_rot == [0, 1, 0, 1, 0, 1, 0, 1]


def test_markov_melody_generation():
    # Minor scale Markov melody starting at default (C5)
    melody = generate_markov_melody(root="C5", scale="minor", length=16)
    assert len(melody) == 16
    # All notes in melody must be in minor scale of C5
    # C5 is pitch 60. minor intervals: 0, 2, 3, 5, 7, 8, 10, 12, 14, 15, 17, 19, 20, 22
    scale_pitches = [60, 62, 63, 65, 67, 68, 70, 72, 74, 75, 77, 79, 80, 82, 84]
    for pitch in melody:
        assert pitch in scale_pitches


def test_voice_leading_optimization():
    # Simple I - V progression in C major (C4 = 60, G4 = 67)
    # C major: C4 (60), E4 (64), G4 (67)
    # G major: G4 (67), B4 (71), D5 (74)
    c_maj = [60, 64, 67]
    g_maj = [67, 71, 74]

    optimized = optimize_voice_leading([c_maj, g_maj])
    assert len(optimized) == 2
    assert optimized[0] == c_maj  # Root stays unchanged
    # G major optimized should have notes transposed down an octave to avoid jumps:
    # G4(67) stays 67, B4(71) stays 71, D5(74) becomes D4(62)
    # Let's see: sorted optimized G major should be [62, 67, 71]
    assert optimized[1] == [62, 67, 71]


def test_parse_chord_string():
    assert parse_chord_string("C5-major") == ("C5", "major")
    assert parse_chord_string("F#4-minor") == ("F#4", "minor")
    assert parse_chord_string("Am") == ("A", "minor")
    assert parse_chord_string("C#5maj7") == ("C#5", "major7")
    assert parse_chord_string("C") == ("C", "major")


# ===========================================================================
# FastMCP Tool Integration Tests (Dry-Run Mode)
# ===========================================================================


@pytest.mark.asyncio
async def test_fl_insert_euclidean_drums_tool(dry_bridge):
    fn = _tool("fl_insert_euclidean_drums")

    # 1. Standard pitch mapping
    params = InsertEuclideanDrumsInput(
        mapping='{"0": "C3", "1": 38}',
        rhythm="eighth",
        hits=4,
        steps=8,
        start_tick=0,
    )
    result = parse(await fn(params))
    assert result["dry_run"] is True
    # 4 hits per channel, 2 channels -> total 8 notes
    assert result["note_count"] == 8
    assert len(result["notes_preview"]) == 8

    # 2. Custom dict mapping (with channel overrides)
    params_custom = InsertEuclideanDrumsInput(
        mapping='{"0": {"pitch": "C3", "hits": 2, "steps": 8}, "1": [1, 0, 1, 0]}',
        rhythm="quarter",
    )
    result_custom = parse(await fn(params_custom))
    assert result_custom["dry_run"] is True
    # Channel 0: 2 hits. Channel 1: [1,0,1,0] list override -> 2 hits. Total 4 notes.
    assert result_custom["note_count"] == 4


@pytest.mark.asyncio
async def test_fl_generate_markov_melody_tool(dry_bridge):
    fn = _tool("fl_generate_markov_melody")
    params = GenerateMarkovMelodyInput(
        root="F#4",
        scale="dorian",
        length_beats=4.0,
        rate="eighth",
        channel_index=1,
        start_tick=96,
        velocity_curve="crescendo",
    )
    result = parse(await fn(params))
    assert result["dry_run"] is True
    # 4 beats * 96 PPQ = 384 ticks. / 48 ticks (eighth note) = 8 notes.
    assert result["note_count"] == 8
    assert len(result["notes_preview"]) == 8


@pytest.mark.asyncio
async def test_fl_insert_voice_led_progression_tool(dry_bridge):
    fn = _tool("fl_insert_voice_led_progression")
    params = InsertVoiceLedProgressionInput(
        progression="C5-major, G5-major, A4-minor, F4-major",
        rate="half",
        channel_index=0,
        start_tick=0,
    )
    result = parse(await fn(params))
    assert result["dry_run"] is True
    # 4 chords * 3 notes each = 12 notes total
    assert result["chord_count"] == 4
    assert result["total_notes"] == 12
    assert len(result["notes_preview"]) == 8  # truncated preview
