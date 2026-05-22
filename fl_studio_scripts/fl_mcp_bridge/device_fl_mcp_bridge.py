"""FL Studio MIDI Controller Script — FL MCP Bridge v1.6
================================================================
Place this entire folder at:
  macOS:   ~/Documents/Image-Line/FL Studio/Settings/Hardware/fl_mcp_bridge/
  Windows: %USERPROFILE%\\Documents\\Image-Line\\FL Studio\\Settings\\Hardware\\fl_mcp_bridge\\

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
  v1.6 — GUI Automation updates, High-DPI support, bidirectional protocol harden
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
import plugins
import arrangement
import playlist

name = "FL MCP Bridge"
version = "1.6"

# Protocol constants (mirrors protocol.py)
_MANUFACTURER_ID = 0x7D

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
# 0x0B reserved (panic is pure MIDI CC — no SysEx needed)
CMD_QUERY_PATTERNS = 0x0C
CMD_MUTE_CHANNEL = 0x0D
CMD_SOLO_CHANNEL = 0x0E
# 0x0F removed in v1.4 (patterns.clearCurrentPattern does not exist in API)
CMD_SET_CHANNEL_PAN = 0x13
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
CMD_SET_PLUGIN_PARAM = 0x20
CMD_GET_PLUGIN_PARAM = 0x21
CMD_SHOW_WINDOW = 0x22
CMD_ADD_MARKER = 0x23
CMD_GET_PEAKS = 0x25
CMD_BROWSER_NAV = 0x27
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

RESP_STATUS = 0x10
RESP_CHANNELS = 0x11
RESP_PATTERNS = 0x12
RESP_NOTES = 0x14
RESP_MIXER_STATE = 0x1C
RESP_ACK = 0x1F
RESP_PLUGIN_PARAM = 0x21

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

    cmd = data[2]
    payload = list(data[3:-1])
    event.handled = True

    dispatch = {
        CMD_PLAY: lambda: _cmd_play(),
        CMD_STOP: lambda: _cmd_stop(),
        CMD_SET_TEMPO: lambda: _cmd_set_tempo(payload),
        CMD_NOTES: lambda: _cmd_play_notes(payload),
        CMD_SAVE: lambda: _cmd_save(),
        CMD_QUERY_STATUS: lambda: _cmd_query_status(),
        CMD_QUERY_CHANNELS: lambda: _cmd_query_channels(),
        CMD_SET_CHANNEL_VOL: lambda: _cmd_set_channel_vol(payload),
        CMD_NEW_PATTERN: lambda: _cmd_new_pattern(),
        CMD_SELECT_PATTERN: lambda: _cmd_select_pattern(payload),
        CMD_QUERY_PATTERNS: lambda: _cmd_query_patterns(),
        CMD_MUTE_CHANNEL: lambda: _cmd_mute_channel(payload),
        CMD_SOLO_CHANNEL: lambda: _cmd_solo_channel(payload),
        CMD_SET_CHANNEL_PAN: lambda: _cmd_set_channel_pan(payload),
        CMD_GET_NOTES: lambda: _cmd_get_notes(),
        CMD_SET_PATTERN_LENGTH: lambda: _cmd_set_pattern_length(payload),
        CMD_RENAME_CHANNEL: lambda: _cmd_rename_channel(payload),
        CMD_RENAME_PATTERN: lambda: _cmd_rename_pattern(payload),
        CMD_PING: lambda: _cmd_ping(payload),
        CMD_SET_MIXER_VOL: lambda: _cmd_set_mixer_vol(payload),
        CMD_SET_MIXER_PAN: lambda: _cmd_set_mixer_pan(payload),
        CMD_ROUTE_TO_MIXER: lambda: _cmd_route_to_mixer(payload),
        CMD_QUERY_MIXER_STATE: lambda: _cmd_query_mixer_state(payload),
        CMD_UNDO: lambda: _cmd_undo(),
        CMD_REDO: lambda: _cmd_redo(),
        CMD_SET_PLUGIN_PARAM: lambda: _cmd_set_plugin_param(payload),
        CMD_GET_PLUGIN_PARAM: lambda: _cmd_get_plugin_param(payload),
        CMD_SHOW_WINDOW: lambda: _cmd_show_window(payload),
        CMD_ADD_MARKER: lambda: _cmd_add_marker(payload),
        CMD_GET_PEAKS: lambda: _cmd_get_peaks(payload),
        CMD_BROWSER_NAV: lambda: _cmd_browser_nav(payload),
        CMD_SET_GRID_BIT: lambda: _cmd_set_grid_bit(payload),
        CMD_MUTE_PLAYLIST_TRACK: lambda: _cmd_mute_playlist_track(payload),
        CMD_SOLO_PLAYLIST_TRACK: lambda: _cmd_solo_playlist_track(payload),
        CMD_SET_TIME_SELECTION: lambda: _cmd_set_time_selection(payload),
        CMD_SET_CHANNEL_COLOR: lambda: _cmd_set_channel_color(payload),
        CMD_SET_PATTERN_COLOR: lambda: _cmd_set_pattern_color(payload),
        # Phase 7
        CMD_SET_CHANNEL_NAME: lambda: _cmd_set_channel_name(payload),
        CMD_SET_CHANNEL_MIXER_TRACK: lambda: _cmd_set_channel_mixer_track(payload),
        CMD_UI_NAVIGATE: lambda: _cmd_ui_navigate(payload)
    }

    handler = dispatch.get(cmd)
    if handler:
        handler()
        queries_and_pings = {
            CMD_QUERY_STATUS,
            CMD_QUERY_CHANNELS,
            CMD_QUERY_PATTERNS,
            CMD_GET_NOTES,
            CMD_QUERY_MIXER_STATE,
            CMD_GET_PLUGIN_PARAM,
            CMD_PING,
            CMD_GET_PEAKS,
        }
        if cmd not in queries_and_pings:
            _send_sysex(RESP_ACK, [cmd])
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
        general.processMIDICC(
            midi.MIDI_TEMPOCHANGE, micros & 0x7F, (micros >> 7) & 0x7F
        )
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
        pitch = payload[i]
        vel = payload[i + 1]
        ch = payload[i + 2]
        # start_tick and dur_tick are available but not used in realtime mode
        # start = _decode_tick(payload[i+3], payload[i+4], payload[i+5])
        # dur   = _decode_tick(payload[i+6], payload[i+7], payload[i+8])

        try:
            channels.midiNoteOn(ch, pitch, vel)
            n_played += 1
        except Exception as exc:
            print(
                f"[FL MCP Bridge] midiNoteOn failed: ch={ch} pitch={pitch} vel={vel} — {exc}"
            )

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
    print(
        f"[FL MCP Bridge] Status → playing={playing} bpm={bpm} pat={pat_idx} ch={ch_count}"
    )


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
    ch_idx = payload[0]
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
    pan = payload[1]
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
    print(
        f"[FL MCP Bridge] Notes → sent {len(payload) // 9} notes for pattern {pat_idx}"
    )


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
        print(
            f"[FL MCP Bridge] Mixer track {track_idx} volume → {volume} ({normalized:.3f})"
        )
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


def _cmd_undo():
    try:
        general.undoUp()
        print("[FL MCP Bridge] Undo")
    except Exception as exc:
        print(f"[FL MCP Bridge] Undo failed: {exc}")


def _cmd_redo():
    try:
        general.undoDown()
        print("[FL MCP Bridge] Redo")
    except Exception as exc:
        print(f"[FL MCP Bridge] Redo failed: {exc}")


def _cmd_ping(payload):
    if not payload:
        print("[FL MCP Bridge] Ping: no challenge payload")
        return
    # Echo back challenge byte
    _send_sysex(CMD_PING, payload)
    print(f"[FL MCP Bridge] Ping response sent for challenge {payload[0]}")


def _cmd_set_plugin_param(payload):
    if len(payload) < 7:
        print("[FL MCP Bridge] set_plugin_param: payload too short")
        return
    target_type = payload[0]
    track_or_chan_idx = payload[1]
    slot_idx = payload[2]
    param_idx = (payload[3] << 7) | payload[4]
    val_int = (payload[5] << 7) | payload[6]
    normalized = max(0.0, min(1.0, val_int / 16383.0))

    try:
        if target_type == 0:  # Mixer effect
            plugins.setParamValue(normalized, param_idx, track_or_chan_idx, slot_idx)
        else:  # Channel generator
            try:
                plugins.setParamValue(normalized, param_idx, -1, track_or_chan_idx)
            except TypeError:
                plugins.setParamValue(normalized, param_idx, track_or_chan_idx)
        print(f"[FL MCP Bridge] Set plugin param t={target_type} ch/trk={track_or_chan_idx} slot={slot_idx} param={param_idx} val={normalized:.3f}")
    except Exception as exc:
        print(f"[FL MCP Bridge] set_plugin_param failed: {exc}")


def _cmd_get_plugin_param(payload):
    if len(payload) < 5:
        print("[FL MCP Bridge] get_plugin_param: payload too short")
        return
    target_type = payload[0]
    track_or_chan_idx = payload[1]
    slot_idx = payload[2]
    param_idx = (payload[3] << 7) | payload[4]

    try:
        if target_type == 0:  # Mixer effect
            val_norm = plugins.getParamValue(param_idx, track_or_chan_idx, slot_idx)
        else:  # Channel generator
            try:
                val_norm = plugins.getParamValue(param_idx, -1, track_or_chan_idx)
            except TypeError:
                val_norm = plugins.getParamValue(param_idx, track_or_chan_idx)
            
        val_int = int(round(val_norm * 16383.0))
        val_hi = (val_int >> 7) & 0x7F
        val_lo = val_int & 0x7F
        _send_sysex(RESP_PLUGIN_PARAM, [val_hi, val_lo])
        print(f"[FL MCP Bridge] Get plugin param param={param_idx} → {val_norm:.3f}")
    except Exception as exc:
        print(f"[FL MCP Bridge] get_plugin_param failed: {exc}")
        _send_sysex(RESP_PLUGIN_PARAM, [0, 0])


def _cmd_show_window(payload):
    if len(payload) < 1:
        print("[FL MCP Bridge] show_window: payload too short")
        return
    window_id = payload[0]
    try:
        if window_id == 0:
            ui.showWindow(midi.widMixer)
        elif window_id == 1:
            ui.showWindow(midi.widChannelRack)
        elif window_id == 2:
            ui.showWindow(midi.widPlaylist)
        elif window_id == 3:
            ui.showWindow(midi.widPianoRoll)
        elif window_id == 4:
            ui.showWindow(midi.widBrowser)
        elif window_id == 5:
            if len(payload) > 1:
                ch_idx = payload[1]
                channels.showEditor(ch_idx, True)
        print(f"[FL MCP Bridge] Show window {window_id}")
    except Exception as exc:
        print(f"[FL MCP Bridge] show_window failed: {exc}")


def _cmd_add_marker(payload: list) -> None:
    if not payload:
        return
    name_len = payload[0]
    name = "".join(chr(b) for b in payload[1:1+name_len])
    try:
        arrangement.addAutoTimeMarker(transport.getSongPos(), name)
        print(f"[FL MCP Bridge] Added marker '{name}'")
    except Exception:
        pass


def _cmd_get_peaks(payload: list) -> None:
    if not payload:
        return
    track_idx = payload[0]
    try:
        l_peak = mixer.getTrackPeaks(track_idx, 0)
        r_peak = mixer.getTrackPeaks(track_idx, 1)
        resp = encode_resp_peaks(l_peak, r_peak)
        device.midiOutSysex(resp)
    except Exception as e:
        print(f"FL-MCP: Error getting peaks: {e}")


def _cmd_browser_nav(payload: list) -> None:
    if not payload:
        return
    action = payload[0]
    # action: 0=Up, 1=Down, 2=Left, 3=Right, 4=Enter
    try:
        if action == 0:
            ui.up()
        elif action == 1:
            ui.down()
        elif action == 2:
            ui.left()
        elif action == 3:
            ui.right()
        elif action == 4:
            ui.enter()
    except Exception:
        pass


def encode_resp_peaks(l_peak: float, r_peak: float) -> bytes:
    RESP_PEAKS = 0x26
    l_int = int(round(max(0.0, min(1.0, l_peak)) * 16383))
    r_int = int(round(max(0.0, min(1.0, r_peak)) * 16383))
    l_hi = (l_int >> 7) & 0x7F
    l_lo = l_int & 0x7F
    r_hi = (r_int >> 7) & 0x7F
    r_lo = r_int & 0x7F
    
    data = [0xF0, 0x7D, RESP_PEAKS, l_hi, l_lo, r_hi, r_lo, 0xF7]
    return bytes(data)


def _cmd_set_grid_bit(payload: list) -> None:
    if len(payload) < 3:
        return
    ch_idx, step_idx, value = payload[0], payload[1], payload[2]
    try:
        channels.setGridBit(ch_idx, step_idx, value)
    except Exception:
        pass


def _cmd_mute_playlist_track(payload: list) -> None:
    if len(payload) < 2:
        return
    track_idx, muted = payload[0], payload[1]
    try:
        playlist.muteTrack(track_idx, bool(muted))
    except Exception:
        pass


def _cmd_solo_playlist_track(payload: list) -> None:
    if len(payload) < 2:
        return
    track_idx, soloed = payload[0], payload[1]
    try:
        playlist.soloTrack(track_idx, bool(soloed))
    except Exception:
        pass


def _cmd_set_time_selection(payload: list) -> None:
    if len(payload) < 4:
        return
    start_bar = (payload[0] << 7) | payload[1]
    end_bar = (payload[2] << 7) | payload[3]
    try:
        # Assuming 4 beats per bar, 96 ticks per beat = 384 ticks per bar
        # arrangement.currentTimeSelection expects Selection, Start, End. 
        # Selection: 1 to set. Start/End in ticks.
        # This API behavior is based on FL docs.
        start_ticks = start_bar * 384
        end_ticks = end_bar * 384
        arrangement.currentTimeSelection(1, start_ticks, end_ticks)
    except Exception:
        pass


def _cmd_set_channel_color(payload: list) -> None:
    if len(payload) < 7:
        return
    ch_idx = payload[0]
    r = (payload[1] << 4) | payload[2]
    g = (payload[3] << 4) | payload[4]
    b = (payload[5] << 4) | payload[6]
    # FL Studio colors are usually 0x00RRGGBB
    color = (r << 16) | (g << 8) | b
    try:
        channels.setChannelColor(ch_idx, color)
    except Exception:
        pass


def _cmd_set_pattern_color(payload: list) -> None:
    if len(payload) < 8:
        return
    pat_idx = (payload[0] << 7) | payload[1]
    r = (payload[2] << 4) | payload[3]
    g = (payload[4] << 4) | payload[5]
    b = (payload[6] << 4) | payload[7]
    color = (r << 16) | (g << 8) | b
    try:
        patterns.setPatternColor(pat_idx, color)
    except Exception:
        pass


def _cmd_set_channel_name(payload: list):
    if len(payload) >= 2:
        ch_hi = payload[0]
        ch_lo = payload[1]
        ch_idx = (ch_hi << 7) | ch_lo
        name_bytes = payload[2:]
        name = "".join([chr(b) for b in name_bytes])
        if 0 <= ch_idx < channels.channelCount():
            channels.setChannelName(ch_idx, name)


def _cmd_set_channel_mixer_track(payload: list):
    if len(payload) >= 4:
        ch_hi = payload[0]
        ch_lo = payload[1]
        tr_hi = payload[2]
        tr_lo = payload[3]
        ch_idx = (ch_hi << 7) | ch_lo
        tr_idx = (tr_hi << 7) | tr_lo
        if 0 <= ch_idx < channels.channelCount():
            channels.setTargetFxTrack(ch_idx, tr_idx)


def _cmd_ui_navigate(payload: list):
    if len(payload) >= 1:
        action = payload[0]
        if action == 0:
            ui.up()
        elif action == 1:
            ui.down()
        elif action == 2:
            ui.left()
        elif action == 3:
            ui.right()
        elif action == 4:
            ui.enter()
        elif action == 5:
            ui.escape()
        elif action == 6:
            ui.setFocused(midi.widBrowser)
        elif action == 7:
            ui.setFocused(midi.widChannelRack)
        elif action == 8:
            ui.setFocused(midi.widMixer)
        elif action == 9:
            ui.setFocused(midi.widPlaylist)
