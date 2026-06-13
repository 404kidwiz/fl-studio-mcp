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


def validate_color(r: int, g: int, b: int) -> None:
    """Validate each RGB component is in 0–255 range."""
    if not all(0 <= c <= 255 for c in (r, g, b)):
        raise ValueError("color components must be 0-255")

# Server → FL Studio commands
CMD_PLAY = 0x01
CMD_STOP = 0x02
CMD_SET_TEMPO = 0x03
CMD_NOTES = 0x04
CMD_SAVE = 0x05
CMD_QUERY_STATUS = 0x06
CMD_QUERY_CHANNELS = 0x07
CMD_SET_CHANNEL_VOL = 0x08
CMD_NEW_PATTERN = 0x09
CMD_SELECT_PATTERN = 0x0A
# 0x0B reserved
CMD_QUERY_PATTERNS = 0x0C
CMD_MUTE_CHANNEL = 0x0D
CMD_SOLO_CHANNEL = 0x0E
# 0x0F removed in v1.4 (patterns.clearCurrentPattern does not exist in FL API)
CMD_SET_CHANNEL_PAN = 0x13  # [ch_idx, pan] both 0-127; 64 = centre
CMD_GET_NOTES = 0x14
CMD_SET_PATTERN_LENGTH = 0x15
CMD_RENAME_CHANNEL = 0x16
CMD_RENAME_PATTERN = 0x17
CMD_PING = 0x18
CMD_SET_MIXER_VOL = 0x19
CMD_SET_MIXER_PAN = 0x1A
CMD_ROUTE_TO_MIXER = 0x1B
CMD_QUERY_MIXER_STATE = 0x1C
CMD_UNDO = 0x1D
CMD_REDO = 0x1E

# Phase 4 Extensions
CMD_SET_PLUGIN_PARAM = 0x20
CMD_GET_PLUGIN_PARAM = 0x21
CMD_SHOW_WINDOW = 0x22
CMD_ADD_MARKER = 0x23
RESP_PLUGIN_PARAM = 0x24
CMD_GET_PEAKS = 0x25
RESP_PEAKS = 0x26
CMD_BROWSER_NAV = 0x27

# Phase 6 Enhancements
CMD_SET_GRID_BIT = 0x28
CMD_MUTE_PLAYLIST_TRACK = 0x29
CMD_SOLO_PLAYLIST_TRACK = 0x2A
CMD_SET_TIME_SELECTION = 0x2B
CMD_SET_CHANNEL_COLOR = 0x2C
CMD_SET_PATTERN_COLOR = 0x2D

# Phase 7 Enhancements
CMD_SET_CHANNEL_NAME = 0x2E
CMD_SET_CHANNEL_MIXER_TRACK = 0x2F
CMD_UI_NAVIGATE = 0x30

# FL Studio → Server responses  (0x10-0x1F, 0x24-0x2F reserved for responses)
RESP_STATUS = 0x10
RESP_CHANNELS = 0x11
RESP_PATTERNS = 0x12
RESP_NOTES = 0x14
RESP_MIXER_STATE = 0x1C
RESP_ACK = 0x1F
RESP_PLUGIN_PARAM = 0x24

# Song/Project Management Commands
CMD_ADD_MARKER = 0x2B
CMD_DELETE_MARKER = 0x2C
CMD_GET_MARKER = 0x2D
CMD_INSERT_MARKER = 0x2E
CMD_SET_TEMPO_RELATIVE = 0x2F
CMD_GET_BPM = 0x30
CMD_SAVE_AS = 0x31
CMD_EXPORT_AUDIO = 0x32
CMD_SELECT_PATTERN = 0x0A
CMD_NEW_PATTERN = 0x09
CMD_DUPLICATE_PATTERN = 0x35
CMD_COPY_PATTERN = 0x36
CMD_CUT_PATTERN = 0x37
CMD_PASTE_PATTERN = 0x38
CMD_CLEAR_PATTERN = 0x39

# MMC device ID 0x7F = "all devices"
_MMC_PLAY = bytes([0xF0, 0x7F, 0x7F, 0x06, 0x02, 0xF7])
_MMC_STOP = bytes([0xF0, 0x7F, 0x7F, 0x06, 0x01, 0xF7])


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
        notes.append(
            {
                "pitch": payload[i],
                "velocity": payload[i + 1],
                "channel": payload[i + 2],
                "start_tick": _decode_tick(
                    payload[i + 3], payload[i + 4], payload[i + 5]
                ),
                "duration_ticks": _decode_tick(
                    payload[i + 6], payload[i + 7], payload[i + 8]
                ),
            }
        )
    return notes


def encode_save() -> bytes:
    """Encode a CMD_SAVE SysEx message (no payload — triggers ui.save())."""
    return _sysex(CMD_SAVE, [])


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
        "playing": bool(payload[0]),
        "bpm": decode_tempo(payload[1:3]),
        "pattern_index": payload[3],
        "channel_count": payload[4],
    }


def encode_resp_status(
    playing: bool, bpm: int, pattern_index: int, channel_count: int
) -> bytes:
    """Build a RESP_STATUS message (used by FL Studio script to respond)."""
    bpm_hi = (bpm >> 7) & 0x7F
    bpm_lo = bpm & 0x7F
    return _sysex(
        RESP_STATUS,
        [int(playing), bpm_hi, bpm_lo, pattern_index & 0x7F, channel_count & 0x7F],
    )


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


def encode_get_notes() -> bytes:
    """Encode a CMD_GET_NOTES SysEx message (no payload)."""
    return _sysex(CMD_GET_NOTES, [])


def encode_set_pattern_length(pattern_idx: int, length_beats: int) -> bytes:
    """Encode CMD_SET_PATTERN_LENGTH SysEx message.

    Supports up to 999 patterns and 999 beats (split as 2 bytes: hi/lo 7-bit).
    """
    if not 0 <= pattern_idx <= 999:
        raise ValueError(f"pattern_idx must be 0-999, got {pattern_idx}")
    if not 1 <= length_beats <= 999:
        raise ValueError(f"length_beats must be 1-999, got {length_beats}")
    pat_hi = (pattern_idx >> 7) & 0x7F
    pat_lo = pattern_idx & 0x7F
    len_hi = (length_beats >> 7) & 0x7F
    len_lo = length_beats & 0x7F
    return _sysex(CMD_SET_PATTERN_LENGTH, [pat_hi, pat_lo, len_hi, len_lo])


def encode_rename_channel(channel_idx: int, name: str) -> bytes:
    """Encode CMD_RENAME_CHANNEL SysEx message.

    Limits name to 14 characters and 7-bit ASCII.
    """
    if not 0 <= channel_idx <= 127:
        raise ValueError(f"channel_idx must be 0-127, got {channel_idx}")
    safe = [ord(c) for c in name[:14] if ord(c) <= 127]
    return _sysex(CMD_RENAME_CHANNEL, [channel_idx, len(safe)] + safe)


def encode_rename_pattern(pattern_idx: int, name: str) -> bytes:
    """Encode CMD_RENAME_PATTERN SysEx message.

    Supports pattern_idx up to 999 (split into pat_hi/pat_lo),
    name limits to 14 characters and 7-bit ASCII.
    """
    if not 0 <= pattern_idx <= 999:
        raise ValueError(f"pattern_idx must be 0-999, got {pattern_idx}")
    pat_hi = (pattern_idx >> 7) & 0x7F
    pat_lo = pattern_idx & 0x7F
    safe = [ord(c) for c in name[:14] if ord(c) <= 127]
    return _sysex(CMD_RENAME_PATTERN, [pat_hi, pat_lo, len(safe)] + safe)


def decode_resp_notes(payload: list[int]) -> list[dict]:
    """Decode RESP_NOTES payload (delegates to decode_notes)."""
    return decode_notes(payload)


def encode_resp_notes(notes: list[dict]) -> bytes:
    """Encode a RESP_NOTES message (used by FL Studio script/bridge mock)."""
    payload: list[int] = []
    for n in notes:
        payload.append(int(n["pitch"]) & 0x7F)
        payload.append(int(n["velocity"]) & 0x7F)
        payload.append(int(n["channel"]) & 0x0F)
        payload.extend(_encode_tick(int(n["start_tick"])))
        payload.extend(_encode_tick(int(n["duration_ticks"])))
    return _sysex(RESP_NOTES, payload)


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


# ---------------------------------------------------------------------------
# Mixer & Routing (Sprint 4)
# ---------------------------------------------------------------------------


def encode_set_mixer_vol(track_idx: int, volume: int) -> bytes:
    if not 0 <= track_idx <= 127:
        raise ValueError(f"track_idx must be 0-127, got {track_idx}")
    if not 0 <= volume <= 127:
        raise ValueError(f"volume must be 0-127, got {volume}")
    return _sysex(CMD_SET_MIXER_VOL, [track_idx, volume])


def encode_set_mixer_pan(track_idx: int, pan: int) -> bytes:
    if not 0 <= track_idx <= 127:
        raise ValueError(f"track_idx must be 0-127, got {track_idx}")
    if not 0 <= pan <= 127:
        raise ValueError(f"pan must be 0-127, got {pan}")
    return _sysex(CMD_SET_MIXER_PAN, [track_idx, pan])


def encode_route_to_mixer(channel_idx: int, track_idx: int) -> bytes:
    if not 0 <= channel_idx <= 127:
        raise ValueError(f"channel_idx must be 0-127, got {channel_idx}")
    if not 0 <= track_idx <= 127:
        raise ValueError(f"track_idx must be 0-127, got {track_idx}")
    return _sysex(CMD_ROUTE_TO_MIXER, [channel_idx, track_idx])


def encode_query_mixer_state(start_track: int, end_track: int) -> bytes:
    if not 0 <= start_track <= 127:
        raise ValueError(f"start_track must be 0-127, got {start_track}")
    if not 0 <= end_track <= 127:
        raise ValueError(f"end_track must be 0-127, got {end_track}")
    if start_track > end_track:
        raise ValueError(
            f"start_track ({start_track}) cannot be greater than end_track ({end_track})"
        )
    if end_track - start_track >= 32:
        raise ValueError(
            f"Queried range exceeds maximum of 32 tracks: {end_track - start_track + 1}"
        )
    return _sysex(CMD_QUERY_MIXER_STATE, [start_track, end_track])


def decode_resp_mixer_state(payload: list[int]) -> dict:
    if len(payload) < 3:
        raise ValueError(f"RESP_MIXER_STATE payload too short: {len(payload)} bytes")
    start_track = payload[0]
    end_track = payload[1]
    count = payload[2]

    tracks = []
    i = 3
    while len(tracks) < count and i < len(payload):
        if i + 3 > len(payload):
            break
        vol = payload[i]
        pan = payload[i + 1]
        name_len = payload[i + 2]
        i += 3
        if i + name_len > len(payload):
            break
        name_bytes = payload[i : i + name_len]
        i += name_len
        name = "".join(chr(b) for b in name_bytes)
        tracks.append({"volume": vol, "pan": pan, "name": name})
    return {"start_track": start_track, "end_track": end_track, "tracks": tracks}


def encode_resp_mixer_state(
    start_track: int, end_track: int, tracks: list[dict]
) -> bytes:
    payload: list[int] = [start_track, end_track, len(tracks)]
    for t in tracks:
        vol = int(t.get("volume", 0)) & 0x7F
        pan = int(t.get("pan", 64)) & 0x7F
        name = t.get("name", "")
        safe = [ord(c) for c in name[:14] if ord(c) <= 127]
        payload.append(vol)
        payload.append(pan)
        payload.append(len(safe))
        payload.extend(safe)
    return _sysex(RESP_MIXER_STATE, payload)


def encode_undo() -> bytes:
    return _sysex(CMD_UNDO, [])


def encode_redo() -> bytes:
    return _sysex(CMD_REDO, [])


def encode_ping(challenge: int) -> bytes:
    if not 0 <= challenge <= 127:
        raise ValueError(f"challenge must be 0-127, got {challenge}")
    return _sysex(CMD_PING, [challenge])


def decode_resp_ack(payload: list[int]) -> int:
    if not payload:
        raise ValueError("RESP_ACK payload is empty")
    return payload[0]


def encode_resp_ack(cmd_byte: int) -> bytes:
    return _sysex(RESP_ACK, [cmd_byte & 0x7F])


# ---------------------------------------------------------------------------
# Phase 4: Plugin Parameters, UI Windows, Markers
# ---------------------------------------------------------------------------


def encode_set_plugin_param(target_type: int, track_or_chan_idx: int, slot_idx: int, param_idx: int, value: float) -> bytes:
    """Encode CMD_SET_PLUGIN_PARAM SysEx message.
    
    target_type: 0 for Mixer (Effect), 1 for Channel (Generator).
    track_or_chan_idx: mixer track index (if 0) or channel index (if 1).
    slot_idx: mixer slot index (0-9). Ignored if target_type is 1.
    param_idx: The index of the parameter to set (0-4095).
    value: float between 0.0 and 1.0. Encoded as 14-bit integer (0-16383).
    """
    if target_type not in (0, 1):
        raise ValueError("target_type must be 0 (Mixer) or 1 (Channel)")
    if not 0 <= param_idx <= 4095:
        raise ValueError(f"param_idx must be 0-4095, got {param_idx}")
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"value must be 0.0-1.0, got {value}")
        
    val_int = int(round(value * 16383))
    val_hi = (val_int >> 7) & 0x7F
    val_lo = val_int & 0x7F
    
    param_hi = (param_idx >> 7) & 0x7F
    param_lo = param_idx & 0x7F
    
    return _sysex(CMD_SET_PLUGIN_PARAM, [target_type, track_or_chan_idx & 0x7F, slot_idx & 0x7F, param_hi, param_lo, val_hi, val_lo])


def encode_get_plugin_param(target_type: int, track_or_chan_idx: int, slot_idx: int, param_idx: int) -> bytes:
    """Encode CMD_GET_PLUGIN_PARAM SysEx message."""
    if target_type not in (0, 1):
        raise ValueError("target_type must be 0 (Mixer) or 1 (Channel)")
    if not 0 <= param_idx <= 4095:
        raise ValueError(f"param_idx must be 0-4095, got {param_idx}")
        
    param_hi = (param_idx >> 7) & 0x7F
    param_lo = param_idx & 0x7F
    
    return _sysex(CMD_GET_PLUGIN_PARAM, [target_type, track_or_chan_idx & 0x7F, slot_idx & 0x7F, param_hi, param_lo])


def decode_resp_plugin_param(payload: list[int]) -> float:
    """Decode a RESP_PLUGIN_PARAM payload (2 bytes: val_hi, val_lo)."""
    if len(payload) < 2:
        raise ValueError("RESP_PLUGIN_PARAM payload too short")
    val_int = (payload[0] << 7) | payload[1]
    return val_int / 16383.0


def encode_resp_plugin_param(value: float) -> bytes:
    val_int = int(round(value * 16383))
    val_hi = (val_int >> 7) & 0x7F
    val_lo = val_int & 0x7F
    return _sysex(RESP_PLUGIN_PARAM, [val_hi, val_lo])


def encode_show_window(window_index: int) -> bytes:
    """Encode CMD_SHOW_WINDOW.
    window_index maps to standard FL Studio ui constants (e.g. 0=Mixer, 1=Channel Rack, 2=Playlist, 3=Piano Roll, 4=Browser).
    """
    return _sysex(CMD_SHOW_WINDOW, [window_index & 0x7F])


def encode_get_peaks(track_idx: int) -> bytes:
    """Encode CMD_GET_PEAKS."""
    return _sysex(CMD_GET_PEAKS, [track_idx & 0x7F])


def decode_resp_peaks(payload: list[int]) -> tuple[float, float]:
    """Decode a RESP_PEAKS payload (4 bytes: l_hi, l_lo, r_hi, r_lo)."""
    if len(payload) < 4:
        raise ValueError("RESP_PEAKS payload too short")
    l_int = (payload[0] << 7) | payload[1]
    r_int = (payload[2] << 7) | payload[3]
    return l_int / 16383.0, r_int / 16383.0


def encode_resp_peaks(l_peak: float, r_peak: float) -> bytes:
    l_int = int(round(max(0.0, min(1.0, l_peak)) * 16383))
    r_int = int(round(max(0.0, min(1.0, r_peak)) * 16383))
    l_hi = (l_int >> 7) & 0x7F
    l_lo = l_int & 0x7F
    r_hi = (r_int >> 7) & 0x7F
    r_lo = r_int & 0x7F
    return _sysex(RESP_PEAKS, [l_hi, l_lo, r_hi, r_lo])


def encode_browser_nav(action: int) -> bytes:
    """Encode CMD_BROWSER_NAV.
    action: 0=Up, 1=Down, 2=Left, 3=Right, 4=Enter
    """
    return _sysex(CMD_BROWSER_NAV, [action & 0x7F])


def encode_set_grid_bit(channel_idx: int, step_idx: int, value: int) -> bytes:
    if not 0 <= channel_idx <= 127:
        raise ValueError("channel_idx out of range")
    if not 0 <= step_idx <= 127:
        raise ValueError("step_idx out of range")
    return _sysex(CMD_SET_GRID_BIT, [channel_idx & 0x7F, step_idx & 0x7F, value & 0x7F])


def encode_mute_playlist_track(track_idx: int, muted: bool) -> bytes:
    if not 0 <= track_idx <= 127:
        raise ValueError("track_idx out of range")
    return _sysex(CMD_MUTE_PLAYLIST_TRACK, [track_idx & 0x7F, int(muted)])


def encode_solo_playlist_track(track_idx: int, soloed: bool) -> bytes:
    if not 0 <= track_idx <= 127:
        raise ValueError("track_idx out of range")
    return _sysex(CMD_SOLO_PLAYLIST_TRACK, [track_idx & 0x7F, int(soloed)])


def encode_set_time_selection(start_bar: int, end_bar: int) -> bytes:
    """Encode CMD_SET_TIME_SELECTION
    start_bar and end_bar can be up to 999. Sent as high/low bytes.
    """
    sb_hi = (start_bar >> 7) & 0x7F
    sb_lo = start_bar & 0x7F
    eb_hi = (end_bar >> 7) & 0x7F
    eb_lo = end_bar & 0x7F
    return _sysex(CMD_SET_TIME_SELECTION, [sb_hi, sb_lo, eb_hi, eb_lo])


# --- Phase 7 Functions ---

def encode_set_channel_name(channel_index: int, name: str) -> bytes:
    """Encode a SET_CHANNEL_NAME command.
    Payload: [ch_hi, ch_lo, ...string bytes...]
    """
    ch_hi = (channel_index >> 7) & 0x7F
    ch_lo = channel_index & 0x7F
    
    # Simple ASCII encoding, filtering non-7-bit characters for safety
    name_bytes = [ord(c) if ord(c) < 128 else 63 for c in name]
    return _sysex(CMD_SET_CHANNEL_NAME, [ch_hi, ch_lo] + name_bytes)


def encode_set_channel_mixer_track(channel_index: int, track_index: int) -> bytes:
    """Encode a SET_CHANNEL_MIXER_TRACK command."""
    ch_hi = (channel_index >> 7) & 0x7F
    ch_lo = channel_index & 0x7F
    tr_hi = (track_index >> 7) & 0x7F
    tr_lo = track_index & 0x7F
    return _sysex(CMD_SET_CHANNEL_MIXER_TRACK, [ch_hi, ch_lo, tr_hi, tr_lo])


def encode_ui_navigate(action_id: int) -> bytes:
    """Encode a UI_NAVIGATE command."""
    # action_id <= 127 is assumed
    return _sysex(CMD_UI_NAVIGATE, [action_id & 0x7F])


def encode_set_channel_color(channel_idx: int, r: int, g: int, b: int) -> bytes:
    """Color RGB must be 0-255. Split into 4-bit nibbles for 7-bit SysEx compliance."""
    if not 0 <= channel_idx <= 127:
        raise ValueError("channel_idx out of range")
    validate_color(r, g, b)
    return _sysex(CMD_SET_CHANNEL_COLOR, [
        channel_idx & 0x7F,
        (r >> 4) & 0x0F, r & 0x0F,
        (g >> 4) & 0x0F, g & 0x0F,
        (b >> 4) & 0x0F, b & 0x0F,
    ])


# --- Song/Project Management Functions ---


def encode_add_marker(marker_name: str, r: int, g: int, b: int) -> bytes:
    """Encode an ADD_MARKER command.
    
    Payload: [name_len, name_bytes..., r_hi, r_lo, g_hi, g_lo, b_hi, b_lo]
    Color components are split into 4-bit nibbles (2 bytes per component).
    """
    if not marker_name:
        raise ValueError("marker_name cannot be empty")
    if len(marker_name) > 127:
        raise ValueError("marker_name too long")
    validate_color(r, g, b)
    name_bytes = [ord(c) if ord(c) < 128 else 63 for c in marker_name]
    color_bytes = [
        (r >> 4) & 0x0F, r & 0x0F,
        (g >> 4) & 0x0F, g & 0x0F,
        (b >> 4) & 0x0F, b & 0x0F,
    ]
    return _sysex(CMD_ADD_MARKER, [len(name_bytes)] + name_bytes + color_bytes)


def encode_delete_marker(marker_index: int) -> bytes:
    """Encode a DELETE_MARKER command.
    
    Payload: [marker_index]
    """
    if not 0 <= marker_index <= 127:
        raise ValueError("marker_index out of range")
    return _sysex(CMD_DELETE_MARKER, [marker_index])


def encode_get_marker(marker_index: int) -> bytes:
    """Encode a GET_MARKER command.
    
    Payload: [marker_index]
    """
    if not 0 <= marker_index <= 127:
        raise ValueError("marker_index out of range")
    return _sysex(CMD_GET_MARKER, [marker_index])


def encode_insert_marker(position_beats: float, marker_name: str, r: int, g: int, b: int) -> bytes:
    """Encode an INSERT_MARKER command.
    
    Payload: [pos_hi, pos_lo, name_len, name_bytes..., r_hi, r_lo, g_hi, g_lo, b_hi, b_lo]
    Color components are split into 4-bit nibbles (2 bytes per component).
    """
    if not 0 <= int(position_beats) <= 127:
        raise ValueError("position_beats must be 0-127")
    if not marker_name:
        raise ValueError("marker_name cannot be empty")
    if len(marker_name) > 127:
        raise ValueError("marker_name too long")
    validate_color(r, g, b)
    # Convert position_beats to 16-bit integer (multiply by 100 for precision)
    position_ticks = int(position_beats * 100)
    pos_hi = (position_ticks >> 7) & 0x7F
    pos_lo = position_ticks & 0x7F
    
    name_bytes = [ord(c) if ord(c) < 128 else 63 for c in marker_name]
    color_bytes = [
        (r >> 4) & 0x0F, r & 0x0F,
        (g >> 4) & 0x0F, g & 0x0F,
        (b >> 4) & 0x0F, b & 0x0F,
    ]
    return _sysex(CMD_INSERT_MARKER, [pos_hi, pos_lo, len(name_bytes)] + name_bytes + color_bytes)


def encode_set_tempo_relative(percentage: int) -> bytes:
    """Encode a SET_TEMPO_RELATIVE command.
    
    Payload: [percentage]
    """
    if not -50 <= percentage <= 200:
        raise ValueError("percentage must be between -50 and 200")
    return _sysex(CMD_SET_TEMPO_RELATIVE, [percentage & 0x7F])


def encode_get_bpm() -> bytes:
    """Encode a GET_BPM command."""
    return _sysex(CMD_GET_BPM, [])


def encode_save_as(filename: str) -> bytes:
    """Encode a SAVE_AS command.
    
    Payload: [filename_len, filename_bytes...]
    """
    if not filename:
        raise ValueError("filename cannot be empty")
    filename_bytes = [ord(c) if ord(c) < 128 else 63 for c in filename]
    if len(filename_bytes) > 127:
        raise ValueError("filename too long")
    return _sysex(CMD_SAVE_AS, [len(filename_bytes)] + filename_bytes)


def encode_export_audio(output_path: str, format: str, quality: int) -> bytes:
    """Encode an EXPORT_AUDIO command.
    
    Payload: [path_len, path_bytes..., format_code, quality]
    """
    if not output_path:
        raise ValueError("output_path cannot be empty")
    format_codes = {"wav": 0, "mp3": 1, "flac": 2}
    if format not in format_codes:
        raise ValueError(f"Unsupported format: {format}")
    if not 0 <= quality <= 100:
        raise ValueError("quality must be 0-100")
    
    path_bytes = [ord(c) if ord(c) < 128 else 63 for c in output_path]
    if len(path_bytes) > 127:
        raise ValueError("output_path too long")
    return _sysex(CMD_EXPORT_AUDIO, [len(path_bytes)] + path_bytes + [format_codes[format], quality])


def encode_duplicate_pattern() -> bytes:
    """Encode a DUPLICATE_PATTERN command."""
    return _sysex(CMD_DUPLICATE_PATTERN, [])


def encode_copy_pattern(target_pattern_index: int) -> bytes:
    """Encode a COPY_PATTERN command.
    
    Payload: [target_pattern_index]
    """
    if not 0 <= target_pattern_index <= 127:
        raise ValueError("target_pattern_index out of range")
    return _sysex(CMD_COPY_PATTERN, [target_pattern_index])


def encode_cut_pattern() -> bytes:
    """Encode a CUT_PATTERN command."""
    return _sysex(CMD_CUT_PATTERN, [])


def encode_paste_pattern(target_pattern_index: int) -> bytes:
    """Encode a PASTE_PATTERN command.
    
    Payload: [target_pattern_index]
    """
    if not 0 <= target_pattern_index <= 127:
        raise ValueError("target_pattern_index out of range")
    return _sysex(CMD_PASTE_PATTERN, [target_pattern_index])


def encode_clear_pattern() -> bytes:
    """Encode a CLEAR_PATTERN command."""
    return _sysex(CMD_CLEAR_PATTERN, [])


def encode_set_pattern_color(pattern_idx: int, r: int, g: int, b: int) -> bytes:
    if not 0 <= pattern_idx <= 999:
        raise ValueError("pattern_idx out of range")
    pat_hi = (pattern_idx >> 7) & 0x7F
    pat_lo = pattern_idx & 0x7F
    return _sysex(CMD_SET_PATTERN_COLOR, [
        pat_hi, pat_lo,
        (r >> 4) & 0x0F, r & 0x0F,
        (g >> 4) & 0x0F, g & 0x0F,
        (b >> 4) & 0x0F, b & 0x0F
    ])
