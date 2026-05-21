# FL Studio MCP

Control FL Studio from Claude (or any MCP client) via MIDI — bidirectional, type-safe, dry-run-capable.

```
Claude ──stdio──► fl-studio-mcp (Python) ──MIDI SysEx──► IAC Driver ──► FL Studio
                                          ◄──MIDI SysEx──────────────────────────
```

---

## Architecture

```
fl-studio-mcp/
├── src/fl_studio_mcp/
│   ├── server.py              # FastMCP server — entry point
│   ├── cli.py                 # Click-based CLI entry point
│   ├── bridge.py              # Singleton MIDI connection + response queue
│   ├── models.py              # Pydantic schemas (Note, ChordStep, inputs)
│   ├── errors.py              # Structured error types
│   ├── protocol.py            # SysEx encode/decode (shared with FL script)
│   └── transports/
│       ├── base.py            # Abstract MIDITransport interface
│       ├── macos.py           # IAC Driver (macOS) — primary
│       └── windows.py         # loopMIDI (Windows) — stub, same interface
│   └── tools/
│       ├── midi_ports.py      # fl_list_midi_ports
│       ├── connection.py      # fl_connect, fl_disconnect
│       ├── transport_control.py  # fl_play_transport, fl_stop_transport
│       ├── tempo.py           # fl_set_tempo
│       ├── notes.py           # fl_insert_notes, fl_add_chord_progression
│       ├── project.py         # fl_save_project
│       ├── status.py          # fl_get_status  ← bidirectional
│       ├── channels.py        # fl_list_channels, fl_set_channel_volume, fl_set_channel_pan  ← bidirectional
│       ├── patterns.py        # fl_create_pattern, fl_select_pattern
│       ├── pattern_list.py    # fl_list_patterns  ← bidirectional
│       └── mixing.py          # fl_panic, fl_mute_channel, fl_solo_channel
├── fl_studio_scripts/
│   └── fl_mcp_bridge/
│       └── device_fl_mcp_bridge.py  # FL Studio controller script (v1.4)
└── tests/
```

---

## Tools Reference (19 total)

### Connection

| Tool | Description |
|------|-------------|
| `fl_list_midi_ports` | List all available MIDI input/output ports |
| `fl_connect` | Connect to FL Studio via MIDI. Set `dry_run=true` to preview without sending |
| `fl_disconnect` | Close active MIDI input and output ports cleanly, resetting connection state |

### Transport

| Tool | Description |
|------|-------------|
| `fl_play_transport` | Start playback |
| `fl_stop_transport` | Stop playback |
| `fl_set_tempo` | Set BPM (20–999) |

### Notes

| Tool | Description |
|------|-------------|
| `fl_insert_notes` | Trigger notes realtime. Enable Record in FL Studio to record them |
| `fl_add_chord_progression` | Trigger chords realtime by root + quality. Enable Record in FL Studio to record them |

### Project

| Tool | Description |
|------|-------------|
| `fl_save_project` | Save the current project (Ctrl+S equivalent) |

### Status & Channels (bidirectional — require FL MCP Bridge script)

| Tool | Description |
|------|-------------|
| `fl_get_status` | Query transport state, BPM, current pattern index, channel count |
| `fl_list_channels` | List all channel rack instruments by name |
| `fl_set_channel_volume` | Set a channel's volume (0–127, 100 = unity gain) |
| `fl_set_channel_pan` | Set a channel's panning (0–127, 64 = center) |

### Patterns

| Tool | Description |
|------|-------------|
| `fl_create_pattern` | Create the next empty pattern slot |
| `fl_select_pattern` | Jump to a pattern by index |
| `fl_list_patterns` | List all pattern names (bidirectional — requires bridge script) |

### Mixing

| Tool | Description |
|------|-------------|
| `fl_panic` | Send All Notes Off + All Sound Off to all 16 MIDI channels immediately |
| `fl_mute_channel` | Mute or unmute a channel rack slot |
| `fl_solo_channel` | Solo or un-solo a channel rack slot |

---

## Quick Start (macOS)

### 1. Enable IAC Driver

Open **Audio MIDI Setup** → MIDI Studio → Double-click "IAC Driver" → check **Device is online** → create a bus named **"IAC Driver Bus 1"** if one doesn't exist.

### 2. Install

```bash
# From the project root
uv sync
```

### 3. Install the FL Studio Controller Script

Copy the bridge folder into FL Studio's hardware scripts directory:

```bash
cp -r fl_studio_scripts/fl_mcp_bridge \
  ~/Documents/Image-Line/FL\ Studio/Settings/Hardware/
```

Then in FL Studio:
1. **Options → MIDI Settings**
2. Under **Input**, select your IAC Driver port → click **Enable**
3. Set the **Controller type** to **FL MCP Bridge**
4. Expand the port row → set the same port for **Output** too (required for bidirectional responses)
5. Close and reopen MIDI Settings — the script prints `[FL MCP Bridge v1.4] Initialized` in the output log

### 4. Add to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "fl_studio_mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/fl-studio-mcp",
        "fl-studio-mcp"
      ]
    }
  }
}
```

Restart Claude Desktop. You should see the FL Studio tools in the tool picker.

### 5. Connect and verify

Ask Claude:
```
Call fl_list_midi_ports to see what's available.
Then call fl_connect with the IAC Driver port name.
Then call fl_get_status to verify the connection.
```

---

## Standalone CLI Interface

In addition to the MCP server, `fl-studio-mcp` installs a standalone command line tool `fl-studio` powered by `click` for direct shell control.

The CLI stores its port connection preferences in `~/.fl_studio_mcp.json` to enable stateless invocations for other commands:

```bash
# List all MIDI ports available on the system
uv run fl-studio ports

# Connect to a MIDI port and save connection configuration
uv run fl-studio connect --port "IAC Driver Bus 1" --dry-run

# Get bridge connection and live FL Studio status
uv run fl-studio status

# Play, stop, panic, or save the project
uv run fl-studio play
uv run fl-studio stop
uv run fl-studio panic
uv run fl-studio save

# Set project tempo (BPM)
uv run fl-studio tempo 130

# Channels commands
uv run fl-studio channels list
uv run fl-studio channels volume <ch_idx> <val>
uv run fl-studio channels pan <ch_idx> <val>
uv run fl-studio channels mute <ch_idx> [--unmute]
uv run fl-studio channels solo <ch_idx> [--unsolo]

# Patterns commands
uv run fl-studio patterns list
uv run fl-studio patterns select <pat_idx>
uv run fl-studio patterns create

# Insert note or chord progression step (realtime notes)
uv run fl-studio notes insert --pitch C4 --velocity 100 --start 0 --duration 96
uv run fl-studio chord C4 major --velocity 100 --start 0 --duration 384

# Start the FastMCP server for Claude Desktop or other MCP clients
uv run fl-studio serve

# Disconnect MIDI ports and clear saved configuration
uv run fl-studio disconnect
```

---

## Dry-Run Mode

Pass `dry_run=true` to `fl_connect` (or set `FL_MCP_DRY_RUN=1` in the environment) to run without sending any MIDI. All tools return what they *would* send, including exact SysEx bytes.

```bash
FL_MCP_DRY_RUN=1 uv run fl-studio-mcp
```

---

## Bidirectional Setup

Tools marked **bidirectional** (`fl_get_status`, `fl_list_channels`, `fl_list_patterns`) send a query and wait for FL Studio to respond over the MIDI input port.

Requirements:
- The FL MCP Bridge controller script must be loaded in FL Studio
- Both input **and** output must be assigned to the same IAC Driver port in MIDI Settings
- `fl_connect` auto-detects the input port from the same partial name match as the output

If FL Studio doesn't respond in time, the tool returns `{"error": "TIMEOUT", "hint": "..."}` with setup instructions.

---

## SysEx Protocol

**Manufacturer ID: `0x7D`** (non-commercial / development)

### Server → FL Studio

| Cmd  | Hex  | Payload |
|------|------|---------|
| play | `F0 7D 01 F7` | — |
| stop | `F0 7D 02 F7` | — |
| set_tempo | `F0 7D 03 BPM_HI BPM_LO F7` | 7-bit encoded BPM |
| insert_notes | `F0 7D 04 [...] F7` | N × 9 bytes per note |
| save | `F0 7D 05 F7` | — |
| query_status | `F0 7D 06 F7` | — → responds 0x10 |
| query_channels | `F0 7D 07 F7` | — → responds 0x11 |
| set_channel_vol | `F0 7D 08 ch_idx vol F7` | both 0-127 |
| new_pattern | `F0 7D 09 F7` | — |
| select_pattern | `F0 7D 0A pat_idx F7` | 0-127 |
| query_patterns | `F0 7D 0C F7` | — → responds 0x12 |
| mute_channel | `F0 7D 0D ch_idx is_muted F7` | is_muted: 0 or 1 |
| solo_channel | `F0 7D 0E ch_idx is_soloed F7` | toggle semantics in FL |
| set_channel_pan | `F0 7D 13 ch_idx pan F7` | both 0-127 |

### FL Studio → Server

| Resp | Hex | Payload |
|------|-----|---------|
| status | `F0 7D 10 playing bpm_hi bpm_lo pat_idx ch_count F7` | |
| channels | `F0 7D 11 count [name_len name_bytes...] F7` | |
| patterns | `F0 7D 12 count [name_len name_bytes...] F7` | |

### MIDI Panic

`fl_panic` sends **standard MIDI CC** (not SysEx) directly on all 16 channels:
- CC 123 — All Notes Off
- CC 120 — All Sound Off  
- CC 121 — Reset All Controllers

This works **without the bridge script** since FL Studio handles these CCs natively.

---

## Note Encoding

96 ticks = 1 quarter note (FL Studio default PPQ).

```
Quarter: 96 ticks
Eighth:  48 ticks
Half:    192 ticks
Whole:   384 ticks
```

Tick values are 3-byte 7-bit encoded: `value = (b2 << 14) | (b1 << 7) | b0`

---

## Development

```bash
# Install with dev deps
uv sync --all-extras --dev

# Run tests (no MIDI hardware required)
uv run pytest tests/ -v

# Run in dry-run mode
FL_MCP_DRY_RUN=1 uv run fl-studio-mcp

# Inspect tools interactively
npx @modelcontextprotocol/inspector uv run fl-studio-mcp
```

---

## Windows

The transport layer is abstracted behind `MIDITransport`. On Windows, use [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) to create a virtual port instead of the IAC Driver. The tool interfaces and SysEx protocol are identical.

---

## Troubleshooting

**Notes stuck / hanging** — Call `fl_panic`. It fires 48 CC messages directly, no script needed.

**`fl_get_status` times out** — Verify the bridge script is loaded and the IAC Driver output is assigned in MIDI Settings. The script must print its init message in the FL output log.

**No ports listed** — On macOS, open Audio MIDI Setup and confirm the IAC Driver is online. On Windows, start loopMIDI before launching FL Studio.

**`fl_connect` fails** — Port name matching is partial and case-insensitive. Pass `"IAC"` and it'll match `"IAC Driver Bus 1"`. Use `fl_list_midi_ports` first to see exact names.
