"""FL Studio MIDI Controller Script — FL MCP Bridge v1.1
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
    F0 7D 03 BPM_HI BPM_LO F7        → Set tempo
    F0 7D 04 [9 bytes × N notes] F7  → Insert notes
    F0 7D 05 [ASCII filename] F7     → Save project
    F0 7D 06 F7                      → Query status (responds with 0x10)
    F0 7D 07 F7                      → Query channels (responds with 0x11)
    F0 7D 08 ch_idx volume F7        → Set channel volume
    F0 7D 09 F7                      → Create new pattern
    F0 7D 0A pat_idx F7              → Select pattern

  FL Studio → Server (responses):
    F0 7D 10 playing bpm_hi bpm_lo pat_idx ch_count F7  → Status response
    F0 7D 11 count [name_len name_bytes...] F7           → Channels response

Note data encoding (9 bytes per note):
  [pitch, velocity, channel, start_b2, start_b1, start_b0, dur_b2, dur_b1, dur_b0]
  Tick value = (b2 << 14) | (b1 << 7) | b0
"""

import channels
import device
import general
import midi
import patterns
import transport
import ui

name = "FL MCP Bridge"
version = "1.1"

# Protocol constants (mirrors protocol.py)
_MANUFACTURER_ID = 0x7D

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

RESP_STATUS   = 0x10
RESP_CHANNELS = 0x11


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def OnInit():
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
        CMD_NOTES:           lambda: _cmd_insert_notes(payload),
        CMD_SAVE_AS:         lambda: _cmd_save_as(payload),
        CMD_QUERY_STATUS:    lambda: _cmd_query_status(),
        CMD_QUERY_CHANNELS:  lambda: _cmd_query_channels(),
        CMD_SET_CHANNEL_VOL: lambda: _cmd_set_channel_vol(payload),
        CMD_NEW_PATTERN:     lambda: _cmd_new_pattern(),
        CMD_SELECT_PATTERN:  lambda: _cmd_select_pattern(payload),
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
    if len(payload) < 2:
        print("[FL MCP Bridge] set_tempo: payload too short")
        return
    bpm = (payload[0] << 7) | payload[1]
    if not 20 <= bpm <= 999:
        print(f"[FL MCP Bridge] set_tempo: BPM {bpm} out of range")
        return
    try:
        transport.setTempo(bpm)
        print(f"[FL MCP Bridge] Tempo → {bpm} BPM")
    except AttributeError:
        # Older FL: fallback via general event
        micros = 60_000_000 // bpm
        try:
            general.processMIDICC(midi.MIDI_TEMPOCHANGE, micros & 0x7F, (micros >> 7) & 0x7F)
        except Exception:
            pass
        print(f"[FL MCP Bridge] Tempo → {bpm} BPM (legacy fallback)")


def _decode_tick(b2, b1, b0):
    return (b2 << 14) | (b1 << 7) | b0


def _cmd_insert_notes(payload):
    if len(payload) % 9 != 0:
        print(f"[FL MCP Bridge] insert_notes: bad payload length {len(payload)}")
        return

    pat_index   = patterns.patternNumber()
    n_inserted  = 0
    n_realtime  = 0

    for i in range(0, len(payload), 9):
        pitch   = payload[i]
        vel     = payload[i + 1]
        ch      = payload[i + 2]
        start   = _decode_tick(payload[i+3], payload[i+4], payload[i+5])
        dur     = _decode_tick(payload[i+6], payload[i+7], payload[i+8])

        if _try_insert_note(pat_index, pitch, vel, ch, start, dur):
            n_inserted += 1
        else:
            channels.midiNoteOn(ch, pitch, vel)
            n_realtime += 1

    print(f"[FL MCP Bridge] Notes: {n_inserted} inserted, {n_realtime} played realtime")


def _try_insert_note(pat_index, pitch, velocity, channel, start_tick, dur_ticks):
    """Try pattern-level insertion; return True on success."""
    try:
        patterns.addNote(pat_index, start_tick, pitch, dur_ticks, velocity, channel)
        return True
    except (AttributeError, TypeError):
        pass
    try:
        patterns.addNote(start_tick, pitch, dur_ticks, velocity)
        return True
    except (AttributeError, TypeError):
        pass
    return False


def _cmd_save_as(payload):
    filename = "".join(chr(b) for b in payload if 32 <= b <= 126)
    print(f"[FL MCP Bridge] Save (name: {filename!r})")
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
        playing     = int(transport.isPlaying())
    except AttributeError:
        playing = 0

    try:
        bpm_raw = transport.getTempo()
        bpm     = max(20, min(999, int(bpm_raw)))
    except AttributeError:
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
