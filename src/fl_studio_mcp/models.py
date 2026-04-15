"""Pydantic models and music theory helpers for FL Studio MCP."""

from __future__ import annotations

import re
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Note name → MIDI pitch conversion
# ---------------------------------------------------------------------------

# Semitone offset from C for each note letter
_NOTE_SEMITONES: dict[str, int] = {
    "C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11,
}

# Accidental adjustments
_ACCIDENTALS: dict[str, int] = {
    "#": 1, "S": 1,          # sharp  (S = legacy "s" shorthand)
    "B": -1, "F": -1,        # flat   (B = b, F = legacy "f" shorthand)
    "X": 2,                  # double sharp
    "BB": -2,                # double flat
}

_NOTE_RE = re.compile(
    r"^([A-Ga-g])"           # note letter
    r"(#{1,2}|b{1,2}|x|bb)?" # optional accidental
    r"(-?\d+)$",             # octave (may be negative, e.g. C-1 = MIDI 0)
    re.IGNORECASE,
)


def note_name_to_pitch(name: str) -> int:
    """Convert a note name string to a MIDI pitch integer (0-127).

    Supported formats:
      "C4"   → 60    "A4"  → 69    "G9"   → 127
      "C#4"  → 61    "Db4" → 61    "F#3"  → 54
      "Bb3"  → 46    "A#3" → 46    "C-1"  → 0
      "Cx4"  (double sharp C4) → 62

    Middle C = C4 = MIDI 60 (FL Studio default).
    """
    m = _NOTE_RE.match(name.strip())
    if not m:
        raise ValueError(
            f"Cannot parse {name!r} as a note name. "
            "Expected format: letter + optional accidental + octave (e.g. C4, F#3, Bb2, Db5)."
        )
    letter = m.group(1).upper()
    acc_raw = (m.group(2) or "").upper()
    octave = int(m.group(3))

    semitone = _NOTE_SEMITONES[letter]
    if acc_raw:
        acc_key = acc_raw.replace("B", "B")  # keep as-is; handled below
        # Normalise 'b' → 'B', '#' stays '#', 'x' → 'X', 'bb' → 'BB'
        acc_key = acc_raw.upper()
        semitone += _ACCIDENTALS.get(acc_key, 0)

    # Formula: MIDI = (octave + 1) * 12 + semitone
    pitch = (octave + 1) * 12 + semitone
    if not 0 <= pitch <= 127:
        raise ValueError(
            f"Note {name!r} maps to MIDI pitch {pitch}, which is outside the valid range 0-127."
        )
    return pitch


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

    The ``pitch`` field accepts both integers (0-127) and note name strings:
      - Integer:   pitch=60   (middle C)
      - Note name: pitch="C4" (same as above)
      - Note name: pitch="F#3", pitch="Bb4", pitch="A4"
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    pitch: Annotated[int, Field(ge=0, le=127, description='MIDI pitch 0-127 OR note name string e.g. "C4", "F#3", "Bb4"')]
    velocity: Annotated[int, Field(ge=1, le=127, description="Note velocity 1-127")] = 100
    start_tick: Annotated[int, Field(ge=0, description="Start position in ticks (96 ticks = 1 quarter note)")] = 0
    duration_ticks: Annotated[int, Field(ge=1, description="Duration in ticks (96 = quarter note)")] = 96
    channel: Annotated[int, Field(ge=0, le=15, description="MIDI channel 0-15")] = 0

    @field_validator("pitch", mode="before")
    @classmethod
    def parse_pitch(cls, v: object) -> int:
        """Accept int, float-like, or note name string (e.g. "C4", "F#3")."""
        if isinstance(v, str):
            # Pure numeric string → treat as int
            if v.strip().lstrip("-").isdigit():
                return int(v)
            return note_name_to_pitch(v)
        return int(v)

    @field_validator("velocity", "start_tick", "duration_ticks", "channel", mode="before")
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

    root_pitch: Annotated[int, Field(ge=0, le=127, description='Root note: MIDI int (60) or note name ("C4", "F#3")')] = 60
    quality: ChordQuality = Field(default=ChordQuality.MAJOR, description="Chord quality")
    velocity: Annotated[int, Field(ge=1, le=127)] = 100
    start_tick: Annotated[int, Field(ge=0)] = 0
    duration_ticks: Annotated[int, Field(ge=1)] = 384  # whole note default
    channel: Annotated[int, Field(ge=0, le=15)] = 0

    @field_validator("root_pitch", mode="before")
    @classmethod
    def parse_root_pitch(cls, v: object) -> int:
        """Accept int or note name string for the chord root."""
        if isinstance(v, str):
            if v.strip().lstrip("-").isdigit():
                return int(v)
            return note_name_to_pitch(v)
        return int(v)


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


class ListPatternsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_ms: Annotated[int, Field(ge=100, le=10000)] = Field(
        default=2000,
        description="How long to wait for FL Studio's pattern list response, in milliseconds.",
    )


class MuteChannelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_index: Annotated[int, Field(ge=0, le=127, description="Channel rack index (0-based)")]
    muted: bool = Field(default=True, description="True to mute, False to unmute.")


class SoloChannelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_index: Annotated[int, Field(ge=0, le=127, description="Channel rack index (0-based)")]
    soloed: bool = Field(default=True, description="True to solo, False to un-solo.")


class PanicInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # No parameters — panic always hits all 16 channels
    pass


class DisconnectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # No parameters — closes whatever ports are currently open
    pass


class ClearPatternInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # No parameters — clears the currently selected pattern
    pass


class SetChannelPanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_index: Annotated[int, Field(ge=0, le=127, description="Channel rack index (0-based)")]
    pan: Annotated[int, Field(ge=0, le=127, description="Pan position: 0=full left, 64=centre, 127=full right")] = 64
