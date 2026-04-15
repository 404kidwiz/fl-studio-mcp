"""MIDI protocol encoding/decoding for the FL MCP bridge.

Custom SysEx format (manufacturer ID 0x7D = "non-commercial"):
    F0 7D <cmd> [payload...] F7

Server → FL Studio commands
---------------------------
0x01  play              no payload
0x02  stop              no payload
0x03  set_tempo         [BPM_HI, BPM_LO]  (7-bit encoded, value = hi<<7 | lo)
0x04  notes             N × 9 bytes per note
0x05  save_as           ASCII filename bytes
0x06  query_status      no payload  → FL responds with RESP_STATUS (0x10)
0x07  query_channels    no payload  → FL responds with RESP_CHANNELS (0x11)
0x08  set_channel_vol   [ch_idx, volume]  (both 0-127)
0x09  new_pattern       no payload
0x0A  select_pattern    [pat_idx]
0x0B  (reserved — panic is pure MIDI CC, no SysEx needed)
0x0C  query_patterns    no payload  → FL responds with RESP_PATTERNS (0x12)
0x0D  mute_channel      [ch_idx, is_muted(0|1)]
0x0E  solo_channel      [ch_idx, is_soloed(0|1)]

FL Studio → Server responses
-----------------------------
0x10  resp_status    [playing, bpm_hi, bpm_lo, pat_idx, ch_count]
0x11  resp_channels  [count, name_len, name_bytes... × count]
0x12  resp_patterns  [count, name_len, name_bytes... × count]

Panic:
    Standard MIDI CC 120 (All Sound Off) + CC 123 (All Notes Off) sent
    directly on all 16 channels — no SysEx or FL Studio script required.

MMC (MIDI Machine Control) is used for play/stop as a fallback because FL
Studio responds to it natively even without the controller script loaded.
"""

from __future__ import annotations

# SysEx framing
_SYSEX_START = 0xF0
_SYSEX_END = 0xF7
_MANUFACTURER_ID = 0x7D  # non-commercial / development

# Server → FL Studio commands
CMD_PLAY             = 0x01
CMD_STOP             = 0x02
CMD_SET_TEMPO        = 0x03
CMD_NOTES            = 0x04
CMD_SAVE_AS          = 0x05
CMD_QUERY_STATUS     = 0x06
CMD_QUERY_CHANNELS   = 0x07
CMD_SET_CHANNEL_VOL  = 0x08
CMD_NEW_PATTERN      = 0x09
CMD_SELECT_PATTERN   = 0x0A
# 0x0B reserved
CMD_QUERY_PATTERNS   = 0x0C
CMD_MUTE_CHANNEL     = 0x0D
CMD_SOLO_CHANNEL     = 0x0E
CMD_CLEAR_PATTERN    = 0x0F   # no payload — clears current pattern
CMD_SET_CHANNEL_PAN  = 0x13   # [ch_idx, pan] both 0-127; 64 = centre

# FL Studio → Server responses  (0x10-0x1F reserved for responses)
RESP_STATUS   = 0x10
RESP_CHANNELS = 0x11
RESP_PATTERNS = 0x12

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


# ---------------------------------------------------------------------------
# New query encoders
# ---------------------------------------------------------------------------

def encode_query_status() -> bytes:
    return _sysex(CMD_QUERY_STATUS, [])


def encode_query_channels() -> bytes:
    return _sysex(CMD_QUERY_CHANNELS, [])


def encode_set_channel_vol(channel_idx: int, volume: int) -> bytes:
    if not 0 <= channel_idx <= 127:
        raise ValueError(f"channel_idx must be 0-127, got {channel_idx}")
    if not 0 <= volume <= 127:
        raise ValueError(f"volume must be 0-127, got {volume}")
    return _sysex(CMD_SET_CHANNEL_VOL, [channel_idx, volume])


def encode_new_pattern() -> bytes:
    return _sysex(CMD_NEW_PATTERN, [])


def encode_select_pattern(pattern_idx: int) -> bytes:
    if not 0 <= pattern_idx <= 127:
        raise ValueError(f"pattern_idx must be 0-127, got {pattern_idx}")
    return _sysex(CMD_SELECT_PATTERN, [pattern_idx])


# ---------------------------------------------------------------------------
# Response decoders  (FL Studio → MCP server)
# ---------------------------------------------------------------------------

def decode_resp_status(payload: list[int]) -> dict:
    """Decode a RESP_STATUS payload.

    Format: [playing, bpm_hi, bpm_lo, pat_idx, ch_count]
    """
    if len(payload) < 5:
        raise ValueError(f"RESP_STATUS payload too short: {len(payload)} bytes")
    return {
        "playing":       bool(payload[0]),
        "bpm":           decode_tempo(payload[1:3]),
        "pattern_index": payload[3],
        "channel_count": payload[4],
    }


def encode_resp_status(playing: bool, bpm: int, pattern_index: int, channel_count: int) -> bytes:
    """Build a RESP_STATUS message (used by FL Studio script to respond)."""
    bpm_hi = (bpm >> 7) & 0x7F
    bpm_lo = bpm & 0x7F
    return _sysex(RESP_STATUS, [int(playing), bpm_hi, bpm_lo, pattern_index & 0x7F, channel_count & 0x7F])


def decode_resp_channels(payload: list[int]) -> list[str]:
    """Decode a RESP_CHANNELS payload into a list of channel name strings.

    Format: [count, name_len_0, name_bytes_0..., name_len_1, name_bytes_1..., ...]
    """
    if not payload:
        return []
    count = payload[0]
    names: list[str] = []
    i = 1
    while len(names) < count and i < len(payload):
        name_len = payload[i]
        i += 1
        name_bytes = payload[i : i + name_len]
        i += name_len
        names.append("".join(chr(b) for b in name_bytes))
    return names


def encode_resp_channels(names: list[str]) -> bytes:
    """Build a RESP_CHANNELS message (used by FL Studio script to respond).

    Channel names are truncated to 14 chars and filtered to 7-bit ASCII.
    """
    payload: list[int] = [min(len(names), 127)]
    for name in names[:127]:
        safe = [ord(c) for c in name[:14] if ord(c) <= 127]
        payload.append(len(safe))
        payload.extend(safe)
    return _sysex(RESP_CHANNELS, payload)


# ---------------------------------------------------------------------------
# Pattern list (mirrors channel encoding, different cmd/resp bytes)
# ---------------------------------------------------------------------------

def encode_query_patterns() -> bytes:
    return _sysex(CMD_QUERY_PATTERNS, [])


def decode_resp_patterns(payload: list[int]) -> list[str]:
    """Decode RESP_PATTERNS payload → list of pattern name strings."""
    # Same wire format as RESP_CHANNELS
    return decode_resp_channels(payload)


def encode_resp_patterns(names: list[str]) -> bytes:
    """Build a RESP_PATTERNS message (used by FL Studio script)."""
    payload: list[int] = [min(len(names), 127)]
    for name in names[:127]:
        safe = [ord(c) for c in name[:14] if ord(c) <= 127]
        payload.append(len(safe))
        payload.extend(safe)
    return _sysex(RESP_PATTERNS, payload)


# ---------------------------------------------------------------------------
# Mute / Solo
# ---------------------------------------------------------------------------

def encode_mute_channel(channel_idx: int, muted: bool) -> bytes:
    if not 0 <= channel_idx <= 127:
        raise ValueError(f"channel_idx must be 0-127, got {channel_idx}")
    return _sysex(CMD_MUTE_CHANNEL, [channel_idx, int(muted)])


def encode_solo_channel(channel_idx: int, soloed: bool) -> bytes:
    if not 0 <= channel_idx <= 127:
        raise ValueError(f"channel_idx must be 0-127, got {channel_idx}")
    return _sysex(CMD_SOLO_CHANNEL, [channel_idx, int(soloed)])


# ---------------------------------------------------------------------------
# Clear pattern / channel pan
# ---------------------------------------------------------------------------

def encode_clear_pattern() -> bytes:
    """Send CMD_CLEAR_PATTERN — erases all notes from the current pattern."""
    return _sysex(CMD_CLEAR_PATTERN, [])


def encode_set_channel_pan(channel_idx: int, pan: int) -> bytes:
    """Encode a set-channel-pan command.

    pan: 0 = full left, 64 = centre, 127 = full right.
    FL Studio internally maps 0-127 → -1.0..+1.0 with 64 = 0.
    """
    if not 0 <= channel_idx <= 127:
        raise ValueError(f"channel_idx must be 0-127, got {channel_idx}")
    if not 0 <= pan <= 127:
        raise ValueError(f"pan must be 0-127, got {pan}")
    return _sysex(CMD_SET_CHANNEL_PAN, [channel_idx, pan])


# ---------------------------------------------------------------------------
# Panic helpers (pure MIDI CC — no SysEx, no FL Studio script needed)
# ---------------------------------------------------------------------------

def panic_messages() -> list[bytes]:
    """Return all-notes-off + all-sound-off CC messages for all 16 channels.

    Each tuple is a raw MIDI byte sequence ready for mido.Message.from_bytes().
    """
    msgs: list[bytes] = []
    for ch in range(16):
        status = 0xB0 | ch  # Control Change on channel ch
        msgs.append(bytes([status, 123, 0]))  # All Notes Off
        msgs.append(bytes([status, 120, 0]))  # All Sound Off
        msgs.append(bytes([status, 121, 0]))  # Reset All Controllers
    return msgs
