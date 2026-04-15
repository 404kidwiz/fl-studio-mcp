"""Pydantic models and music theory helpers for FL Studio MCP."""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Note model
# ---------------------------------------------------------------------------

class Note(BaseModel):
    """A single MIDI note with position and duration expressed in ticks.

    96 ticks = 1 quarter note (FL Studio default PPQ).
    Common durations:
      - whole note:   384 ticks
      - half note:    192 ticks
      - quarter note:  96 ticks
      - eighth note:   48 ticks
      - sixteenth:     24 ticks
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    pitch: Annotated[int, Field(ge=0, le=127, description="MIDI pitch 0-127; 60 = middle C (C4)")]
    velocity: Annotated[int, Field(ge=1, le=127, description="Note velocity 1-127")] = 100
    start_tick: Annotated[int, Field(ge=0, description="Start position in ticks (96 ticks = 1 quarter note)")] = 0
    duration_ticks: Annotated[int, Field(ge=1, description="Duration in ticks (96 = quarter note)")] = 96
    channel: Annotated[int, Field(ge=0, le=15, description="MIDI channel 0-15")] = 0

    @field_validator("pitch", "velocity", "start_tick", "duration_ticks", "channel", mode="before")
    @classmethod
    def coerce_int(cls, v: object) -> int:
        return int(v)  # accept float-like inputs gracefully


# ---------------------------------------------------------------------------
# Chord helpers
# ---------------------------------------------------------------------------

class ChordQuality(str, Enum):
    MAJOR = "major"
    MINOR = "minor"
    DOM7 = "dom7"
    MAJ7 = "maj7"
    MIN7 = "min7"
    DIM = "dim"
    AUG = "aug"
    SUS2 = "sus2"
    SUS4 = "sus4"


# Semitone intervals from root for each quality
CHORD_INTERVALS: dict[ChordQuality, list[int]] = {
    ChordQuality.MAJOR: [0, 4, 7],
    ChordQuality.MINOR: [0, 3, 7],
    ChordQuality.DOM7:  [0, 4, 7, 10],
    ChordQuality.MAJ7:  [0, 4, 7, 11],
    ChordQuality.MIN7:  [0, 3, 7, 10],
    ChordQuality.DIM:   [0, 3, 6],
    ChordQuality.AUG:   [0, 4, 8],
    ChordQuality.SUS2:  [0, 2, 7],
    ChordQuality.SUS4:  [0, 5, 7],
}


def build_chord_notes(
    root_pitch: int,
    quality: ChordQuality,
    velocity: int,
    start_tick: int,
    duration_ticks: int,
    channel: int,
) -> list[Note]:
    """Expand a chord descriptor into individual Note objects."""
    intervals = CHORD_INTERVALS[quality]
    notes: list[Note] = []
    for semitones in intervals:
        pitch = root_pitch + semitones
        if 0 <= pitch <= 127:
            notes.append(
                Note(
                    pitch=pitch,
                    velocity=velocity,
                    start_tick=start_tick,
                    duration_ticks=duration_ticks,
                    channel=channel,
                )
            )
    return notes


# ---------------------------------------------------------------------------
# Transport / project models used by tools as input schemas
# ---------------------------------------------------------------------------

class ConnectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    port_name: str = Field(
        description='MIDI output port name. Partial match accepted (e.g. "IAC Driver"). '
                    'Use fl_list_midi_ports to discover available names.',
    )
    input_port_name: str | None = Field(
        default=None,
        description='MIDI input port name for receiving FL Studio responses. '
                    'Defaults to auto-detect using the same partial match as port_name. '
                    'Pass "" to disable input entirely.',
    )
    dry_run: bool = Field(
        default=False,
        description="If true, no MIDI is sent; responses show what would be sent.",
    )


class PlayStopInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # No parameters — transport commands are stateless
    pass


class SetTempoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bpm: Annotated[int, Field(ge=20, le=999, description="Target BPM (20-999)")]


class InsertNotesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: list[Note] = Field(
        min_length=1,
        max_length=128,
        description="List of notes to insert. Max 128 notes per call.",
    )


class ChordStep(BaseModel):
    """One chord in a progression."""

    model_config = ConfigDict(extra="forbid")

    root_pitch: Annotated[int, Field(ge=0, le=127, description="Root note MIDI pitch (e.g. 60 = C4)")] = 60
    quality: ChordQuality = Field(default=ChordQuality.MAJOR, description="Chord quality")
    velocity: Annotated[int, Field(ge=1, le=127)] = 100
    start_tick: Annotated[int, Field(ge=0)] = 0
    duration_ticks: Annotated[int, Field(ge=1)] = 384  # whole note default
    channel: Annotated[int, Field(ge=0, le=15)] = 0


class AddChordProgressionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chords: list[ChordStep] = Field(
        min_length=1,
        max_length=32,
        description="Ordered list of chord steps to insert.",
    )


class SaveProjectAsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(
        description="Project filename without extension (e.g. 'MyTrack'). "
                    "The FL Studio script calls ui.save(); the filename is sent as metadata.",
        min_length=1,
        max_length=255,
    )

    @field_validator("filename")
    @classmethod
    def no_path_traversal(cls, v: str) -> str:
        # Whitelist: alphanumeric, spaces, dashes, underscores, dots
        import re
        if not re.match(r'^[\w\s\-\.]+$', v):
            raise ValueError(
                "filename must contain only letters, numbers, spaces, dashes, underscores, and dots"
            )
        return v


# ---------------------------------------------------------------------------
# New tool input models
# ---------------------------------------------------------------------------

class GetStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_ms: Annotated[int, Field(ge=100, le=10000)] = Field(
        default=2000,
        description="How long to wait for FL Studio's status response, in milliseconds (100-10000).",
    )


class ListChannelsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_ms: Annotated[int, Field(ge=100, le=10000)] = Field(
        default=2000,
        description="How long to wait for FL Studio's channel list response, in milliseconds.",
    )


class SetChannelVolumeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_index: Annotated[int, Field(ge=0, le=127, description="Channel rack index (0-based)")] = 0
    volume: Annotated[int, Field(ge=0, le=127, description="Volume level 0-127 (100 = unity gain)")] = 100


class CreatePatternInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # No required params — FL Studio creates the next available pattern
    pass


class SelectPatternInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern_index: Annotated[int, Field(ge=0, le=127, description="Pattern index to jump to (0-based)")]
