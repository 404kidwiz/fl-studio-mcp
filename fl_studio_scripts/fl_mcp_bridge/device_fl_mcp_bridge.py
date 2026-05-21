"""FL Studio MIDI Controller Script — FL MCP Bridge v1.4
================================================================
Place this entire folder at:
  macOS:   ~/Documents/Image-Line/FL Studio/Settings/Hardware/fl_mcp_bridge/
  Windows: %USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Hardware\fl_mcp_bridge\

After placing the files:
  1. Open FL Studio → Options → MIDI Settings
  2. Under Input, select your IAC Driver Bus (macOS) or loopMIDI port (Windows)
  3. Click "Enable" and set the controller script to "FL MCP Bridge"
  4. Expand the port row, set the same port for Output too (for status responses)
  5. Close and reopen MIDI Settings to confirm it loads — check the output log

SysEx Protocol (Manufacturer ID 0x7D = non-commercial):

  Server → FL Studio (commands):
    F0 7D 01 F7                      → Play transport
    F0 7D 02 F7                      → Stop transport
    F0 7D 03 BPM_HI BPM_LO F7        → Set tempo (best-effort; see notes)
    F0 7D 04 [9 bytes × N notes] F7  → Play notes (realtime via midiNoteOn)
    F0 7D 05 F7                      → Save project (current filename)
    F0 7D 06 F7                      → Query status (responds with 0x10)
    F0 7D 07 F7                      → Query channels (responds with 0x11)
    F0 7D 08 ch_idx volume F7        → Set channel volume
    F0 7D 09 F7                      → Create new pattern
    F0 7D 0A pat_idx F7              → Select pattern
    F0 7D 0C F7                      → Query patterns (responds with 0x12)
    F0 7D 0D ch_idx is_muted F7      → Mute/unmute channel
    F0 7D 0E ch_idx is_soloed F7     → Solo/un-solo channel
    F0 7D 13 ch_idx pan F7           → Set channel pan (0=L, 64=C, 127=R)

  FL Studio → Server (responses):
    F0 7D 10 playing bpm_hi bpm_lo pat_idx ch_count F7  → Status response
    F0 7D 11 count [name_len name_bytes...] F7           → Channels response
    F0 7D 12 count [name_len name_bytes...] F7           → Patterns response

Note data encoding (9 bytes per note):
  [pitch, velocity, channel, start_b2, start_b1, start_b0, dur_b2, dur_b1, dur_b0]
  Tick value = (b2 << 14) | (b1 << 7) | b0

API Limitations (FL Studio MIDI Controller Scripting):
  - patterns.addNote() does NOT exist — notes are played via channels.midiNoteOn()
    in realtime. To record into a pattern, enable record mode in transport first.
  - patterns.clearCurrentPattern() does NOT exist — no programmatic pattern clear.
  - transport.setTempo() does NOT exist — tempo is set via general.processRECEvent
    when available, with a fallback to TempoJog. May not work on all FL versions.
  - ui.save() saves to the current filename only — cannot specify a new filename.

Changelog:
  v1.4 — API corrections: fixed getTempo→getSongTempo, removed non-existent
          patterns.addNote/clearCurrentPattern, honest note playback via midiNoteOn,
          removed CMD_CLEAR_PATTERN, fixed save semantics
  v1.3 — Added CMD_CLEAR_PATTERN (0x0F), CMD_SET_CHANNEL_PAN (0x13)
  v1.2 — Added CMD_QUERY_PATTERNS, CMD_MUTE_CHANNEL, CMD_SOLO_CHANNEL
  v1.1 — Added bidirectional queries (status, channels, set_channel_vol, patterns)
  v1.0 — Initial release (play, stop, tempo, notes, save)
"""

import channels
import device
import general
import midi
import mixer
import patterns
import transport
import ui

name = "FL MCP Bridge"
version = "1.6"

# Protocol constants (mirrors protocol.py)
_MANUFACTURER_ID = 0x7D

CMD_PLAY             = 0x01
CMD_STOP             = 0x02
CMD_SET_TEMPO        = 0x03
CMD_NOTES            = 0x04
CMD_SAVE             = 0x05
CMD_QUERY_STATUS     = 0x06
CMD_QUERY_CHANNELS   = 0x07
CMD_SET_CHANNEL_VOL  = 0x08
CMD_NEW_PATTERN      = 0x09
CMD_SELECT_PATTERN   = 0x0A
# 0x0B reserved (panic is pure MIDI CC — no SysEx needed)
CMD_QUERY_PATTERNS   = 0x0C
CMD_MUTE_CHANNEL     = 0x0D
CMD_SOLO_CHANNEL     = 0x0E
# 0x0F removed in v1.4 (patterns.clearCurrentPattern does not exist in API)
CMD_SET_CHANNEL_PAN  = 0x13
CMD_GET_NOTES        = 0x14
CMD_SET_PATTERN_LENGTH = 0x15
CMD_RENAME_CHANNEL   = 0x16
CMD_RENAME_PATTERN   = 0x17
CMD_SET_MIXER_VOL    = 0x19
CMD_SET_MIXER_PAN    = 0x1A
CMD_ROUTE_TO_MIXER   = 0x1B
CMD_QUERY_MIXER_STATE = 0x1C

RESP_STATUS   = 0x10
RESP_CHANNELS = 0x11
RESP_PATTERNS = 0x12
RESP_NOTES    = 0x14
RESP_MIXER_STATE = 0x1C

# Session-level notes cache mapping pattern index -> list of note bytes
notes_cache = {}


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def OnInit():
    global notes_cache
    notes_cache = {}
    print(f"[FL MCP Bridge v{version}] Initialized. Listening for SysEx.")
    device.setHasMeters(False)


def OnDeInit():
    print("[FL MCP Bridge] Deinitialized.")


# ---------------------------------------------------------------------------
# MIDI callbacks
# ---------------------------------------------------------------------------

def OnMidiMsg(event):
    event.handled = False


def OnSysEx(event):
    """Route incoming SysEx to the appropriate command handler."""
    data = event.sysex  # includes F0 and F7

    if len(data) < 4:
        return
    if data[0] != 0xF0 or data[-1] != 0xF7:
        return
    if data[1] != _MANUFACTURER_ID:
        return

    cmd     = data[2]
    payload = list(data[3:-1])
    event.handled = True

    dispatch = {
        CMD_PLAY:            lambda: _cmd_play(),
        CMD_STOP:            lambda: _cmd_stop(),
        CMD_SET_TEMPO:       lambda: _cmd_set_tempo(payload),
        CMD_NOTES:           lambda: _cmd_play_notes(payload),
        CMD_SAVE:            lambda: _cmd_save(),
        CMD_QUERY_STATUS:    lambda: _cmd_query_status(),
        CMD_QUERY_CHANNELS:  lambda: _cmd_query_channels(),
        CMD_SET_CHANNEL_VOL: lambda: _cmd_set_channel_vol(payload),
        CMD_NEW_PATTERN:     lambda: _cmd_new_pattern(),
        CMD_SELECT_PATTERN:  lambda: _cmd_select_pattern(payload),
        CMD_QUERY_PATTERNS:  lambda: _cmd_query_patterns(),
        CMD_MUTE_CHANNEL:    lambda: _cmd_mute_channel(payload),
        CMD_SOLO_CHANNEL:    lambda: _cmd_solo_channel(payload),
        CMD_SET_CHANNEL_PAN: lambda: _cmd_set_channel_pan(payload),
        CMD_GET_NOTES:          lambda: _cmd_get_notes(),
        CMD_SET_PATTERN_LENGTH: lambda: _cmd_set_pattern_length(payload),
        CMD_RENAME_CHANNEL:     lambda: _cmd_rename_channel(payload),
        CMD_RENAME_PATTERN:     lambda: _cmd_rename_pattern(payload),
        CMD_SET_MIXER_VOL:      lambda: _cmd_set_mixer_vol(payload),
        CMD_SET_MIXER_PAN:      lambda: _cmd_set_mixer_pan(payload),
        CMD_ROUTE_TO_MIXER:     lambda: _cmd_route_to_mixer(payload),
        CMD_QUERY_MIXER_STATE:  lambda: _cmd_query_mixer_state(payload),
    }

    handler = dispatch.get(cmd)
    if handler:
        handler()
    else:
        print(f"[FL MCP Bridge] Unknown command: {cmd:#x}")


# ---------------------------------------------------------------------------
# SysEx output helper
# ---------------------------------------------------------------------------

def _send_sysex(cmd: int, payload: list) -> None:
    """Send a SysEx response back to the MCP server via MIDI output."""
    data = [0xF0, _MANUFACTURER_ID, cmd] + payload + [0xF7]
    try:
        device.midiOutSysex(bytes(data))
    except Exception as exc:
        print(f"[FL MCP Bridge] midiOutSysex failed: {exc}")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _cmd_play():
    transport.start()
    print("[FL MCP Bridge] Play")


def _cmd_stop():
    transport.stop()
    print("[FL MCP Bridge] Stop")


def _cmd_set_tempo(payload):
    """Set tempo — best-effort since no direct transport.setTempo() exists.

    Strategy:
      1. Try general.processRECEvent with REC_Tempo (works on modern FL)
      2. Fall back to TempoJog via transport.globalTransport (relative, less precise)
      3. Fall back to general.processMIDICC (legacy)
    """
    if len(payload) < 2:
        print("[FL MCP Bridge] set_tempo: payload too short")
        return
    bpm = (payload[0] << 7) | payload[1]
    if not 20 <= bpm <= 999:
        print(f"[FL MCP Bridge] set_tempo: BPM {bpm} out of range")
        return

    # Strategy 1: processRECEvent — most reliable on modern FL Studio
    try:
        # REC_Tempo expects BPM * 1000 (milliBPM)
        general.processRECEvent(midi.REC_Tempo, bpm * 1000, midi.REC_MIDIController)
        print(f"[FL MCP Bridge] Tempo → {bpm} BPM (via processRECEvent)")
        return
    except (AttributeError, TypeError, Exception):
        pass

    # Strategy 2: TempoJog — relative, so we read current and compute delta
    try:
        current_bpm = int(transport.getSongTempo())
        delta = bpm - current_bpm
        if delta != 0:
            transport.globalTransport(midi.FPT_TempoJog, delta)
        print(f"[FL MCP Bridge] Tempo → {bpm} BPM (via TempoJog, delta={delta})")
        return
    except (AttributeError, TypeError, Exception):
        pass

    # Strategy 3: Legacy fallback via processMIDICC
    try:
        micros = 60_000_000 // bpm
        general.processMIDICC(midi.MIDI_TEMPOCHANGE, micros & 0x7F, (micros >> 7) & 0x7F)
        print(f"[FL MCP Bridge] Tempo → {bpm} BPM (legacy fallback)")
        return
    except (AttributeError, TypeError, Exception):
        pass

    print(f"[FL MCP Bridge] set_tempo: all strategies failed for BPM {bpm}")


def _decode_tick(b2, b1, b0):
    return (b2 << 14) | (b1 << 7) | b0


def _cmd_play_notes(payload):
    """Play notes in realtime via channels.midiNoteOn.

    NOTE: The FL Studio MIDI Controller Scripting API does NOT have
    patterns.addNote(). Notes are triggered in realtime. To record
    notes into a pattern, start transport in record mode BEFORE calling
    this command — FL Studio will capture the played notes.

    Each note is 9 bytes:
      [pitch, velocity, channel, start_b2, start_b1, start_b0, dur_b2, dur_b1, dur_b0]

    Start tick and duration are used to schedule note timing relative to
    each other. In realtime mode, all notes fire immediately (start_tick
    offsets are ignored). Duration triggers a note-off after the specified
    length — but in this simple implementation we only send note-on.
    FL Studio handles note-off via its internal note management.
    """
    if len(payload) % 9 != 0:
        print(f"[FL MCP Bridge] play_notes: bad payload length {len(payload)}")
        return

    # Cache notes for the active pattern
    try:
        pat_idx = patterns.patternNumber()
        if pat_idx not in notes_cache:
            notes_cache[pat_idx] = []
        notes_cache[pat_idx].extend(payload)
    except Exception as exc:
        print(f"[FL MCP Bridge] Failed to cache notes: {exc}")

    n_played = 0
    for i in range(0, len(payload), 9):
        pitch   = payload[i]
        vel     = payload[i + 1]
        ch      = payload[i + 2]
        # start_tick and dur_tick are available but not used in realtime mode
        # start = _decode_tick(payload[i+3], payload[i+4], payload[i+5])
        # dur   = _decode_tick(payload[i+6], payload[i+7], payload[i+8])

        try:
            channels.midiNoteOn(ch, pitch, vel)
            n_played += 1
        except Exception as exc:
            print(f"[FL MCP Bridge] midiNoteOn failed: ch={ch} pitch={pitch} vel={vel} — {exc}")

    print(f"[FL MCP Bridge] Notes: {n_played} played realtime")


def _cmd_save():
    """Save the current project (Ctrl+S equivalent).

    NOTE: ui.save() saves to the current filename. It cannot set a new
    filename programmatically. If the project has never been saved,
    FL Studio will show its native Save dialog.
    """
    try:
        ui.save()
        print("[FL MCP Bridge] Saved.")
    except Exception as exc:
        print(f"[FL MCP Bridge] Save failed: {exc}")


# ---------------------------------------------------------------------------
# Query handlers — send SysEx responses back to the MCP server
# ---------------------------------------------------------------------------

def _cmd_query_status():
    """Respond with current transport state, BPM, pattern index, channel count."""
    try:
        playing = int(transport.isPlaying())
    except (AttributeError, Exception):
        playing = 0

    # transport.getSongTempo() is the correct API (not getTempo)
    try:
        bpm_raw = transport.getSongTempo()
        bpm = max(20, min(999, int(bpm_raw)))
    except (AttributeError, Exception):
        bpm = 120

    try:
        pat_idx = patterns.patternNumber() & 0x7F
    except Exception:
        pat_idx = 0

    try:
        ch_count = channels.channelCount() & 0x7F
    except Exception:
        ch_count = 0

    bpm_hi = (bpm >> 7) & 0x7F
    bpm_lo = bpm & 0x7F

    _send_sysex(RESP_STATUS, [playing, bpm_hi, bpm_lo, pat_idx, ch_count])
    print(f"[FL MCP Bridge] Status → playing={playing} bpm={bpm} pat={pat_idx} ch={ch_count}")


def _cmd_query_channels():
    """Respond with channel rack names."""
    try:
        count = channels.channelCount()
    except Exception:
        count = 0

    payload = [min(count, 127)]
    for i in range(min(count, 127)):
        try:
            raw_name = channels.getChannelName(i)
        except Exception:
            raw_name = f"Ch{i}"
        # Truncate to 14 chars, keep only 7-bit-safe ASCII
        safe = [ord(c) for c in raw_name[:14] if ord(c) <= 127]
        payload.append(len(safe))
        payload.extend(safe)

    _send_sysex(RESP_CHANNELS, payload)
    print(f"[FL MCP Bridge] Channels → {count} channels sent")


def _cmd_set_channel_vol(payload):
    if len(payload) < 2:
        print("[FL MCP Bridge] set_channel_vol: payload too short")
        return
    ch_idx = payload[0]
    volume = payload[1]
    try:
        # FL Studio volume is 0.0–1.0 internally; 100/127 ≈ 0.787 = unity
        normalized = volume / 127.0
        channels.setChannelVolume(ch_idx, normalized)
        print(f"[FL MCP Bridge] Channel {ch_idx} volume → {volume} ({normalized:.3f})")
    except Exception as exc:
        print(f"[FL MCP Bridge] set_channel_vol failed: {exc}")


def _cmd_new_pattern():
    """Create (jump to) the next empty pattern slot."""
    try:
        count = patterns.patternCount()
        patterns.jumpToPattern(count)
        print(f"[FL MCP Bridge] New pattern at index {count}")
    except Exception as exc:
        print(f"[FL MCP Bridge] new_pattern failed: {exc}")


def _cmd_select_pattern(payload):
    if not payload:
        print("[FL MCP Bridge] select_pattern: no index provided")
        return
    idx = payload[0]
    try:
        patterns.jumpToPattern(idx)
        print(f"[FL MCP Bridge] Selected pattern {idx}")
    except Exception as exc:
        print(f"[FL MCP Bridge] select_pattern failed: {exc}")


def _cmd_query_patterns():
    """Respond with pattern names."""
    try:
        count = patterns.patternCount()
    except Exception:
        count = 0

    payload = [min(count, 127)]
    for i in range(min(count, 127)):
        try:
            raw_name = patterns.getPatternName(i)
        except Exception:
            raw_name = f"Pattern {i + 1}"
        # Truncate to 14 chars, keep only 7-bit-safe ASCII
        safe = [ord(c) for c in raw_name[:14] if ord(c) <= 127]
        payload.append(len(safe))
        payload.extend(safe)

    _send_sysex(RESP_PATTERNS, payload)
    print(f"[FL MCP Bridge] Patterns → {count} patterns sent")


def _cmd_mute_channel(payload):
    if len(payload) < 2:
        print("[FL MCP Bridge] mute_channel: payload too short")
        return
    ch_idx  = payload[0]
    # channels.muteChannel(index, value) — value: 1=mute, 0=unmute, -1=toggle
    is_muted = int(payload[1])
    try:
        channels.muteChannel(ch_idx, is_muted)
        state = "muted" if is_muted else "unmuted"
        print(f"[FL MCP Bridge] Channel {ch_idx} {state}")
    except Exception as exc:
        print(f"[FL MCP Bridge] mute_channel failed: {exc}")


def _cmd_solo_channel(payload):
    if len(payload) < 2:
        print("[FL MCP Bridge] solo_channel: payload too short")
        return
    ch_idx = payload[0]
    # channels.soloChannel(index, value) — value: 1=solo, 0=unsolo, -1=toggle
    is_soloed = int(payload[1])
    try:
        channels.soloChannel(ch_idx, is_soloed)
        state = "soloed" if is_soloed else "unsoloed"
        print(f"[FL MCP Bridge] Channel {ch_idx} {state}")
    except Exception as exc:
        print(f"[FL MCP Bridge] solo_channel failed: {exc}")


def _cmd_set_channel_pan(payload):
    if len(payload) < 2:
        print("[FL MCP Bridge] set_channel_pan: payload too short")
        return
    ch_idx = payload[0]
    pan    = payload[1]
    try:
        # FL Studio pan is -1.0 (left) → 0.0 (centre) → +1.0 (right)
        # MIDI 0-127 → 0=L (-1.0), 64=C (0.0), 127=R (+1.0)
        normalized = (pan - 64) / 64.0
        normalized = max(-1.0, min(1.0, normalized))
        channels.setChannelPan(ch_idx, normalized)
        print(f"[FL MCP Bridge] Channel {ch_idx} pan → {pan} ({normalized:.3f})")
    except Exception as exc:
        print(f"[FL MCP Bridge] set_channel_pan failed: {exc}")


def _cmd_get_notes():
    try:
        pat_idx = patterns.patternNumber()
        payload = notes_cache.get(pat_idx, [])
    except Exception as exc:
        print(f"[FL MCP Bridge] get_notes: failed to get active pattern index: {exc}")
        payload = []
    _send_sysex(RESP_NOTES, payload)
    print(f"[FL MCP Bridge] Notes → sent {len(payload) // 9} notes for pattern {pat_idx}")


def _cmd_set_pattern_length(payload):
    if len(payload) < 4:
        print("[FL MCP Bridge] set_pattern_length: payload too short")
        return
    pat_idx = (payload[0] << 7) | payload[1]
    length_beats = (payload[2] << 7) | payload[3]
    try:
        patterns.setPatternLength(pat_idx, length_beats)
        print(f"[FL MCP Bridge] Pattern {pat_idx} length set to {length_beats} beats")
    except Exception as exc:
        print(f"[FL MCP Bridge] set_pattern_length failed: {exc}")


def _cmd_rename_channel(payload):
    if len(payload) < 2:
        print("[FL MCP Bridge] rename_channel: payload too short")
        return
    ch_idx = payload[0]
    name_len = payload[1]
    name_bytes = payload[2 : 2 + name_len]
    name = "".join(chr(b) for b in name_bytes)
    try:
        channels.setChannelName(ch_idx, name)
        print(f"[FL MCP Bridge] Rename channel {ch_idx} → '{name}'")
    except Exception as exc:
        print(f"[FL MCP Bridge] rename_channel failed: {exc}")


def _cmd_rename_pattern(payload):
    if len(payload) < 3:
        print("[FL MCP Bridge] rename_pattern: payload too short")
        return
    pat_idx = (payload[0] << 7) | payload[1]
    name_len = payload[2]
    name_bytes = payload[3 : 3 + name_len]
    name = "".join(chr(b) for b in name_bytes)
    try:
        patterns.setPatternName(pat_idx, name)
        print(f"[FL MCP Bridge] Rename pattern {pat_idx} → '{name}'")
    except Exception as exc:
        print(f"[FL MCP Bridge] rename_pattern failed: {exc}")


def _cmd_set_mixer_vol(payload):
    if len(payload) < 2:
        print("[FL MCP Bridge] set_mixer_vol: payload too short")
        return
    track_idx = payload[0]
    volume = payload[1]
    try:
        normalized = max(0.0, min(1.0, volume / 127.0))
        mixer.setTrackVolume(track_idx, normalized)
        print(f"[FL MCP Bridge] Mixer track {track_idx} volume → {volume} ({normalized:.3f})")
    except Exception as exc:
        print(f"[FL MCP Bridge] set_mixer_vol failed: {exc}")


def _cmd_set_mixer_pan(payload):
    if len(payload) < 2:
        print("[FL MCP Bridge] set_mixer_pan: payload too short")
        return
    track_idx = payload[0]
    pan = payload[1]
    try:
        normalized = (pan - 64) / 64.0
        normalized = max(-1.0, min(1.0, normalized))
        mixer.setTrackPan(track_idx, normalized)
        print(f"[FL MCP Bridge] Mixer track {track_idx} pan → {pan} ({normalized:.3f})")
    except Exception as exc:
        print(f"[FL MCP Bridge] set_mixer_pan failed: {exc}")


def _cmd_route_to_mixer(payload):
    if len(payload) < 2:
        print("[FL MCP Bridge] route_to_mixer: payload too short")
        return
    ch_idx = payload[0]
    track_idx = payload[1]
    try:
        channels.setTargetTrack(ch_idx, track_idx)
        print(f"[FL MCP Bridge] Channel {ch_idx} routed to mixer track {track_idx}")
    except Exception as exc:
        print(f"[FL MCP Bridge] route_to_mixer failed: {exc}")


def _cmd_query_mixer_state(payload):
    if len(payload) < 2:
        print("[FL MCP Bridge] query_mixer_state: payload too short")
        return
    start_track = payload[0]
    end_track = payload[1]
    if start_track > end_track:
        print("[FL MCP Bridge] query_mixer_state: start_track > end_track")
        return
    if end_track - start_track >= 32:
        end_track = start_track + 31
    
    response_payload = [start_track, end_track, end_track - start_track + 1]
    for i in range(start_track, end_track + 1):
        try:
            vol_norm = mixer.getTrackVolume(i)
            vol = int(vol_norm * 127.0 + 0.5)
            vol = max(0, min(127, vol))
            
            pan_norm = mixer.getTrackPan(i)
            pan = int(pan_norm * 64.0 + 64.0 + 0.5)
            pan = max(0, min(127, pan))
            
            name = mixer.getTrackName(i)
            safe = [ord(c) for c in name[:14] if ord(c) <= 127]
        except Exception as exc:
            print(f"[FL MCP Bridge] Failed to query track {i} state: {exc}")
            vol = 0
            pan = 64
            safe = []
            
        response_payload.append(vol)
        response_payload.append(pan)
        response_payload.append(len(safe))
        response_payload.extend(safe)
        
    _send_sysex(RESP_MIXER_STATE, response_payload)
    print(f"[FL MCP Bridge] Mixer state → sent tracks {start_track}-{end_track}")

