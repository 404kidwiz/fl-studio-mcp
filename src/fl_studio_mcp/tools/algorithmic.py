"""Tool: Algorithmic composition tools (Euclidean, Markov, Voice-leading)."""

import json
import re
from typing import Any
from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import FLMCPError, ErrorCode
from ..models import (
    InsertEuclideanDrumsInput,
    GenerateMarkovMelodyInput,
    InsertVoiceLedProgressionInput,
    note_name_to_pitch,
)
from ..theory import (
    generate_euclidean_rhythm,
    generate_markov_melody,
    optimize_voice_leading,
    generate_chord_pitches,
    rhythm_to_ticks,
    apply_composition_modifiers,
)
from ..protocol import encode_notes, CMD_NOTES


def _notes_to_dicts(notes) -> list[dict]:
    return [n.model_dump() for n in notes]


def parse_pitch_value(val: Any) -> int:
    """Helper to convert string/integer pitch to MIDI pitch int."""
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        if val.strip().lstrip("-").isdigit():
            return int(val)
        return note_name_to_pitch(val)
    return 60  # default fallback


def parse_chord_string(s: str) -> tuple[str, str]:
    """Helper to parse root note and quality from a chord string, e.g. C5-major."""
    s = s.strip()
    if "-" in s:
        parts = s.split("-", 1)
        return parts[0].strip(), parts[1].strip()

    # Fallback to regex split for note name vs quality, e.g. C5major, C5min, Am, C
    m = re.match(r"^([A-G][#b]?\d?)(.*)$", s, re.IGNORECASE)
    if m:
        root_str = m.group(1)
        quality_str = m.group(2).strip()
        if not quality_str:
            quality_str = "major"

        # Map common abbreviations to supported CHORDS qualities:
        q_lower = quality_str.lower()
        if q_lower in ("m", "min", "minor"):
            quality_str = "minor"
        elif q_lower in ("maj", "major"):
            quality_str = "major"
        elif q_lower in ("dim", "diminished"):
            quality_str = "diminished"
        elif q_lower in ("aug", "augmented"):
            quality_str = "augmented"
        elif q_lower in ("7", "dom7", "dominant7"):
            quality_str = "dominant7"
        elif q_lower in ("maj7", "major7"):
            quality_str = "major7"
        elif q_lower in ("min7", "minor7", "m7"):
            quality_str = "minor7"
        return root_str, quality_str

    return s, "major"


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="fl_insert_euclidean_drums",
        annotations={
            "title": "Insert Euclidean Drums",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_insert_euclidean_drums(params: InsertEuclideanDrumsInput) -> str:
        """Insert a step-sequencer style drum pattern using the Euclidean rhythm algorithm.

        Bjorklund/Bresenham algorithm distributes hits as evenly as possible across step length.
        """
        bridge = FLStudioBridge.get()

        try:
            try:
                mapping_dict = json.loads(params.mapping)
            except Exception:
                raise ValueError("mapping must be a valid JSON dictionary string.")

            step_ticks = rhythm_to_ticks(params.rhythm)
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        note_dicts = []
        for chan_str, value in mapping_dict.items():
            try:
                chan_idx = int(chan_str)
            except ValueError:
                return format_result(
                    FLMCPError(
                        ErrorCode.INVALID_PARAMS,
                        f"Mapping keys must be integer strings representing channel indices. Got: {chan_str!r}",
                    ).to_dict()
                )

            # Determine rhythm list for this channel
            if isinstance(value, list):
                # Direct override with custom sequence
                rhythm_pattern = value
            elif isinstance(value, dict):
                # Custom channel-level Euclidean override
                override_pitch = parse_pitch_value(value.get("pitch", 60))
                override_hits = value.get("hits", params.hits)
                override_steps = value.get("steps", params.steps)
                override_rotation = value.get("rotation", params.rotation)
                rhythm_pattern = generate_euclidean_rhythm(
                    override_hits, override_steps, override_rotation
                )
                pitch = override_pitch
            else:
                # Value is treated as a pitch and mapped to main Euclidean rhythm parameters
                pitch = parse_pitch_value(value)
                rhythm_pattern = generate_euclidean_rhythm(
                    params.hits, params.steps, params.rotation
                )

            for step_idx, hit in enumerate(rhythm_pattern):
                if hit:
                    # In case of custom sequence, we don't have default pitch in sequence, use 60
                    p = pitch if not isinstance(value, list) else 60
                    note_dicts.append(
                        {
                            "pitch": p,
                            "velocity": 100,
                            "start_tick": params.start_tick + step_idx * step_ticks,
                            "duration_ticks": step_ticks,
                            "channel": chan_idx,
                        }
                    )

        if not note_dicts:
            return format_result(
                FLMCPError(
                    ErrorCode.INVALID_PARAMS,
                    "No valid notes generated — make sure hits/steps and mapping are correct.",
                ).to_dict()
            )

        # Apply modifiers
        note_dicts = apply_composition_modifiers(
            note_dicts, params.velocity_curve, params.swing
        )

        max_chunk_size = 32
        note_chunks = [
            note_dicts[i : i + max_chunk_size]
            for i in range(0, len(note_dicts), max_chunk_size)
        ]

        last_result = None
        try:
            for chunk in note_chunks:
                sysex = encode_notes(chunk)
                last_result = await bridge.send_write(
                    sysex, CMD_NOTES, params.ack, params.timeout_ms
                )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        result = last_result or {}
        result["note_count"] = len(note_dicts)
        result["notes_preview"] = note_dicts[:8]
        result["chunks_sent"] = len(note_chunks)
        return format_result(result)

    @mcp.tool(
        name="fl_generate_markov_melody",
        annotations={
            "title": "Generate Markov Melody",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_generate_markov_melody(params: GenerateMarkovMelodyInput) -> str:
        """Generates a musical sequence using a scale-constrained Markov chain.

        Transitions notes based on common harmonic probabilities, keeping all pitches in key.
        """
        bridge = FLStudioBridge.get()

        try:
            step_ticks = rhythm_to_ticks(params.rate)
            # Total beats * 96 ticks = total ticks. Steps is total ticks divided by step subdivision ticks.
            total_ticks = int(params.length_beats * 96)
            total_steps = max(1, int(round(total_ticks / step_ticks)))
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        try:
            pitches = generate_markov_melody(
                root=params.root,
                scale=params.scale,
                length=total_steps,
            )
        except ValueError as exc:
            return format_result(
                FLMCPError(
                    ErrorCode.INVALID_PARAMS,
                    f"Failed to generate Markov pitches: {exc}",
                ).to_dict()
            )

        note_dicts = []
        for idx, pitch in enumerate(pitches):
            note_dicts.append(
                {
                    "pitch": pitch,
                    "velocity": 100,
                    "start_tick": params.start_tick + idx * step_ticks,
                    "duration_ticks": step_ticks,
                    "channel": params.channel_index,
                }
            )

        # Apply modifiers
        note_dicts = apply_composition_modifiers(
            note_dicts, params.velocity_curve, params.swing
        )

        max_chunk_size = 32
        note_chunks = [
            note_dicts[i : i + max_chunk_size]
            for i in range(0, len(note_dicts), max_chunk_size)
        ]

        last_result = None
        try:
            for chunk in note_chunks:
                sysex = encode_notes(chunk)
                last_result = await bridge.send_write(
                    sysex, CMD_NOTES, params.ack, params.timeout_ms
                )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        result = last_result or {}
        result["note_count"] = len(note_dicts)
        result["notes_preview"] = note_dicts[:8]
        result["chunks_sent"] = len(note_chunks)
        return format_result(result)

    @mcp.tool(
        name="fl_insert_voice_led_progression",
        annotations={
            "title": "Insert Voice-Led Chord Progression",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_insert_voice_led_progression(
        params: InsertVoiceLedProgressionInput,
    ) -> str:
        """Insert a chord progression where octaves/inversions are optimized to minimize voice jumping.

        Uses minimum absolute distance transposition solver to smooth transitions.
        """
        bridge = FLStudioBridge.get()

        if not params.progression.strip():
            return format_result(
                FLMCPError(
                    ErrorCode.INVALID_PARAMS, "progression string cannot be empty."
                ).to_dict()
            )

        chord_strings = [c.strip() for c in params.progression.split(",") if c.strip()]
        chords_pitches = []

        try:
            step_ticks = rhythm_to_ticks(params.rate)
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        for chord_str in chord_strings:
            try:
                root_str, quality_str = parse_chord_string(chord_str)
                pitches = generate_chord_pitches(root_str, quality_str)
                chords_pitches.append(pitches)
            except Exception as exc:
                return format_result(
                    FLMCPError(
                        ErrorCode.INVALID_PARAMS,
                        f"Failed parsing chord '{chord_str}': {exc}",
                    ).to_dict()
                )

        try:
            optimized_chords = optimize_voice_leading(chords_pitches)
        except Exception as exc:
            return format_result(
                FLMCPError(
                    ErrorCode.UNKNOWN, f"Voice-leading optimization failed: {exc}"
                ).to_dict()
            )

        note_dicts = []
        for c_idx, chord in enumerate(optimized_chords):
            start_offset = params.start_tick + c_idx * step_ticks
            for pitch in chord:
                note_dicts.append(
                    {
                        "pitch": pitch,
                        "velocity": 100,
                        "start_tick": start_offset,
                        "duration_ticks": step_ticks,
                        "channel": params.channel_index,
                    }
                )

        # Apply modifiers
        note_dicts = apply_composition_modifiers(
            note_dicts, params.velocity_curve, params.swing
        )

        max_chunk_size = 32
        note_chunks = [
            note_dicts[i : i + max_chunk_size]
            for i in range(0, len(note_dicts), max_chunk_size)
        ]

        last_result = None
        try:
            for chunk in note_chunks:
                sysex = encode_notes(chunk)
                last_result = await bridge.send_write(
                    sysex, CMD_NOTES, params.ack, params.timeout_ms
                )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        result = last_result or {}
        result["chord_count"] = len(chord_strings)
        result["total_notes"] = len(note_dicts)
        result["chunks_sent"] = len(note_chunks)
        result["notes_preview"] = note_dicts[:8]
        return format_result(result)
