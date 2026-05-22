"""Tools: fl_insert_scale, fl_insert_arpeggio, fl_insert_drum_pattern."""

import json
import random
from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import FLMCPError
from ..models import (
    InsertScaleInput,
    InsertArpeggioInput,
    InsertDrumPatternInput,
    note_name_to_pitch,
)
from ..protocol import encode_notes
from ..theory import (
    generate_scale_notes,
    generate_chord_pitches,
    rhythm_to_ticks,
    apply_composition_modifiers,
)


def _notes_to_dicts(notes) -> list[dict]:
    return notes


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="fl_insert_scale",
        annotations={
            "title": "Insert Scale Pattern",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_insert_scale(params: InsertScaleInput) -> str:
        """Generate and insert a sequence of scale notes.

        Args:
            params (InsertScaleInput):
                - root (str): e.g. "C5", "F#4", "Bb3"
                - scale (str): e.g. "major", "minor", "pentatonic_major", "harmonic_minor"
                - octaves (int 1-8): span of octaves; defaults to 1
                - rhythm (str): e.g. "eighth", "sixteenth", "quarter"
                - channel_index (int 0-127): target MIDI channel/index; defaults to 0
                - start_tick (int): start tick offset; defaults to 0
                - velocity_curve (str): "none", "humanize", "crescendo", "decrescendo"
                - swing (float 0.0-1.0): swing factor; defaults to 0.0

        Returns:
            str: JSON result
        """
        bridge = FLStudioBridge.get()

        try:
            pitches = generate_scale_notes(params.root, params.scale, params.octaves)
            rhythm_ticks = rhythm_to_ticks(params.rhythm)
        except ValueError as exc:
            from ..errors import ErrorCode
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        note_dicts = []
        for idx, pitch in enumerate(pitches):
            note_dicts.append({
                "pitch": pitch,
                "velocity": 100,
                "start_tick": params.start_tick + idx * rhythm_ticks,
                "duration_ticks": rhythm_ticks,
                "channel": params.channel_index,
            })

        # Apply modifiers
        note_dicts = apply_composition_modifiers(
            note_dicts, params.velocity_curve, params.swing
        )

        max_chunk_size = 32
        note_chunks = [note_dicts[i : i + max_chunk_size] for i in range(0, len(note_dicts), max_chunk_size)]

        from ..protocol import CMD_NOTES

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
        name="fl_insert_arpeggio",
        annotations={
            "title": "Insert Arpeggio",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_insert_arpeggio(params: InsertArpeggioInput) -> str:
        """Generate and insert an arpeggio sequence based on a root note or chord.

        Args:
            params (InsertArpeggioInput):
                - root (str): e.g. "C5" or comma-separated list like "C5,E5,G5"
                - chord_type (str): formula if root is single note (e.g., "major", "minor7")
                - style (str): arpeggio style: "up", "down", "updown", "random"
                - rate (str): rhythm rate: "sixteenth", "eighth", "quarter"
                - octaves (int 1-8): number of octaves to repeat
                - channel_index (int 0-127): target MIDI channel/index; defaults to 0
                - start_tick (int): start tick offset; defaults to 0
                - duration_beats (float): length in beats
                - velocity_curve (str): "none", "humanize", "crescendo", "decrescendo"
                - swing (float 0.0-1.0): swing factor; defaults to 0.0

        Returns:
            str: JSON result
        """
        bridge = FLStudioBridge.get()

        try:
            rate_ticks = rhythm_to_ticks(params.rate)
            
            # Resolve pitches
            if "," in params.root:
                base_pitches = []
                for part in params.root.split(","):
                    part = part.strip()
                    if part:
                        if part.lstrip("-").isdigit():
                            base_pitches.append(int(part))
                        else:
                            base_pitches.append(note_name_to_pitch(part))
                pitches = []
                for oct_idx in range(params.octaves):
                    for bp in base_pitches:
                        pitches.append(bp + oct_idx * 12)
            else:
                pitches = generate_chord_pitches(params.root, params.chord_type, params.octaves)
            
            if not pitches:
                raise ValueError("No pitches resolved for arpeggiator.")

            # Order pitches by style
            style_norm = params.style.strip().lower()
            if style_norm == "up":
                ordered = sorted(pitches)
            elif style_norm == "down":
                ordered = sorted(pitches, reverse=True)
            elif style_norm == "updown":
                up = sorted(pitches)
                if len(up) > 2:
                    down = up[-2:0:-1]
                    ordered = up + down
                else:
                    ordered = up + up[::-1]
            elif style_norm == "random":
                ordered = pitches  # Selected randomly per step
            else:
                ordered = sorted(pitches)

        except ValueError as exc:
            from ..errors import ErrorCode
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        total_duration_ticks = int(params.duration_beats * 96)
        num_steps = total_duration_ticks // rate_ticks

        note_dicts = []
        for step_idx in range(num_steps):
            if style_norm == "random":
                p = random.choice(ordered)
            else:
                p = ordered[step_idx % len(ordered)]

            note_dicts.append({
                "pitch": p,
                "velocity": 100,
                "start_tick": params.start_tick + step_idx * rate_ticks,
                "duration_ticks": rate_ticks,
                "channel": params.channel_index,
            })

        # Apply modifiers
        note_dicts = apply_composition_modifiers(
            note_dicts, params.velocity_curve, params.swing
        )

        max_chunk_size = 32
        note_chunks = [note_dicts[i : i + max_chunk_size] for i in range(0, len(note_dicts), max_chunk_size)]

        from ..protocol import CMD_NOTES

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
        name="fl_insert_drum_pattern",
        annotations={
            "title": "Insert Drum Pattern",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_insert_drum_pattern(params: InsertDrumPatternInput) -> str:
        """Insert a step-sequencer style drum pattern across channels.

        Args:
            params (InsertDrumPatternInput):
                - mapping (str): JSON dict mapping channel index strings to binary list, e.g. '{"0": [1,0,0,1]}'
                - rhythm (str): e.g. "sixteenth", "eighth"
                - start_tick (int): start tick offset; defaults to 0
                - velocity_curve (str): "none", "humanize", "crescendo", "decrescendo"
                - swing (float 0.0-1.0): swing factor; defaults to 0.0

        Returns:
            str: JSON result
        """
        bridge = FLStudioBridge.get()

        try:
            try:
                mapping_dict = json.loads(params.mapping)
            except Exception:
                raise ValueError("mapping must be a valid JSON dictionary string.")

            step_ticks = rhythm_to_ticks(params.rhythm)
        except ValueError as exc:
            from ..errors import ErrorCode
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        note_dicts = []
        for chan_str, sequence in mapping_dict.items():
            try:
                chan_idx = int(chan_str)
            except ValueError:
                from ..errors import ErrorCode
                return format_result(
                    FLMCPError(
                        ErrorCode.INVALID_PARAMS,
                        f"Mapping keys must be integer strings representing channel indices. Got: {chan_str!r}",
                    ).to_dict()
                )

            for step_idx, hit in enumerate(sequence):
                if hit:
                    note_dicts.append({
                        "pitch": 60,
                        "velocity": 100,
                        "start_tick": params.start_tick + step_idx * step_ticks,
                        "duration_ticks": step_ticks,
                        "channel": chan_idx,
                    })

        # Apply modifiers
        note_dicts = apply_composition_modifiers(
            note_dicts, params.velocity_curve, params.swing
        )

        max_chunk_size = 32
        note_chunks = [note_dicts[i : i + max_chunk_size] for i in range(0, len(note_dicts), max_chunk_size)]

        from ..protocol import CMD_NOTES

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
