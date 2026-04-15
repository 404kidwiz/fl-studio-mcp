# FL Studio MCP

Control FL Studio from Claude (or any MCP client) via MIDI.

```
Claude ──stdio──► fl-studio-mcp (Python) ──MIDI SysEx──► IAC Driver ──► FL Studio
```

---

## Architecture

```
fl-studio-mcp/
├── src/fl_studio_mcp/
│   ├── server.py              # FastMCP server — entry point
│   ├── bridge.py              # Singleton MIDI connection + dry-run state
│   ├── models.py              # Pydantic schemas (Note, ChordStep, inputs)
│   ├── errors.py              # Structured error types
│   ├── protocol.py            # SysEx encode/decode (shared with FL script)
│   └── transports/
│       ├── base.py            # Abstract MIDITransport interface
│       ├── macos.py           # IAC Driver (macOS) — primary
│       └── windows.py         # loopMIDI (Windows) — stub, same interface
│   └── tools/
│       ├── midi_ports.py      # fl_list_midi_ports
│       ├── connection.py      # fl_connect
│       ├── transport_control.py  # fl_play_transport, fl_stop_transport
│       ├── tempo.py           # fl_set_tempo
│       ├── notes.py           # fl_insert_notes, fl_add_chord_progression
│       └── project.py         # fl_save_project_as
└── fl_studio_scripts/
    └── fl_mcp_bridge/
        ├── device_fl_mcp_bridge.py  # FL Studio controller script
        └── name.py
```

**Communication protocol:**
- `play` / `stop` → **MMC SysEx** (`F0 7F 7F 06 0x F7`) — FL Studio handles natively
- `set_tempo`, `insert_notes`, `save_project_as` → **Custom SysEx** (`F0 7D <cmd> ... F7`)
  The FL Studio controller script parses these and calls FL's Python API.

**Dry-run mode:** Pass `dry_run=true` to `fl_connect` (or set `FL_MCP_DRY_RUN=1`).
All tools return a full preview of what would be sent — no MIDI ports opened.

---

## macOS Setup (v1 target)

### 1. Enable the IAC Driver

1. Open **Audio MIDI Setup** (Spotlight → "Audio MIDI Setup")
2. **Window → Show MIDI Studio**
3. Double-click **IAC Driver** → check **"Device is online"**
4. Optionally rename the bus (e.g. "FL Studio Bus")

### 2. Install the FL Studio controller script

```bash
# Copy the bridge script folder to FL Studio's hardware scripts directory
cp -r fl_studio_scripts/fl_mcp_bridge \
  ~/Documents/Image-Line/FL\ Studio/Settings/Hardware/
```

### 3. Configure FL Studio

1. Open FL Studio → **Options → MIDI Settings**
2. Under **Input**, find your IAC Driver bus (e.g. "IAC Driver Bus 1")
3. Click **Enable** ✓
4. Set the **Controller type** dropdown to **"FL MCP Bridge"**
5. Confirm the script loads — check the output log for:
   `[FL MCP Bridge v1.0] Initialized.`

### 4. Install the MCP server

```bash
# Requires Python 3.11+, uv recommended
cd /path/to/fl-studio-mcp
uv sync

# Test MIDI port discovery (no FL Studio needed)
uv run fl-studio-mcp  # starts MCP server over stdio

# Or run tests first
uv run pytest
```

### 5. Add to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "fl-studio": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/fl-studio-mcp",
        "run",
        "fl-studio-mcp"
      ],
      "env": {
        "FL_MCP_PORT": "IAC Driver Bus 1"
      }
    }
  }
}
```

Restart Claude Desktop. You should see "fl-studio" in the MCP tools panel.

---

## Windows Setup (future)

1. Install [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)
2. Create a virtual port named **"FL Studio Bus"**
3. Copy `fl_studio_scripts/fl_mcp_bridge/` to:
   `%USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Hardware\`
4. Same FL Studio MIDI Settings steps as macOS
5. In `claude_desktop_config.json`, set `"FL_MCP_PORT": "FL Studio Bus"`

No tool interface changes required — only the port name differs.

---

## Available Tools

| Tool | Description |
|------|-------------|
| `fl_list_midi_ports` | List available MIDI I/O ports. No connection needed. |
| `fl_connect` | Open the MIDI output port. Supports `dry_run=true`. |
| `fl_play_transport` | Start FL Studio playback (MMC Play). |
| `fl_stop_transport` | Stop FL Studio playback (MMC Stop). |
| `fl_set_tempo` | Set project BPM (20–999). |
| `fl_insert_notes` | Insert up to 128 MIDI notes at specific tick positions. |
| `fl_add_chord_progression` | Insert a chord progression (major, minor, dom7, maj7, min7, dim, aug, sus2, sus4). |
| `fl_save_project_as` | Trigger project save in FL Studio. |

---

## Example Claude Prompts

```
"List my MIDI ports and connect FL Studio"

"Set the tempo to 140 BPM"

"Add a I-V-vi-IV chord progression in C major across 4 bars"

"Insert a basic drum pattern kick on beats 1 and 3 (pitch 36, channel 9)"

"Play the transport and save the project as 'BeatSession01'"
```

**Chord progression example prompt for Claude:**
```
Connect to FL Studio on port "IAC Driver Bus 1",
set tempo to 128 BPM,
then add a ii-V-I jazz progression in C major starting at bar 1:
  Dm7 (D=62, min7) at bar 1, Am7 (A=69, min7) at bar 2, Cmaj7 (C=60, maj7) at bar 3
Each chord should be a whole note (384 ticks).
```

---

## Dry-Run Mode

Explore the full tool surface without FL Studio or a MIDI port:

```json
// In fl_connect:
{"port_name": "IAC Driver Bus 1", "dry_run": true}
```

Or via environment variable:
```bash
FL_MCP_DRY_RUN=1 uv run fl-studio-mcp
```

Dry-run responses include `"dry_run": true` and a `"would_send_bytes"` hex preview.

---

## SysEx Protocol Reference

```
Play transport:   F0 7F 7F 06 02 F7          (MMC standard)
Stop transport:   F0 7F 7F 06 01 F7          (MMC standard)
Set tempo:        F0 7D 03 BPM_HI BPM_LO F7
                  BPM = (BPM_HI << 7) | BPM_LO
Insert notes:     F0 7D 04 [N × 9 bytes] F7
                  Per note: pitch vel ch start_b2 start_b1 start_b0 dur_b2 dur_b1 dur_b0
                  Tick = (b2<<14) | (b1<<7) | b0   [7-bit safe, max ~2M ticks]
Save project:     F0 7D 05 [ASCII filename bytes] F7
```

Tick reference at 96 PPQ (FL Studio default):
| Duration | Ticks |
|----------|-------|
| Whole note | 384 |
| Half note | 192 |
| Quarter note | 96 |
| 8th note | 48 |
| 16th note | 24 |

---

## Limitations (v1)

- **Note insertion** requires FL Studio 20+ for the `patterns.addNote` API.
  On older versions, notes are played in realtime via `channels.midiNoteOn`
  (arm recording in FL Studio to capture them into a pattern).
- **save_project_as** calls `ui.save()` — it saves to the *current* project path.
  To save under a new name, rename the project in FL Studio first.
- MMC play/stop works without the controller script loaded (FL Studio handles it).
  All other commands require the FL MCP Bridge script to be active.

---

## Development

```bash
uv sync
uv run pytest -v

# Verify server starts (Ctrl+C to exit)
uv run fl-studio-mcp
```

Protocol changes belong in `protocol.py` — keep it in sync with the FL Studio
script's parsing logic in `device_fl_mcp_bridge.py`.
