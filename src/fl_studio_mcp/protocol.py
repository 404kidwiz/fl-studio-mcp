"""MIDI protocol encoding/decoding for the FL MCP bridge.

Custom SysEx format (manufacturer ID 0x7D = "non-commercial"):
    F0 7D <cmd> [payload...] F7

Commands
--------
0x01  play       no payload
0x02  stop       no payload
0x03  set_tempo  payload: [BPM_HI, BPM_LO]  (7-bit encoded, value = hi<<7 | lo)
0x04  notes      payload: N * 9 bytes per note (see encode_note_payload)
0x05  save_as    payload: ASCII bytes of filename (7-bit safe — no 0x80+)

MMC (MIDI Machine Control) is used for play/stop as a fallback because FL
Studio responds to it natively even without the controller script loaded.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# SysEx framing
_SYSEX_START = 0xF0
_SYSEX_END = 0xF7
_MANUFACTURER_ID = 0x7D  # non-commercial / development

# Command IDs
CMD_PLAY = 0x01
CMD_STOP = 0x02
CMD_SET_TEMPO = 0x03
CMD_NOTES = 0x04
CMD_SAVE_AS = 0x05

# MMC device ID 0x7F = "all devices"
_MMC_PLAY  = bytes([0xF0, 0x7F, 0x7F, 0x06, 0x02, 0xF7])
_MMC_STOP  = bytes([0xF0, 0x7F, 0x7F, 0x06, 0x01, 0xF7])


def mmc_play() -> bytes:
    return _MMC_PLAY


def mmc_stop() -> bytes:
    return _MMC_STOP


def _sysex(cmd: int, payload: list[int]) -> bytes:
    """Wrap command + payload in SysEx framing."""
    data = [_SYSEX_START, _MANUFACTURER_ID, cmd] + payload + [_SYSEX_END]
    # Sanity: all data bytes must be 0-127
    for i, b in enumerate(data[1:-1]):
        if b > 0x7F:
            raise ValueError(f"SysEx data byte at index {i+1} out of range: {b:#x}")
    return bytes(data)


def encode_tempo(bpm: int) -> bytes:
    """Encode a BPM value (20–999) as a two-byte 7-bit pair."""
    if not 20 <= bpm <= 999:
        raise ValueError(f"BPM must be 20–999, got {bpm}")
    hi = (bpm >> 7) & 0x7F
    lo = bpm & 0x7F
    return _sysex(CMD_SET_TEMPO, [hi, lo])


def decode_tempo(payload: list[int]) -> int:
    """Decode [hi, lo] → BPM."""
    return (payload[0] << 7) | payload[1]


def _encode_tick(value: int) -> list[int]:
    """Encode a tick value into 3 × 7-bit bytes (max 2,097,151 ticks)."""
    if value < 0:
        raise ValueError(f"Tick value must be >= 0, got {value}")
    b2 = (value >> 14) & 0x7F
    b1 = (value >> 7) & 0x7F
    b0 = value & 0x7F
    return [b2, b1, b0]


def _decode_tick(b2: int, b1: int, b0: int) -> int:
    return (b2 << 14) | (b1 << 7) | b0


def encode_notes(notes: list[dict]) -> bytes:
    """Encode a list of note dicts into a CMD_NOTES SysEx message.

    Each note is 9 bytes:
      [pitch, velocity, channel, start_b2, start_b1, start_b0, dur_b2, dur_b1, dur_b0]
    """
    payload: list[int] = []
    for n in notes:
        payload.append(int(n["pitch"]) & 0x7F)
        payload.append(int(n["velocity"]) & 0x7F)
        payload.append(int(n["channel"]) & 0x0F)
        payload.extend(_encode_tick(int(n["start_tick"])))
        payload.extend(_encode_tick(int(n["duration_ticks"])))
    return _sysex(CMD_NOTES, payload)


def decode_notes(payload: list[int]) -> list[dict]:
    """Inverse of encode_notes — used by the FL Studio controller script."""
    if len(payload) % 9 != 0:
        raise ValueError(f"Notes payload length {len(payload)} is not a multiple of 9")
    notes = []
    for i in range(0, len(payload), 9):
        notes.append({
            "pitch":          payload[i],
            "velocity":       payload[i + 1],
            "channel":        payload[i + 2],
            "start_tick":     _decode_tick(payload[i+3], payload[i+4], payload[i+5]),
            "duration_ticks": _decode_tick(payload[i+6], payload[i+7], payload[i+8]),
        })
    return notes


def encode_save_as(filename: str) -> bytes:
    """Encode a filename string as ASCII bytes in a CMD_SAVE_AS SysEx message."""
    encoded = [ord(c) for c in filename]
    for c in encoded:
        if c > 127:
            raise ValueError(f"Non-ASCII character in filename: chr({c})")
    return _sysex(CMD_SAVE_AS, encoded)


def decode_sysex(raw: bytes) -> tuple[int, list[int]] | None:
    """Parse raw SysEx bytes.

    Returns (cmd, payload) for FL-MCP messages, or None if not ours.
    """
    if len(raw) < 4:
        return None
    if raw[0] != _SYSEX_START or raw[-1] != _SYSEX_END:
        return None
    if raw[1] != _MANUFACTURER_ID:
        return None
    cmd = raw[2]
    payload = list(raw[3:-1])
    return cmd, payload
