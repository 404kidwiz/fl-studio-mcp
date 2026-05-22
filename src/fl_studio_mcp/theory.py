"""Music theory structures and note generators for scales, chords, and arpeggios."""

import random
from typing import Dict, List, Union, Optional
from fl_studio_mcp.models import note_name_to_pitch

SCALES: Dict[str, List[int]] = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "natural_minor": [0, 2, 3, 5, 7, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
    "pentatonic_major": [0, 2, 4, 7, 9],
    "pentatonic_minor": [0, 3, 5, 7, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "locrian": [0, 1, 3, 5, 6, 8, 10],
    "chromatic": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "whole_tone": [0, 2, 4, 6, 8, 10],
}

CHORDS: Dict[str, List[int]] = {
    "major": [0, 4, 7],
    "minor": [0, 3, 7],
    "diminished": [0, 3, 6],
    "augmented": [0, 4, 8],
    "major7": [0, 4, 7, 11],
    "minor7": [0, 3, 7, 10],
    "dominant7": [0, 4, 7, 10],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
}

RHYTHMS: Dict[str, int] = {
    "whole": 384,
    "half": 192,
    "quarter": 96,
    "eighth": 48,
    "sixteenth": 24,
    "triplet_quarter": 64,
    "triplet_eighth": 32,
}


def rhythm_to_ticks(rhythm: str) -> int:
    """Parse a rhythm name string to its tick duration (based on 96 ticks per beat)."""
    norm = rhythm.strip().lower()
    if norm in RHYTHMS:
        return RHYTHMS[norm]
    # Fallback to int parsing if passed directly
    try:
        return int(rhythm)
    except ValueError:
        raise ValueError(
            f"Invalid rhythm string: {rhythm!r}. Supported values: "
            f"{', '.join(RHYTHMS.keys())} or an integer tick count."
        )


def generate_scale_notes(
    root: Union[int, str], scale_name: str, octaves: int = 1
) -> List[int]:
    """Generate a list of MIDI pitch integers for a scale starting at root.

    Includes the resolution note of the final octave.
    """
    if isinstance(root, str):
        root_pitch = note_name_to_pitch(root)
    else:
        root_pitch = root

    norm_scale = scale_name.strip().lower().replace(" ", "_")
    if norm_scale not in SCALES:
        raise ValueError(
            f"Unsupported scale: {scale_name!r}. Supported scales: {', '.join(SCALES.keys())}"
        )

    if octaves < 1 or octaves > 8:
        raise ValueError("octaves must be between 1 and 8")

    intervals = SCALES[norm_scale]
    pitches = []
    for oct_idx in range(octaves):
        offset = oct_idx * 12
        for interval in intervals:
            p = root_pitch + offset + interval
            if 0 <= p <= 127:
                pitches.append(p)

    # Complete scale resolution
    resolved_pitch = root_pitch + octaves * 12
    if 0 <= resolved_pitch <= 127:
        pitches.append(resolved_pitch)

    return pitches


def generate_chord_pitches(
    root: Union[int, str], chord_type: str, octaves: int = 1
) -> List[int]:
    """Generate a list of MIDI pitch integers for a chord starting at root."""
    if isinstance(root, str):
        root_pitch = note_name_to_pitch(root)
    else:
        root_pitch = root

    norm_chord = chord_type.strip().lower().replace(" ", "_")
    if norm_chord not in CHORDS:
        raise ValueError(
            f"Unsupported chord type: {chord_type!r}. Supported chord types: {', '.join(CHORDS.keys())}"
        )

    if octaves < 1 or octaves > 8:
        raise ValueError("octaves must be between 1 and 8")

    intervals = CHORDS[norm_chord]
    pitches = []
    for oct_idx in range(octaves):
        offset = oct_idx * 12
        for interval in intervals:
            p = root_pitch + offset + interval
            if 0 <= p <= 127:
                pitches.append(p)
    return pitches


def apply_composition_modifiers(
    note_dicts: list[dict], velocity_curve: str, swing: float
) -> list[dict]:
    """Apply velocity curves and swing quantization to list of note dicts.

    velocity_curve can be: 'none', 'humanize', 'crescendo', 'decrescendo'.
    swing is a factor between 0.0 and 1.0 that shifts even subdivisions.
    """
    import random

    n = len(note_dicts)
    if n > 0:
        vel_mode = velocity_curve.strip().lower()
        if vel_mode == "humanize":
            for note in note_dicts:
                offset = random.randint(-15, 15)
                note["velocity"] = max(1, min(127, note["velocity"] + offset))
        elif vel_mode == "crescendo":
            for idx, note in enumerate(note_dicts):
                if n == 1:
                    note["velocity"] = 127
                else:
                    note["velocity"] = int(50 + (idx / (n - 1)) * (127 - 50))
        elif vel_mode == "decrescendo":
            for idx, note in enumerate(note_dicts):
                if n == 1:
                    note["velocity"] = 50
                else:
                    note["velocity"] = int(127 - (idx / (n - 1)) * (127 - 50))

    # 2. Apply swing quantization
    if swing > 0.0:
        grid_ticks = 24  # Sixteenth note division (96 PPQ / 4 = 24 ticks)
        shift_ticks = int(round(swing * (grid_ticks / 2)))  # up to 12 ticks
        for note in note_dicts:
            step_idx = note["start_tick"] // grid_ticks
            if step_idx % 2 == 1:
                note["start_tick"] += shift_ticks

    # 3. Sort chronologically by start_tick (with tie-breakers for stable order)
    note_dicts.sort(
        key=lambda x: (x.get("start_tick", 0), x.get("channel", 0), x.get("pitch", 0))
    )

    return note_dicts


def generate_euclidean_rhythm(hits: int, steps: int, rotation: int = 0) -> List[int]:
    """Distribute k hits across n steps as evenly as possible using Bresenham/Euclidean spacing."""
    if steps <= 0:
        return []
    hits = max(0, min(hits, steps))
    if hits == 0:
        return [0] * steps

    # Generate base sequence
    pattern = [1 if ((i * hits) % steps) < hits else 0 for i in range(steps)]

    # Apply circular shift rotation
    if rotation != 0:
        rotation = rotation % steps
        pattern = pattern[-rotation:] + pattern[:-rotation]

    return pattern


def generate_markov_melody(
    root: str,
    scale: str,
    length: int = 16,
    start_pitch: Optional[Union[int, str]] = None,
) -> List[int]:
    """Generate a sequence of MIDI pitches using a scale-constrained Markov chain."""
    # 1. Generate available scale pitches over 2 octaves
    scale_pitches = generate_scale_notes(root, scale, octaves=2)
    if not scale_pitches:
        return []

    # Remove duplicates and sort
    scale_pitches = sorted(list(set(scale_pitches)))

    # 2. Determine start index
    if start_pitch is not None:
        if isinstance(start_pitch, str):
            start_val = note_name_to_pitch(start_pitch)
        else:
            start_val = start_pitch
        # Find closest pitch in scale
        curr_idx = min(
            range(len(scale_pitches)), key=lambda i: abs(scale_pitches[i] - start_val)
        )
    else:
        curr_idx = 0  # Root note

    melody = [scale_pitches[curr_idx]]

    # 3. Transition rules
    # 7-degree transition matrix
    matrix = [
        [0.1, 0.3, 0.1, 0.1, 0.3, 0.0, 0.1],  # 0 -> 2nd, 5th preferred
        [0.2, 0.1, 0.3, 0.1, 0.1, 0.1, 0.1],  # 1 -> 3rd preferred
        [0.1, 0.1, 0.1, 0.3, 0.2, 0.1, 0.1],  # 2 -> 4th preferred
        [0.1, 0.1, 0.2, 0.1, 0.3, 0.1, 0.1],  # 3 -> 5th preferred
        [0.3, 0.0, 0.1, 0.1, 0.1, 0.2, 0.2],  # 4 -> root/6th/7th preferred
        [0.1, 0.1, 0.1, 0.2, 0.3, 0.1, 0.1],  # 5 -> 5th preferred
        [0.5, 0.1, 0.0, 0.1, 0.1, 0.1, 0.1],  # 6 -> root resolution
    ]

    for _ in range(length - 1):
        current_degree = curr_idx % 7
        probs = matrix[current_degree]

        # Choose next scale degree index
        r = random.random()
        cumulative = 0.0
        next_degree = 0
        for idx, p in enumerate(probs):
            cumulative += p
            if r <= cumulative:
                next_degree = idx
                break

        # Move curr_idx towards next_degree in current or adjacent octave
        # Ensure we stay within scale_pitches boundaries
        current_octave = curr_idx // 7
        candidate_idx = current_octave * 7 + next_degree
        if candidate_idx >= len(scale_pitches):
            candidate_idx = next_degree  # Reset to base octave if out of bounds

        curr_idx = max(0, min(candidate_idx, len(scale_pitches) - 1))
        melody.append(scale_pitches[curr_idx])

    return melody


def optimize_voice_leading(chords_pitches: List[List[int]]) -> List[List[int]]:
    """Adjust octave/inversion of consecutive chords to minimize absolute pitch transitions."""
    if not chords_pitches:
        return []

    optimized = [sorted(chords_pitches[0])]

    for i in range(1, len(chords_pitches)):
        prev_chord = optimized[-1]
        curr_chord = chords_pitches[i]

        new_chord = []
        for pitch in curr_chord:
            # Find closest pitch in prev_chord
            closest_target = min(prev_chord, key=lambda p: abs(p - pitch))
            # Calculate octave shift that gets closest to that target note
            octave_shift = int(round((closest_target - pitch) / 12.0)) * 12
            new_pitch = pitch + octave_shift
            # Constrain within valid MIDI boundaries
            new_pitch = max(0, min(127, new_pitch))
            new_chord.append(new_pitch)

        optimized.append(sorted(new_chord))

    return optimized
