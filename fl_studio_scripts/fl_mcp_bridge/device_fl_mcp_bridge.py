"""FL Studio MIDI Controller Script — FL MCP Bridge
================================================================
Place this entire folder at:
  macOS:   ~/Documents/Image-Line/FL Studio/Settings/Hardware/fl_mcp_bridge/
  Windows: %USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Hardware\fl_mcp_bridge\

After placing the files:
  1. Open FL Studio → Options → MIDI Settings
  2. Under Input, select your IAC Driver Bus (macOS) or loopMIDI port (Windows)
  3. Click "Enable" and set the controller script to "FL MCP Bridge"
  4. Close and reopen MIDI Settings to confirm it loads (check the output log)

SysEx Protocol (Manufacturer ID 0x7D = non-commercial):
  F0 7D 01 F7               → Play transport
  F0 7D 02 F7               → Stop transport
  F0 7D 03 BPM_HI BPM_LO F7 → Set tempo (BPM = (HI<<7)|LO)
  F0 7D 04 [note_data] F7   → Insert notes (9 bytes per note, see below)
  F0 7D 05 [ascii] F7       → Save project

Note data (9 bytes per note):
  [pitch, velocity, channel, start_b2, start_b1, start_b0, dur_b2, dur_b1, dur_b0]
  Tick values use 3-byte 7-bit encoding: value = (b2<<14)|(b1<<7)|b0

MMC (MIDI Machine Control) is also supported natively by FL Studio:
  F0 7F 7F 06 02 F7 → Play   (sent by fl_play_transport)
  F0 7F 7F 06 01 F7 → Stop   (sent by fl_stop_transport)
"""

# FL Studio Python scripting API modules
import channels
import device
import general
import midi
import patterns
import transport
import ui

# Script metadata
name = "FL MCP Bridge"
version = "1.0"

# Protocol constants (must mirror protocol.py)
_MANUFACTURER_ID = 0x7D
CMD_PLAY     = 0x01
CMD_STOP     = 0x02
CMD_SET_TEMPO = 0x03
CMD_NOTES    = 0x04
CMD_SAVE_AS  = 0x05


# ---------------------------------------------------------------------------
# Lifecycle callbacks
# ---------------------------------------------------------------------------

def OnInit():
    """Called when FL Studio loads the controller script."""
    print(f"[FL MCP Bridge v{version}] Initialized. Listening for SysEx on this MIDI input.")
    device.setHasMeters(False)


def OnDeInit():
    """Called when FL Studio unloads the script."""
    print("[FL MCP Bridge] Deinitialized.")


# ---------------------------------------------------------------------------
# MIDI callbacks
# ---------------------------------------------------------------------------

def OnMidiMsg(event):
    """Pass through unhandled messages to FL Studio."""
    event.handled = False


def OnSysEx(event):
    """Handle incoming SysEx from the MCP server.

    event.sysex contains the raw bytes including F0 and F7.
    """
    data = event.sysex

    # Minimum valid message: F0 7D <cmd> F7 = 4 bytes
    if len(data) < 4:
        return

    if data[0] != 0xF0 or data[-1] != 0xF7:
        return

    # Check for our manufacturer ID
    if data[1] != _MANUFACTURER_ID:
        return

    cmd     = data[2]
    payload = list(data[3:-1])  # strip F0, manufacturer, cmd, F7

    event.handled = True  # prevent FL Studio from processing further

    if cmd == CMD_PLAY:
        _cmd_play()
    elif cmd == CMD_STOP:
        _cmd_stop()
    elif cmd == CMD_SET_TEMPO:
        _cmd_set_tempo(payload)
    elif cmd == CMD_NOTES:
        _cmd_insert_notes(payload)
    elif cmd == CMD_SAVE_AS:
        _cmd_save_as(payload)
    else:
        print(f"[FL MCP Bridge] Unknown command: {cmd:#x}")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _cmd_play():
    """Start FL Studio playback."""
    transport.start()
    print("[FL MCP Bridge] Play")


def _cmd_stop():
    """Stop FL Studio playback."""
    transport.stop()
    print("[FL MCP Bridge] Stop")


def _cmd_set_tempo(payload):
    """Set project BPM from 2-byte 7-bit encoded payload."""
    if len(payload) < 2:
        print("[FL MCP Bridge] set_tempo: payload too short")
        return

    bpm = (payload[0] << 7) | payload[1]
    if not 20 <= bpm <= 999:
        print(f"[FL MCP Bridge] set_tempo: BPM {bpm} out of range (20-999)")
        return

    # transport.setTempo is available in FL Studio 20.9+
    # Falls back to a general MIDI tempo event if unavailable
    try:
        transport.setTempo(bpm)
        print(f"[FL MCP Bridge] Tempo → {bpm} BPM")
    except AttributeError:
        # Older FL Studio versions: use MIDI tempo change via general module
        # tempo in microseconds per beat = 60,000,000 / BPM
        micros = 60_000_000 // bpm
        general.processMIDICC(
            midi.MIDI_TEMPOCHANGE,
            micros & 0x7F,
            (micros >> 7) & 0x7F,
        )
        print(f"[FL MCP Bridge] Tempo → {bpm} BPM (via legacy fallback)")


def _decode_tick(b2, b1, b0):
    """Decode 3 × 7-bit bytes back to a tick value."""
    return (b2 << 14) | (b1 << 7) | b0


def _cmd_insert_notes(payload):
    """Insert notes into the current pattern.

    Each note is 9 bytes:
      [pitch, vel, ch, start_b2, start_b1, start_b0, dur_b2, dur_b1, dur_b0]
    """
    if len(payload) % 9 != 0:
        print(f"[FL MCP Bridge] insert_notes: bad payload length {len(payload)}")
        return

    pat_index = patterns.patternNumber()
    notes_inserted = 0
    notes_played = 0

    for i in range(0, len(payload), 9):
        pitch      = payload[i]
        velocity   = payload[i + 1]
        ch         = payload[i + 2]
        start_tick = _decode_tick(payload[i+3], payload[i+4], payload[i+5])
        dur_ticks  = _decode_tick(payload[i+6], payload[i+7], payload[i+8])

        # Attempt pattern insertion (FL Studio 20+ scripting API)
        inserted = _try_insert_note(pat_index, pitch, velocity, ch, start_tick, dur_ticks)
        if inserted:
            notes_inserted += 1
        else:
            # Fallback: play note in realtime (useful when recording is armed)
            channels.midiNoteOn(ch, pitch, velocity)
            notes_played += 1

    print(
        f"[FL MCP Bridge] Notes: {notes_inserted} inserted into pattern {pat_index}, "
        f"{notes_played} played in realtime"
    )


def _try_insert_note(pat_index, pitch, velocity, channel, start_tick, dur_ticks):
    """Attempt to add a note to the pattern editor.

    Returns True if successful, False if the API isn't available.
    The patterns.addNote signature varies across FL Studio versions —
    this function tries the most common forms.
    """
    try:
        # FL Studio 21+ form: addNote(pattern, time, note, length, velocity, channel)
        patterns.addNote(pat_index, start_tick, pitch, dur_ticks, velocity, channel)
        return True
    except (AttributeError, TypeError):
        pass

    try:
        # Alternative form seen in some versions (0-indexed channel)
        patterns.addNote(start_tick, pitch, dur_ticks, velocity)
        return True
    except (AttributeError, TypeError):
        pass

    return False


def _cmd_save_as(payload):
    """Save the current project. filename in payload is metadata only."""
    filename = "".join(chr(b) for b in payload if 32 <= b <= 126)
    print(f"[FL MCP Bridge] Save project (requested name: {filename!r})")
    try:
        ui.save()
        print("[FL MCP Bridge] Project saved.")
    except Exception as exc:
        print(f"[FL MCP Bridge] Save failed: {exc}")
