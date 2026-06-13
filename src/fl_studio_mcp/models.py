"""Pydantic models and music theory helpers for FL Studio MCP."""

from __future__ import annotations

import re
from enum import Enum
from typing import Annotated, Optional, List

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Note name → MIDI pitch conversion
# ---------------------------------------------------------------------------

# Semitone offset from C for each note letter
_NOTE_SEMITONES: dict[str, int] = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}

# Accidental adjustments
_ACCIDENTALS: dict[str, int] = {
    "#": 1,
    "S": 1,  # sharp  (S = legacy "s" shorthand)
    "B": -1,
    "F": -1,  # flat   (B = b, F = legacy "f" shorthand)
    "X": 2,  # double sharp
    "BB": -2,  # double flat
}

_NOTE_RE = re.compile(
    r"^([A-Ga-g])"  # note letter
    r"(#{1,2}|b{1,2}|x|bb)?"  # optional accidental
    r"(-?\d+)$",  # octave (may be negative, e.g. C-1 = MIDI 0)
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

    pitch: Annotated[
        int,
        Field(
            ge=0,
            le=127,
            description='MIDI pitch 0-127 OR note name string e.g. "C4", "F#3", "Bb4"',
        ),
    ]
    velocity: Annotated[int, Field(ge=1, le=127, description="Note velocity 1-127")] = (
        100
    )
    start_tick: Annotated[
        int,
        Field(ge=0, description="Start position in ticks (96 ticks = 1 quarter note)"),
    ] = 0
    duration_ticks: Annotated[
        int, Field(ge=1, description="Duration in ticks (96 = quarter note)")
    ] = 96
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

    @field_validator(
        "velocity", "start_tick", "duration_ticks", "channel", mode="before"
    )
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
    ChordQuality.DOM7: [0, 4, 7, 10],
    ChordQuality.MAJ7: [0, 4, 7, 11],
    ChordQuality.MIN7: [0, 3, 7, 10],
    ChordQuality.DIM: [0, 3, 6],
    ChordQuality.AUG: [0, 4, 8],
    ChordQuality.SUS2: [0, 2, 7],
    ChordQuality.SUS4: [0, 5, 7],
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
        "Use fl_list_midi_ports to discover available names.",
    )
    input_port_name: str | None = Field(
        default=None,
        description="MIDI input port name for receiving FL Studio responses. "
        "Defaults to auto-detect using the same partial match as port_name. "
        'Pass "" to disable input entirely.',
    )
    dry_run: bool = Field(
        default=False,
        description="If true, no MIDI is sent; responses show what would be sent.",
    )


class WriteCommandInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ack: bool = Field(
        default=False,
        description="Whether to wait for confirmation (ACK) from FL Studio.",
    )
    timeout_ms: Annotated[int, Field(ge=50, le=10000)] = Field(
        default=200,
        description="How long to wait for ACK (if enabled), in milliseconds.",
    )


class PlayStopInput(WriteCommandInput):
    # No parameters — transport commands are stateless
    pass


class SetTempoInput(WriteCommandInput):
    bpm: Annotated[int, Field(ge=20, le=999, description="Target BPM (20-999)")]


class InsertNotesInput(WriteCommandInput):
    notes: list[Note] = Field(
        min_length=1,
        max_length=128,
        description="List of notes to insert. Max 128 notes per call.",
    )
    velocity_curve: str = Field(
        default="none",
        description="Velocity curve: 'none', 'humanize' (±15 random), 'crescendo', 'decrescendo'",
    )
    swing: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        default=0.0,
        description="Swing percentage (0.0 - 1.0) to shift even-numbered subdivisions.",
    )


class InsertScaleInput(WriteCommandInput):
    root: str = Field(
        default="C5",
        description="Root note (e.g. C5, F#4, Bb3)",
    )
    scale: str = Field(
        default="major",
        description="Scale type: 'major', 'minor', 'pentatonic_major', 'pentatonic_minor', 'dorian', 'phrygian', 'lydian', 'mixolydian', 'locrian', 'harmonic_minor', 'melodic_minor', 'chromatic', 'whole_tone'",
    )
    octaves: Annotated[int, Field(ge=1, le=8)] = Field(
        default=1,
        description="Number of octaves to span (1 to 8).",
    )
    rhythm: str = Field(
        default="eighth",
        description="Rhythm step size: 'whole', 'half', 'quarter', 'eighth', 'sixteenth', 'triplet_quarter', 'triplet_eighth' or a tick count.",
    )
    channel_index: Annotated[int, Field(ge=0, le=127)] = Field(
        default=0,
        description="Target channel index in the Channel Rack.",
    )
    start_tick: Annotated[int, Field(ge=0)] = Field(
        default=0,
        description="Tick at which the scale starts (96 ticks = 1 beat).",
    )
    velocity_curve: str = Field(
        default="none",
        description="Velocity curve: 'none', 'humanize', 'crescendo', 'decrescendo'",
    )
    swing: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        default=0.0,
        description="Swing percentage (0.0 - 1.0) to shift even steps.",
    )


class InsertArpeggioInput(WriteCommandInput):
    root: str = Field(
        default="C5",
        description="Root note or starting note (e.g. C5, F#4) or comma-separated list of notes (e.g. 'C5,E5,G5')",
    )
    chord_type: str = Field(
        default="major",
        description="Chord formula to use if root is a single note: 'major', 'minor', 'diminished', 'augmented', 'major7', 'minor7', 'dominant7', 'sus2', 'sus4'",
    )
    style: str = Field(
        default="up",
        description="Arpeggio pattern style: 'up', 'down', 'updown' (pingpong), 'random'",
    )
    rate: str = Field(
        default="sixteenth",
        description="Step duration rate: 'whole', 'half', 'quarter', 'eighth', 'sixteenth', 'triplet_quarter', 'triplet_eighth' or a tick count.",
    )
    octaves: Annotated[int, Field(ge=1, le=8)] = Field(
        default=1,
        description="Number of octaves to repeat the arpeggiation (1 to 8).",
    )
    channel_index: Annotated[int, Field(ge=0, le=127)] = Field(
        default=0,
        description="Target channel index in the Channel Rack.",
    )
    start_tick: Annotated[int, Field(ge=0)] = Field(
        default=0,
        description="Tick at which the arpeggio starts.",
    )
    duration_beats: Annotated[float, Field(ge=0.25)] = Field(
        default=4.0,
        description="Total duration of arpeggiation in beats (BPM dependent).",
    )
    velocity_curve: str = Field(
        default="none",
        description="Velocity curve: 'none', 'humanize', 'crescendo', 'decrescendo'",
    )
    swing: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        default=0.0,
        description="Swing percentage (0.0 - 1.0) to shift even steps.",
    )


class InsertDrumPatternInput(WriteCommandInput):
    mapping: str = Field(
        description='JSON dictionary mapping channel index strings to lists of 1s (hits) and 0s (rests) e.g., \'{"0": [1,0,0,1], "1": [0,1,0,0]}\'',
    )
    rhythm: str = Field(
        default="sixteenth",
        description="Step duration rate: 'whole', 'half', 'quarter', 'eighth', 'sixteenth', 'triplet_quarter', 'triplet_eighth' or a tick count.",
    )
    start_tick: Annotated[int, Field(ge=0)] = Field(
        default=0,
        description="Tick at which the drum pattern starts.",
    )
    velocity_curve: str = Field(
        default="none",
        description="Velocity curve: 'none', 'humanize', 'crescendo', 'decrescendo'",
    )
    swing: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        default=0.0,
        description="Swing percentage (0.0 - 1.0) to shift even steps.",
    )


class ChordStep(BaseModel):
    """One chord in a progression."""

    model_config = ConfigDict(extra="forbid")

    root_pitch: Annotated[
        int,
        Field(
            ge=0,
            le=127,
            description='Root note: MIDI int (60) or note name ("C4", "F#3")',
        ),
    ] = 60
    quality: ChordQuality = Field(
        default=ChordQuality.MAJOR, description="Chord quality"
    )
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


class AddChordProgressionInput(WriteCommandInput):
    chords: list[ChordStep] = Field(
        min_length=1,
        max_length=32,
        description="Ordered list of chord steps to insert.",
    )


class SaveProjectInput(WriteCommandInput):
    """Input for saving the current project.

    FL Studio's ui.save() saves to the current filename (Ctrl+S equivalent).
    If the project has never been saved, FL Studio shows its native Save dialog.
    No filename can be set programmatically from a controller script.
    """

    confirm: bool = Field(
        default=False,
        description="MUST be set to true to execute the save command. Prevents accidental project overwrites.",
    )


class ChannelInitInput(BaseModel):
    """Input for initializing or modifying a channel in a project generator."""

    name: str = Field(description="Name of the channel.")
    sample_path: str | None = Field(default=None, description="Optional absolute path to an audio file/sample.")


class GenerateProjectInput(WriteCommandInput):
    """Input for generating/modifying an FL Studio project offline."""

    output_path: str = Field(description="Absolute destination path to save the generated/modified .flp project.")
    genre: str = Field(
        default="empty",
        description="Genre starter template. Allowed: 'trap', 'house', 'synthwave', 'empty'",
    )
    bpm: float | None = Field(
        default=None,
        description="BPM to set in the project (e.g. 140.0).",
    )
    title: str | None = Field(
        default=None,
        description="Project title/name metadata.",
    )
    channels: list[ChannelInitInput] | None = Field(
        default=None,
        description="Optional list of channels to initialize or modify.",
    )


# ---------------------------------------------------------------------------
# New tool input models
# ---------------------------------------------------------------------------


class UndoInput(WriteCommandInput):
    """Input for navigating backward in history (Undo)."""

    pass


class RedoInput(WriteCommandInput):
    """Input for navigating forward in history (Redo)."""

    pass


class PingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge: Annotated[int, Field(ge=0, le=127)] = Field(
        default=42,
        description="Ping challenge byte (0-127).",
    )
    timeout_ms: Annotated[int, Field(ge=100, le=10000)] = Field(
        default=1000,
        description="How long to wait for response, in milliseconds.",
    )


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


class SetChannelVolumeInput(WriteCommandInput):
    channel_index: Annotated[
        int, Field(ge=0, le=127, description="Channel rack index (0-based)")
    ] = 0
    volume: Annotated[
        int, Field(ge=0, le=127, description="Volume level 0-127 (100 = unity gain)")
    ] = 100


class CreatePatternInput(WriteCommandInput):
    # No required params — FL Studio creates the next available pattern
    pass


class SelectPatternInput(WriteCommandInput):
    pattern_index: Annotated[
        int, Field(ge=0, le=127, description="Pattern index to jump to (0-based)")
    ]


class ListPatternsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_ms: Annotated[int, Field(ge=100, le=10000)] = Field(
        default=2000,
        description="How long to wait for FL Studio's pattern list response, in milliseconds.",
    )


class MuteChannelInput(WriteCommandInput):
    channel_index: Annotated[
        int, Field(ge=0, le=127, description="Channel rack index (0-based)")
    ]
    muted: bool = Field(default=True, description="True to mute, False to unmute.")


class SoloChannelInput(WriteCommandInput):
    channel_index: Annotated[
        int, Field(ge=0, le=127, description="Channel rack index (0-based)")
    ]
    soloed: bool = Field(default=True, description="True to solo, False to un-solo.")


class PanicInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # No parameters — panic always hits all 16 channels
    pass


class DisconnectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # No parameters — closes whatever ports are currently open
    pass


class SetChannelPanInput(WriteCommandInput):
    channel_index: Annotated[
        int, Field(ge=0, le=127, description="Channel rack index (0-based)")
    ]
    pan: Annotated[
        int,
        Field(
            ge=0,
            le=127,
            description="Pan position: 0=full left, 64=centre, 127=full right",
        ),
    ] = 64


class GetNotesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_ms: Annotated[int, Field(ge=100, le=10000)] = Field(
        default=2000,
        description="How long to wait for FL Studio's notes response, in milliseconds.",
    )


class GetContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_ms: Annotated[int, Field(ge=100, le=10000)] = Field(
        default=2000,
        description="How long to wait for FL Studio's context response, in milliseconds.",
    )


class SetPatternLengthInput(WriteCommandInput):
    pattern_index: Annotated[
        int, Field(ge=0, le=999, description="Pattern index (0-based, up to 999)")
    ]
    length_beats: Annotated[
        int, Field(ge=1, le=999, description="Target pattern length in beats (1-999)")
    ]


class RenameChannelInput(WriteCommandInput):
    channel_index: Annotated[
        int, Field(ge=0, le=127, description="Channel rack index (0-based)")
    ]
    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=14,
            description="New name (ASCII characters only, max 14 chars)",
        ),
    ]

    @field_validator("name")
    @classmethod
    def validate_ascii(cls, v: str) -> str:
        if not v.isascii():
            raise ValueError("Name must contain ASCII characters only.")
        return v


class RenamePatternInput(WriteCommandInput):
    pattern_index: Annotated[
        int, Field(ge=0, le=999, description="Pattern index (0-based, up to 999)")
    ]
    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=14,
            description="New name (ASCII characters only, max 14 chars)",
        ),
    ]

    @field_validator("name")
    @classmethod
    def validate_ascii(cls, v: str) -> str:
        if not v.isascii():
            raise ValueError("Name must contain ASCII characters only.")
        return v


class SetMixerVolumeInput(WriteCommandInput):
    track_index: Annotated[
        int, Field(ge=0, le=127, description="Mixer track index (0-127)")
    ] = 0
    volume: Annotated[
        int,
        Field(
            ge=0,
            le=127,
            description="Volume level 0-127 (100 = unity gain / 100% fader in FL)",
        ),
    ] = 100


class SetMixerPanInput(WriteCommandInput):
    track_index: Annotated[
        int, Field(ge=0, le=127, description="Mixer track index (0-127)")
    ]
    pan: Annotated[
        int,
        Field(
            ge=0,
            le=127,
            description="Pan position: 0=full left, 64=centre, 127=full right",
        ),
    ] = 64


class RouteToMixerInput(WriteCommandInput):
    channel_index: Annotated[
        int, Field(ge=0, le=127, description="Channel rack index (0-based)")
    ]
    track_index: Annotated[
        int, Field(ge=0, le=127, description="Mixer track index (0-127) to route to")
    ]


class GetMixerStateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_track: Annotated[
        int, Field(ge=0, le=127, description="Start track index (0-127)")
    ] = 0
    end_track: Annotated[
        int, Field(ge=0, le=127, description="End track index (0-127)")
    ] = 16
    timeout_ms: Annotated[
        int,
        Field(
            ge=100,
            le=10000,
            description="How long to wait for response in milliseconds",
        ),
    ] = 2000


# --- Option 2: Preset Librarian Pydantic Inputs ---


class CatalogPresetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vst_name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            description="The name of the VST plug-in (e.g. Serum, Vital)",
        ),
    ]
    preset_name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            description="The name of the VST preset to catalog",
        ),
    ]
    x: Annotated[int, Field(ge=0, description="X screen coordinate for mouse click")]
    y: Annotated[int, Field(ge=0, description="Y screen coordinate for mouse click")]
    category: Annotated[
        str,
        Field(
            default="Unsorted",
            description="Optional preset category (e.g. Leads, Pads, Basses)",
        ),
    ]
    tags: Annotated[
        Optional[List[str]],
        Field(default=None, description="Optional search tags for categorization"),
    ] = None
    notes: Annotated[
        str,
        Field(
            default="",
            description="Descriptive notes or documentation about the preset",
        ),
    ] = ""


class SearchPresetsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Keyword search query across name, notes, category, and tags",
        ),
    ] = None
    vst_name: Annotated[
        Optional[str],
        Field(default=None, description="Filter presets by specific VST name"),
    ] = None
    tag: Annotated[
        Optional[str], Field(default=None, description="Filter presets by a single tag")
    ] = None
    category: Annotated[
        Optional[str],
        Field(default=None, description="Filter presets by a specific category"),
    ] = None


class LoadPresetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vst_name: Annotated[
        str, Field(min_length=1, description="The name of the VST plug-in")
    ]
    preset_name: Annotated[
        str, Field(min_length=1, description="The name of the preset to load")
    ]


# --- Option 3: Algorithmic Composition Pydantic Inputs ---


class InsertEuclideanDrumsInput(WriteCommandInput):
    mapping: Annotated[
        str,
        Field(
            description="JSON dict string mapping channel index strings to binary sequencer hit length, e.g. '{\"0\": [1,0,0,1]}'"
        ),
    ]
    rhythm: Annotated[
        str,
        Field(
            default="sixteenth",
            description="The step subdivision speed, e.g. 'sixteenth', 'eighth', 'quarter'",
        ),
    ] = "sixteenth"
    start_tick: Annotated[
        int, Field(default=0, ge=0, description="Starting tick offset (96 PPQ)")
    ] = 0
    hits: Annotated[
        int, Field(default=5, ge=1, le=64, description="Number of hits to distribute")
    ] = 5
    steps: Annotated[
        int,
        Field(default=16, ge=1, le=128, description="Length of sequence loop steps"),
    ] = 16
    rotation: Annotated[
        int,
        Field(
            default=0,
            description="Left/right circular shift (rotation) of Euclidean rhythm",
        ),
    ] = 0
    velocity_curve: Annotated[
        str,
        Field(
            default="none",
            description="Velocity curves: 'none', 'humanize', 'crescendo', 'decrescendo'",
        ),
    ] = "none"
    swing: Annotated[
        float,
        Field(
            default=0.0, ge=0.0, le=1.0, description="Swing quantization shift factor"
        ),
    ] = 0.0


class GenerateMarkovMelodyInput(WriteCommandInput):
    root: Annotated[
        str, Field(default="C5", description="Root note name (e.g. C5, F#4)")
    ] = "C5"
    scale: Annotated[
        str,
        Field(
            default="minor",
            description="Scale type (e.g. major, minor, dorian, harmonic_minor)",
        ),
    ] = "minor"
    length_beats: Annotated[
        float,
        Field(default=4.0, ge=0.5, le=32.0, description="Length of melody in beats"),
    ] = 4.0
    rate: Annotated[
        str,
        Field(
            default="eighth",
            description="Step note division speed: 'sixteenth', 'eighth', 'quarter'",
        ),
    ] = "eighth"
    channel_index: Annotated[
        int,
        Field(default=0, ge=0, le=127, description="Target instrument channel index"),
    ] = 0
    start_tick: Annotated[
        int, Field(default=0, ge=0, description="Start tick offset (96 PPQ)")
    ] = 0
    velocity_curve: Annotated[
        str,
        Field(
            default="humanize",
            description="Velocity curves: 'none', 'humanize', 'crescendo', 'decrescendo'",
        ),
    ] = "humanize"
    swing: Annotated[
        float,
        Field(
            default=0.0, ge=0.0, le=1.0, description="Swing quantization shift factor"
        ),
    ] = 0.0


class InsertVoiceLedProgressionInput(WriteCommandInput):
    progression: Annotated[
        str,
        Field(
            description="Comma-separated chord progression, e.g. 'C5-major, G5-major, A4-minor, F4-major'"
        ),
    ]
    rate: Annotated[
        str,
        Field(
            default="half",
            description="Chord change division: 'whole', 'half', 'quarter'",
        ),
    ] = "half"
    channel_index: Annotated[
        int,
        Field(default=0, ge=0, le=127, description="Target instrument channel index"),
    ] = 0
    start_tick: Annotated[
        int, Field(default=0, ge=0, description="Start tick offset (96 PPQ)")
    ] = 0
    velocity_curve: Annotated[
        str,
        Field(
            default="none",
            description="Velocity curves: 'none', 'humanize', 'crescendo', 'decrescendo'",
        ),
    ] = "none"
    swing: Annotated[
        float,
        Field(
            default=0.0, ge=0.0, le=1.0, description="Swing quantization shift factor"
        ),
    ] = 0.0


class SetGridBitInput(WriteCommandInput):
    channel_index: Annotated[int, Field(ge=0, le=127, description="Channel rack index")]
    step_index: Annotated[int, Field(ge=0, le=127, description="Step sequence index (e.g., 0-15)")]
    value: Annotated[int, Field(ge=0, le=1, description="1 to enable step, 0 to disable")]


class MutePlaylistTrackInput(WriteCommandInput):
    track_index: Annotated[int, Field(ge=0, le=127, description="Playlist track index (1-based generally, but test 0-based in FL API)")]
    muted: bool


class SoloPlaylistTrackInput(WriteCommandInput):
    track_index: Annotated[int, Field(ge=0, le=127, description="Playlist track index")]
    soloed: bool


class SetTimeSelectionInput(WriteCommandInput):
    start_bar: Annotated[int, Field(ge=0, le=999, description="Start bar for selection loop")]
    end_bar: Annotated[int, Field(ge=0, le=999, description="End bar for selection loop")]


class SetChannelColorInput(WriteCommandInput):
    channel_index: Annotated[int, Field(ge=0, le=127, description="Channel rack index")]
    r: Annotated[int, Field(ge=0, le=255)]
    g: Annotated[int, Field(ge=0, le=255)]
    b: Annotated[int, Field(ge=0, le=255)]


class SetPatternColorInput(BaseModel):
    pattern_index: int = Field(..., description="The pattern number to color.")
    color_hex: int = Field(..., description="The 24-bit RGB hex code for the color (e.g. 0x00RRGGBB).")


# --- Phase 7 Enhancements ---

class SetChannelNameInput(BaseModel):
    channel_index: int = Field(..., description="The channel index to rename.")
    name: str = Field(..., description="The new name for the channel. Use empty string to reset to default.")

class SetChannelMixerTrackInput(BaseModel):
    channel_index: int = Field(..., description="The channel index.")
    track_index: int = Field(..., description="The mixer track number to route this channel to (0 = Master, 1-125 = Inserts).")

class UiNavigateInput(BaseModel):
    action: str = Field(
        ...,
        description="The UI action to perform. Valid actions: 'up', 'down', 'left', 'right', 'enter', 'escape', 'focus_browser', 'focus_channel_rack', 'focus_mixer', 'focus_playlist'"
    )


class RenderProjectInput(WriteCommandInput):
    """Input for rendering an FL Studio project to audio via headless CLI or fallback simulator."""
    project_path: str = Field(..., description="Absolute path to the source FL Studio project (.flp) to render.")
    output_path: str = Field(..., description="Absolute destination path to save the rendered audio file.")
    format: str = Field(default="wav", description="Render output format. Valid choices: 'wav', 'mp3', 'ogg', 'flac', 'mid'. Defaults to 'wav'.")
    bitrate: int | None = Field(default=None, description="Bitrate for MP3/OGG (e.g. 192, 320) or bit-depth for WAV/FLAC (16, 24, 32).")


class GetTrackPeaksInput(BaseModel):
    """Input for retrieving peak levels of a mixer track."""
    track_index: int = Field(default=0, ge=0, le=127, description="Mixer track index (0 = Master, 1-127 = Inserts).")


class AutoMixInput(WriteCommandInput):
    """Input for the fader balancer mixing assistant."""
    tracks: list[int] = Field(..., description="List of mixer track indices to analyze and balance (1-127).")
    target_db: float = Field(default=-12.0, ge=-48.0, le=0.0, description="Target peak level in dB for the balanced tracks.")
    headroom_db: float = Field(default=-3.0, ge=-12.0, le=0.0, description="Additional headroom or scaling margin.")


# ---------------------------------------------------------------------------
# Song/Project Management Models
# ---------------------------------------------------------------------------


class GetSongLengthInput(BaseModel):
    """Input for retrieving the total duration of the current song."""
    pass


class SetSongMarkerInput(BaseModel):
    """Input for setting a marker at the current position."""
    marker_name: str = Field(..., description="Name for the marker")
    color_r: int = Field(default=255, ge=0, le=255, description="Red component (0-255)")
    color_g: int = Field(default=255, ge=0, le=255, description="Green component (0-255)")
    color_b: int = Field(default=255, ge=0, le=255, description="Blue component (0-255)")


class GetMarkerInput(BaseModel):
    """Input for retrieving information about a specific marker."""
    marker_index: int = Field(..., ge=0, description="Zero-based index of the marker")


class DeleteMarkerInput(BaseModel):
    """Input for deleting a marker from the playlist."""
    marker_index: int = Field(..., ge=0, description="Zero-based index of the marker to delete")


class InsertMarkerInput(BaseModel):
    """Input for inserting a marker at a specific position."""
    position_beats: float = Field(..., ge=0, description="Position in beats where to insert marker")
    marker_name: str = Field(..., description="Name for the marker")
    color_r: int = Field(default=255, ge=0, le=255, description="Red component (0-255)")
    color_g: int = Field(default=255, ge=0, le=255, description="Green component (0-255)")
    color_b: int = Field(default=255, ge=0, le=255, description="Blue component (0-255)")


class GetSongTempoInput(BaseModel):
    """Input for retrieving the current tempo (BPM) of the song."""
    timeout_ms: int = Field(default=2000, ge=100, le=10000, description="Response wait timeout in milliseconds")


class SetSongBpmInput(BaseModel):
    """Input for setting the tempo (BPM) of the song."""
    bpm: int = Field(..., ge=20, le=999, description="Target BPM (20-999)")
    confirm: bool = Field(default=False, description="Confirmation flag to prevent accidental changes")


class GetSongBpmInput(BaseModel):
    """Input for retrieving the current BPM as a floating-point number."""
    pass


class SetSongTempoRelativeInput(BaseModel):
    """Input for adjusting the tempo relative to the current BPM."""
    percentage: float = Field(..., ge=-50, le=200, description="Percentage change (-50 to 200)")
    confirm: bool = Field(default=False, description="Confirmation flag to prevent accidental changes")


class GetSongInfoInput(BaseModel):
    """Input for retrieving comprehensive information about the current song."""
    pass


class SaveAsProjectInput(BaseModel):
    """Input for saving the current project with a new filename."""
    filename: str = Field(..., description="New filename (with .flp extension)")
    confirm: bool = Field(default=False, description="Confirmation flag to prevent accidental overwrites")


class ExportAudioInput(BaseModel):
    """Input for exporting audio from the project."""
    output_path: str = Field(..., description="Path where to save the exported audio file")
    format: str = Field(..., description="Audio format ('wav', 'mp3', 'flac')")
    quality: int = Field(default=90, ge=0, le=100, description="Quality level (0-100, higher is better)")
    confirm: bool = Field(default=False, description="Confirmation flag to prevent accidental exports")


class GetMixerTrackCountInput(BaseModel):
    """Input for retrieving the number of tracks in the mixer."""
    timeout_ms: int = Field(default=2000, ge=100, le=10000, description="Response wait timeout in milliseconds")


class GetChannelCountInput(BaseModel):
    """Input for retrieving the number of channels in the channel rack."""
    timeout_ms: int = Field(default=2000, ge=100, le=10000, description="Response wait timeout in milliseconds")


class GetPatternCountInput(BaseModel):
    """Input for retrieving the number of patterns in the song."""
    timeout_ms: int = Field(default=2000, ge=100, le=10000, description="Response wait timeout in milliseconds")


class GetCurrentPatternInput(BaseModel):
    """Input for retrieving the index of the currently selected pattern."""
    timeout_ms: int = Field(default=2000, ge=100, le=10000, description="Response wait timeout in milliseconds")


class SetCurrentPatternInput(BaseModel):
    """Input for setting the currently selected pattern."""
    pattern_index: int = Field(..., ge=0, description="Zero-based pattern index to select")
    confirm: bool = Field(default=False, description="Confirmation flag to prevent accidental changes")


class DuplicatePatternInput(BaseModel):
    """Input for duplicating the current pattern."""
    pass


class CopyPatternInput(BaseModel):
    """Input for copying the current pattern to a specific slot."""
    target_pattern_index: int = Field(..., ge=0, le=127, description="Target pattern slot index (0-127)")
    confirm: bool = Field(default=False, description="Confirmation flag")


class CutPatternInput(BaseModel):
    """Input for cutting the current pattern to clipboard."""
    pass


class PastePatternInput(BaseModel):
    """Input for pasting pattern from clipboard to a specific slot."""
    target_pattern_index: int = Field(..., ge=0, le=127, description="Target pattern slot index (0-127)")
    confirm: bool = Field(default=False, description="Confirmation flag")


class ClearPatternInput(BaseModel):
    """Input for clearing the current pattern."""
    pass
