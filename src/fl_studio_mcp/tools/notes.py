"""Tools: insert_notes, add_chord_progression — send note data to FL Studio."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import FLMCPError
from ..models import (
    AddChordProgressionInput,
    InsertNotesInput,
    build_chord_notes,
)
from ..protocol import encode_notes


def _notes_to_dicts(notes) -> list[dict]:
    return [n.model_dump() for n in notes]


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="fl_insert_notes",
        annotations={
            "title": "Insert Notes",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_insert_notes(params: InsertNotesInput) -> str:
        """Play MIDI notes in FL Studio via the bridge controller script.

        The FL MCP Bridge receives this SysEx and plays notes in realtime
        via channels.midiNoteOn(). Notes are triggered immediately — they
        are NOT inserted into the pattern piano roll.

        **To record notes into a pattern:** Enable Record mode in FL Studio's
        transport BEFORE calling this tool. FL Studio will capture the played
        notes into the current pattern while recording.

        Tick reference (FL Studio default 96 PPQ):
          - Quarter note = 96 ticks
          - Half note    = 192 ticks
          - Whole note   = 384 ticks
          - 8th note     = 48 ticks
          - 16th note    = 24 ticks

        Note: start_tick and duration_ticks are encoded in the SysEx but
        currently fire all notes simultaneously in realtime mode.

        Requires fl_connect to have been called first.

        Args:
            params (InsertNotesInput):
                - notes (list[Note]): 1-128 notes. Each note has:
                    - pitch (int 0-127): MIDI pitch; 60 = middle C
                    - velocity (int 1-127): defaults to 100
                    - start_tick (int): position in ticks; defaults to 0
                    - duration_ticks (int): length in ticks; defaults to 96
                    - channel (int 0-15): MIDI channel; defaults to 0

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - note_count (int)
                - notes_preview (list): first 8 notes as confirmation
                - bytes (str): hex of SysEx sent (may be truncated in preview)
        """
        bridge = FLStudioBridge.get()
        note_dicts = _notes_to_dicts(params.notes)

        # Apply composition modifiers (velocity curves and swing)
        from ..theory import apply_composition_modifiers

        note_dicts = apply_composition_modifiers(
            note_dicts, params.velocity_curve, params.swing
        )

        # Chunk notes list into batches of max 32 notes
        max_chunk_size = 32
        note_chunks = [
            note_dicts[i : i + max_chunk_size]
            for i in range(0, len(note_dicts), max_chunk_size)
        ]

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
        except ValueError as exc:
            from ..errors import ErrorCode

            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result = last_result or {}
        result["note_count"] = len(params.notes)
        result["notes_preview"] = note_dicts[:8]
        result["chunks_sent"] = len(note_chunks)
        return format_result(result)

    @mcp.tool(
        name="fl_add_chord_progression",
        annotations={
            "title": "Add Chord Progression",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_add_chord_progression(params: AddChordProgressionInput) -> str:
        """Insert a chord progression into FL Studio.

        Expands each ChordStep into individual MIDI notes using music-theory
        interval tables, then sends them all in a single SysEx message.

        Supported chord qualities:
          major, minor, dom7, maj7, min7, dim, aug, sus2, sus4

        Tick reference (96 PPQ):
          - duration_ticks=384 → whole note (one full bar at 4/4)
          - Set start_tick to 384, 768, 1152 … for bars 1, 2, 3 …

        Requires fl_connect to have been called first.

        Args:
            params (AddChordProgressionInput):
                - chords (list[ChordStep]): 1-32 chords. Each step has:
                    - root_pitch (int 0-127): root note; e.g. 60=C4, 62=D4, 64=E4
                    - quality (str): chord quality (see above)
                    - velocity (int 1-127): defaults to 100
                    - start_tick (int): bar offset in ticks; defaults to 0
                    - duration_ticks (int): chord length in ticks; defaults to 384
                    - channel (int 0-15): MIDI channel; defaults to 0

        Returns:
            str: JSON with keys:
                - sent (bool) or dry_run (bool)
                - chord_count (int)
                - total_notes (int): individual MIDI notes sent
                - progression_preview (list): summary of each chord
                - bytes (str): hex of SysEx sent
                - chunks_sent (int): number of SysEx chunks sent

        Examples:
            I-V-vi-IV in C major (C4=60):
              chords = [
                {root_pitch:60, quality:"major",  start_tick:0,   duration_ticks:384},
                {root_pitch:67, quality:"major",  start_tick:384, duration_ticks:384},
                {root_pitch:69, quality:"minor",  start_tick:768, duration_ticks:384},
                {root_pitch:65, quality:"major",  start_tick:1152,duration_ticks:384},
              ]
        """
        bridge = FLStudioBridge.get()

        # Expand all chords into notes
        all_notes = []
        progression_preview = []
        for step in params.chords:
            chord_notes = build_chord_notes(
                root_pitch=step.root_pitch,
                quality=step.quality,
                velocity=step.velocity,
                start_tick=step.start_tick,
                duration_ticks=step.duration_ticks,
                channel=step.channel,
            )
            all_notes.extend(chord_notes)
            progression_preview.append(
                {
                    "root_pitch": step.root_pitch,
                    "quality": step.quality,
                    "start_tick": step.start_tick,
                    "note_count": len(chord_notes),
                }
            )

        if not all_notes:
            from ..errors import ErrorCode

            return format_result(
                FLMCPError(
                    ErrorCode.INVALID_PARAMS,
                    "No valid notes generated — check that root_pitch values are 0-127.",
                ).to_dict()
            )

        note_dicts = _notes_to_dicts(all_notes)
        max_chunk_size = 32
        note_chunks = [
            note_dicts[i : i + max_chunk_size]
            for i in range(0, len(note_dicts), max_chunk_size)
        ]

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
        except ValueError as exc:
            from ..errors import ErrorCode

            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result = last_result or {}
        result["chord_count"] = len(params.chords)
        result["total_notes"] = len(all_notes)
        result["progression_preview"] = progression_preview
        result["chunks_sent"] = len(note_chunks)
        return format_result(result)
