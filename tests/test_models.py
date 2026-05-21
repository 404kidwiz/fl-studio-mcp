"""Unit tests for models, protocol encoding, and music theory helpers."""

import pytest

from fl_studio_mcp.models import (
    AddChordProgressionInput,
    ChordQuality,
    ChordStep,
    Note,
    SaveProjectInput,
    build_chord_notes,
)
from fl_studio_mcp.protocol import (
    decode_notes,
    decode_sysex,
    decode_tempo,
    encode_notes,
    encode_save,
    encode_tempo,
    mmc_play,
    mmc_stop,
)


# ---------------------------------------------------------------------------
# Note model validation
# ---------------------------------------------------------------------------

class TestNoteModel:
    def test_defaults(self):
        n = Note(pitch=60)
        assert n.velocity == 100
        assert n.start_tick == 0
        assert n.duration_ticks == 96
        assert n.channel == 0

    def test_pitch_bounds(self):
        Note(pitch=0)
        Note(pitch=127)
        with pytest.raises(Exception):
            Note(pitch=128)
        with pytest.raises(Exception):
            Note(pitch=-1)

    def test_velocity_zero_rejected(self):
        with pytest.raises(Exception):
            Note(pitch=60, velocity=0)

    def test_extra_fields_rejected(self):
        with pytest.raises(Exception):
            Note(pitch=60, unknown_field="x")

    def test_float_coercion(self):
        n = Note(pitch=60.9, velocity=100.0)
        assert n.pitch == 60
        assert n.velocity == 100


# ---------------------------------------------------------------------------
# Protocol: MMC messages
# ---------------------------------------------------------------------------

class TestMMC:
    def test_play_bytes(self):
        assert mmc_play() == bytes([0xF0, 0x7F, 0x7F, 0x06, 0x02, 0xF7])

    def test_stop_bytes(self):
        assert mmc_stop() == bytes([0xF0, 0x7F, 0x7F, 0x06, 0x01, 0xF7])


# ---------------------------------------------------------------------------
# Protocol: tempo encoding
# ---------------------------------------------------------------------------

class TestTempoProtocol:
    @pytest.mark.parametrize("bpm", [20, 60, 120, 140, 180, 999])
    def test_roundtrip(self, bpm):
        encoded = encode_tempo(bpm)
        cmd, payload = decode_sysex(encoded)
        assert cmd == 0x03
        assert decode_tempo(payload) == bpm

    def test_out_of_range(self):
        with pytest.raises(ValueError):
            encode_tempo(19)
        with pytest.raises(ValueError):
            encode_tempo(1000)

    def test_sysex_framing(self):
        raw = encode_tempo(120)
        assert raw[0] == 0xF0
        assert raw[-1] == 0xF7
        assert raw[1] == 0x7D  # manufacturer ID

    def test_all_bytes_7bit(self):
        raw = encode_tempo(999)
        for b in raw[1:-1]:  # skip F0 and F7
            assert b <= 0x7F, f"Byte {b:#x} exceeds 7-bit range"


# ---------------------------------------------------------------------------
# Protocol: note encoding
# ---------------------------------------------------------------------------

class TestNotesProtocol:
    def _make_note(self, **kwargs):
        defaults = dict(pitch=60, velocity=100, channel=0, start_tick=0, duration_ticks=96)
        defaults.update(kwargs)
        return defaults

    def test_single_note_roundtrip(self):
        note = self._make_note(pitch=60, velocity=90, channel=1, start_tick=192, duration_ticks=48)
        encoded = encode_notes([note])
        cmd, payload = decode_sysex(encoded)
        assert cmd == 0x04
        decoded = decode_notes(payload)
        assert len(decoded) == 1
        assert decoded[0] == note

    def test_multiple_notes_roundtrip(self):
        notes = [
            self._make_note(pitch=60, start_tick=0,   duration_ticks=96),
            self._make_note(pitch=64, start_tick=96,  duration_ticks=96),
            self._make_note(pitch=67, start_tick=192, duration_ticks=96),
        ]
        encoded = encode_notes(notes)
        _, payload = decode_sysex(encoded)
        decoded = decode_notes(payload)
        assert decoded == notes

    def test_large_tick_values(self):
        # start_tick at 2 million — exercises 3-byte encoding
        note = self._make_note(start_tick=2_000_000, duration_ticks=384)
        encoded = encode_notes([note])
        _, payload = decode_sysex(encoded)
        decoded = decode_notes(payload)
        assert decoded[0]["start_tick"] == 2_000_000

    def test_all_bytes_7bit(self):
        note = self._make_note(pitch=127, velocity=127, channel=15, start_tick=99999, duration_ticks=384)
        raw = encode_notes([note])
        for b in raw[1:-1]:
            assert b <= 0x7F

    def test_bad_payload_length(self):
        with pytest.raises(ValueError):
            decode_notes([1, 2, 3])  # not multiple of 9


# ---------------------------------------------------------------------------
# Protocol: save encoding
# ---------------------------------------------------------------------------

class TestSaveProtocol:
    def test_save_command_byte(self):
        raw = encode_save()
        cmd, payload = decode_sysex(raw)
        assert cmd == 0x05
        assert payload == []  # no payload — just triggers ui.save()

    def test_save_framing(self):
        raw = encode_save()
        assert raw[0] == 0xF0
        assert raw[-1] == 0xF7
        assert raw[1] == 0x7D


# ---------------------------------------------------------------------------
# Model: SaveProjectInput (no filename field)
# ---------------------------------------------------------------------------

class TestSaveProjectInput:
    def test_empty_input_accepted(self):
        SaveProjectInput()  # no fields needed

    def test_extra_fields_rejected(self):
        with pytest.raises(Exception):
            SaveProjectInput(filename="should_not_exist")


# ---------------------------------------------------------------------------
# Chord / progression tests
# ---------------------------------------------------------------------------

class TestChordProgression:
    def test_build_chord_notes_major(self):
        notes = build_chord_notes(
            root_pitch=60,
            quality=ChordQuality.MAJOR,
            velocity=100,
            start_tick=0,
            duration_ticks=384,
            channel=0,
        )
        assert len(notes) == 3
        # C major is C (60), E (64), G (67)
        assert [n.pitch for n in notes] == [60, 64, 67]
        for n in notes:
            assert n.velocity == 100
            assert n.start_tick == 0
            assert n.duration_ticks == 384
            assert n.channel == 0

    def test_chord_step_validation(self):
        cs = ChordStep(root_pitch="C4", quality="minor")
        assert cs.root_pitch == 60
        assert cs.quality == ChordQuality.MINOR

        with pytest.raises(Exception):
            ChordStep(root_pitch=128)

