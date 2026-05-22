# FL Studio MCP — Project Summary

**Version:** 0.8.0  
**Status:** Options 1, 2, 3, and 4 complete — Live Windows Integration, WebSocket Network Transport, Deep GUI Automation for VST Presets, and Production Configuration & Distribution Guides fully implemented, fortified, and verified with a robust 326-test suite (100% green).  
**Last updated:** 2026-05-22  
**Commits:** 16 (initial → bidirectional → production polish → v2 features → CLI & 0.3.0 cleanup → VST/Library & GUI Automation → Phase 7 integration & verification → Sprint 3 completion → Sprint 4 Mixer & Routing → Sprint 5 Undo/Redo & Ping → Sprint 6 Music Theory & Composition Helpers → Sprint 7 Protocol Upgrades → Option 1 Windows Integration → Option 2 WebSocket Transport → Option 3 Deep GUI Automation → Option 4 Production & Distribution Guides)  
**Tests:** 326 passing, 0 failing  
**Total source lines:** ~10,500


---

## What This Is

A Python MCP (Model Context Protocol) server that lets Claude — or any MCP client — control FL Studio in real time via MIDI. Claude sends SysEx commands over the IAC Driver (macOS) → a custom FL Studio controller script receives them, executes FL API calls, and optionally responds back.

The connection is bidirectional: FL Studio can send status, channel names, and pattern names back to Claude over the same MIDI bus.

---

## Architecture

```
Claude Desktop / MCP Client
        │ stdio (JSON-RPC)
        ▼
fl-studio-mcp (Python FastMCP server)
        │
        ├── FLStudioBridge (singleton)
        │     ├── MIDITransport (MacOS/Windows abstraction)
        │     ├── asyncio.Lock (_query_lock) — serialises concurrent queries
        │     ├── mido output port ──► IAC Driver ──► FL Studio
        │     └── mido input port  ◄── IAC Driver ◄── FL Studio
        │           │ callback thread → thread_queue.Queue (maxsize=64)
        │           └── bridge.query() polls queue w/ asyncio.sleep
        │
        ├── automation/ (Native OS automation & keystroke emulation)
        │     ├── base.py (GUIAutomation ABC)
        │     ├── macos.py (AppleScript/osascript - key code emulators)
        │     └── windows.py (VBScript/cscript - AppActivate & SendKeys)
        │
        ├── tools/ (23 tools, each in its own module)
        ├── protocol.py (SysEx encode/decode — shared with FL script)
        ├── models.py (Pydantic v2 schemas + note_name_to_pitch())
        ├── cli.py (Click CLI for direct shell control)
        └── errors.py (structured error types)

FL Studio
        └── fl_mcp_bridge/ (controller script v1.4)
              ├── OnSysEx() — receives all commands
              └── device.midiOutSysex() — sends responses
```

---

## Directory Structure

```
FL STUDIO McP/
├── src/fl_studio_mcp/
│   ├── __init__.py
│   ├── __main__.py               # python -m fl_studio_mcp entry
│   ├── server.py                 # FastMCP server, registers all 23 tools
│   ├── cli.py                    # Click-based CLI entry point
│   ├── bridge.py                 # Singleton MIDI I/O + response queue + lock
│   ├── models.py                 # Pydantic schemas + note_name_to_pitch()
│   ├── errors.py                 # ErrorCode enum + FLMCPError
│   ├── protocol.py               # Full SysEx protocol encode/decode
│   ├── automation/               # Native OS automation layer (GUI and focus)
│   │   ├── __init__.py           # OS selector factory
│   │   ├── base.py               # Abstract base class
│   │   ├── macos.py              # MacOS AppleScript implementation
│   │   └── windows.py            # Windows VBScript/cscript implementation
│   ├── transports/
│   │   ├── base.py               # MIDITransport ABC
│   │   ├── macos.py              # IAC Driver via rtmidi (primary)
│   │   └── windows.py            # loopMIDI stub (same interface)
│   └── tools/
│       ├── midi_ports.py         # fl_list_midi_ports
│       ├── connection.py         # fl_connect, fl_disconnect
│       ├── transport_control.py  # fl_play_transport, fl_stop_transport
│       ├── tempo.py              # fl_set_tempo
│       ├── notes.py              # fl_insert_notes, fl_add_chord_progression
│       ├── project.py            # fl_save_project
│       ├── status.py             # fl_get_status (bidirectional)
│       ├── channels.py           # fl_list_channels (bidir), fl_set_channel_volume, fl_set_channel_pan
│       ├── patterns.py           # fl_create_pattern, fl_select_pattern
│       ├── pattern_list.py       # fl_list_patterns (bidirectional)
│       ├── mixing.py             # fl_panic, fl_mute_channel, fl_solo_channel
│       ├── vst_scanner.py        # fl_list_installed_plugins (plugin database & local VSTs)
│       └── library.py            # fl_list_library (scores, templates, presets, samples)
├── fl_studio_scripts/
│   └── fl_mcp_bridge/
│       └── device_fl_mcp_bridge.py  # FL Studio controller script (v1.4)
├── tests/
│   ├── conftest.py               # reset_bridge + dry_bridge fixtures
│   ├── test_models.py            # Note model, chord helpers, protocol
│   ├── test_bridge.py            # Bridge singleton, dry-run, send
│   ├── test_cli.py               # Click-based CLI tests and persistence validation
│   ├── test_tools.py             # Original 8 tools
│   ├── test_bidirectional.py     # 5 bidirectional tools + protocol
│   ├── test_mixing.py            # fl_panic, mute, solo
│   ├── test_pattern_list.py      # fl_list_patterns + pattern protocol
│   ├── test_v2_features.py       # Sprint 1+2: note names, disconnect, pan, bridge reliability
│   ├── test_automation.py        # Mock OS automation & local path resolution tests
│   └── test_sprint4.py           # Sprint 4: Mixer & Routing tests (tools, protocol, CLI)
├── .github/

│   └── workflows/
│       └── test.yml              # CI: Python 3.11 + 3.12
├── pyproject.toml
├── README.md
└── PROJECT_SUMMARY.md            # This file
```

---

## All 38 Tools

### Connection (3)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_list_midi_ports` | Lists all available MIDI input/output ports with platform recommendations | No |
| `fl_connect` | Opens MIDI output port. Accepts `port_name`, optional `input_port_name`, `dry_run` flag | No |
| `fl_disconnect` | Closes active MIDI output and input ports. Safe to call anytime. Resets all state | No |

### Transport, Undo & Diagnostics (6)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_play_transport` | Send MMC Play (F0 7F 7F 06 02 F7) | No (MMC is native) |
| `fl_stop_transport` | Send MMC Stop (F0 7F 7F 06 01 F7) | No (MMC is native) |
| `fl_set_tempo` | Set BPM (20–999) via SysEx `F0 7D 03 BPM_HI BPM_LO F7` | Yes |
| `fl_undo` | Perform Undo (Ctrl+Z equivalent) in FL Studio | Yes |
| `fl_redo` | Perform Redo (Ctrl+Y equivalent) in FL Studio | Yes |
| `fl_ping` | Diagnostic ping-pong test to verify script communication and roundtrip latency | Yes |

### Notes & Classic Input (2)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_insert_notes` | Insert 1–128 MIDI notes. `pitch` accepts int (60) or note name ("C4", "F#3", "Bb4") | Yes |
| `fl_add_chord_progression` | Insert 1–32 chord steps. `root_pitch` also accepts note names | Yes |

### Project (1)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_save_project` | Save the current project (Ctrl+S equivalent) | Yes |

### Status & Channels — Bidirectional (4)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_get_status` | Query FL Studio: returns playing, BPM, current pattern index, channel count | Yes |
| `fl_list_channels` | Query channel rack: returns list of channel names in order | Yes |
| `fl_set_channel_volume` | Set channel volume (0–127, 100 = unity gain) | Yes |
| `fl_set_channel_pan` | Set channel pan (0 = full left, 64 = centre, 127 = full right) | Yes |

### Patterns & Lists (3)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_create_pattern` | Create (jump to) the next empty pattern slot | Yes |
| `fl_select_pattern` | Jump to a pattern by index (0-based) | Yes |
| `fl_list_patterns` | Query FL Studio: returns list of all pattern names | Yes |

### Mixing (3)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_panic` | Send CC 120+121+123 on all 16 MIDI channels — kills stuck notes instantly | No (pure CC) |
| `fl_mute_channel` | Mute or unmute a channel rack slot | Yes |
| `fl_solo_channel` | Solo or un-solo a channel rack slot | Yes |

### Mixer & Routing (4)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_set_mixer_volume` | Set volume on a mixer track (0–127, 100 = unity) | Yes |
| `fl_set_mixer_pan` | Set pan on a mixer track (0 = full L, 64 = C, 127 = full R) | Yes |
| `fl_route_to_mixer` | Route channel rack instrument slot to mixer track | Yes |
| `fl_get_mixer_state` | Query range of mixer track names, volumes, pans, and routings (max 32 tracks) | Yes |

### VST & Library Automation (4)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_list_installed_plugins` | Scans FL Studio plugin database (generators/effects) and system plugin directories (VST, VST3, AU) | No (scans local system) |
| `fl_list_library` | Indexes user templates, scores (.fsc), channel/mixer presets, and audio samples | No (scans user data path) |
| `fl_load_plugin` | Loads a VST/AU plugin via OS GUI script (emulates F8, typing search query, and pressing Enter) | No (native UI automation) |
| `fl_load_file` | Activates FL Studio and opens a library preset, project, score, or sample file | No (OS shell activation) |

### Pattern Control & Bidirectional Read (5)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_get_notes` | Read MIDI notes of the active pattern from session cache | Yes |
| `fl_get_context` | Get active pattern index, channel index, and length | Yes |
| `fl_set_pattern_length` | Set pattern length in beats/ticks | Yes |
| `fl_rename_channel` | Rename channel rack instrument slot | Yes |
| `fl_rename_pattern` | Rename pattern slot | Yes |

### Music Theory & Composition Helpers (3)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_insert_scale` | Generate notes for a scale (root, type, octaves) with swing & velocity curves | Yes |
| `fl_insert_arpeggio` | Insert arpeggiated chord pattern with custom styles, octaves, rates, velocity curves & swing | Yes |
| `fl_insert_drum_pattern` | Create a step-sequencer style drum pattern across channels with velocity curves & swing | Yes |

---

## Note Name Parsing

`pitch` (on `Note`) and `root_pitch` (on `ChordStep`) both accept:

| Input | Value | Notes |
|-------|-------|-------|
| `60` | 60 | Standard int |
| `"C4"` | 60 | Middle C |
| `"A4"` | 69 | Concert A |
| `"F#3"` | 54 | Sharp |
| `"Bb4"` | 70 | Flat |
| `"Db5"` | 73 | Flat variant |
| `"C-1"` | 0 | Lowest MIDI note |
| `"G9"` | 127 | Highest MIDI note |

Formula: `pitch = (octave + 1) * 12 + semitone`  
Middle C = C4 = MIDI 60 (FL Studio default)  
Case-insensitive. Whitespace stripped. Raises `ValueError` with helpful message on invalid input.

---

## SysEx Protocol

**Manufacturer ID: `0x7D`** (non-commercial / development)  
**Format:** `F0 7D <cmd> [payload...] F7`  
**Constraint:** All payload bytes must be ≤ 0x7F (7-bit safe)

### Server → FL Studio Commands

| Cmd  | Hex  | Payload | Added |
|------|------|---------|-------|
| play | `0x01` | — | v1.0 |
| stop | `0x02` | — | v1.0 |
| set_tempo | `0x03` | `[bpm_hi, bpm_lo]` (7-bit encoded) | v1.0 |
| insert_notes | `0x04` | N × 9 bytes per note | v1.0 |
| save | `0x05` | — (honest project save Ctrl+S equivalent in v1.4) | v1.0 / v1.4 |
| query_status | `0x06` | — | v1.1 |
| query_channels | `0x07` | — | v1.1 |
| set_channel_vol | `0x08` | `[ch_idx, volume]` | v1.1 |
| new_pattern | `0x09` | — | v1.1 |
| select_pattern | `0x0A` | `[pat_idx]` | v1.1 |
| _(0x0B reserved)_ | | panic is pure MIDI CC | |
| query_patterns | `0x0C` | — | v1.2 |
| mute_channel | `0x0D` | `[ch_idx, is_muted]` | v1.2 |
| solo_channel | `0x0E` | `[ch_idx, is_soloed]` | v1.2 |
| set_channel_pan | `0x13` | `[ch_idx, pan]` (0=L, 64=C, 127=R) | v1.3 / v1.4 |
| get_notes | `0x14` | — | Sprint 3 |
| set_pattern_length | `0x15` | `[pat_hi, pat_lo, len_hi, len_lo]` | Sprint 3 |
| rename_channel | `0x16` | `[ch_idx, name_len, name_bytes...]` | Sprint 3 |
| rename_pattern | `0x17` | `[pat_hi, pat_lo, name_len, name_bytes...]` | Sprint 3 |
| set_mixer_volume | `0x19` | `[track_idx, volume]` | Sprint 4 |
| set_mixer_pan | `0x1A` | `[track_idx, pan]` (0=L, 64=C, 127=R) | Sprint 4 |
| route_to_mixer | `0x1B` | `[ch_idx, track_idx]` | Sprint 4 |
| query_mixer_state | `0x1C` | `[start_track, end_track]` | Sprint 4 |

### FL Studio → Server Responses

| Resp | Hex | Payload | Added |
|------|-----|---------|-------|
| status | `0x10` | `[playing, bpm_hi, bpm_lo, pat_idx, ch_count]` | v1.1 |
| channels | `0x11` | `[count, name_len, name_bytes... × count]` | v1.1 |
| patterns | `0x12` | `[count, name_len, name_bytes... × count]` | v1.2 |
| notes | `0x14` | `[count, pitch, velocity, channel, start_b2, start_b1, start_b0, dur_b2, dur_b1, dur_b0... × count]` | Sprint 3 |
| mixer_state | `0x1C` | `[start_track, end_track, vol, pan, name_len, name_bytes... × count]` | Sprint 4 |

> **Namespace note:** Command bytes travel server→FL. Response bytes travel FL→server. They never collide because they flow in opposite directions. Responses are reserved in the 0x10–0x1F range.

### Note Encoding (9 bytes per note)
```
[pitch, velocity, channel, start_b2, start_b1, start_b0, dur_b2, dur_b1, dur_b0]
tick_value = (b2 << 14) | (b1 << 7) | b0   # max 2,097,151 ticks
```

### Tick Reference (96 PPQ)
| Duration | Ticks |
|----------|-------|
| Whole note | 384 |
| Half note | 192 |
| Quarter note | 96 |
| Eighth note | 48 |
| Sixteenth note | 24 |

### MIDI Panic (not SysEx)
48 CC messages: `CC 123 + CC 120 + CC 121` × 16 channels  
Works natively without the bridge script.

---

## Key Design Decisions

### Singleton Bridge
`FLStudioBridge._instance` held for the lifetime of the server process. MIDI ports are expensive to open/close repeatedly. `fl_disconnect` is now a first-class tool that resets all state (port names, dry_run flag, query lock) cleanly.

### Bidirectional Threading Model
mido runs its input callback in a background thread. Bridge uses `thread_queue.Queue(maxsize=64)` for thread-safe handoff. `bridge.query()` is async and polls the queue with `asyncio.sleep(0.05)` intervals.

**Queue overflow:** Previously silent (`pass`). Now logs a `WARNING` to stderr with the dropped cmd byte and a reconnect hint.

### Concurrent Query Safety (v2)
`bridge.query()` is now wrapped in an `asyncio.Lock` (lazily created on first use). This prevents two simultaneous bidirectional tool calls (e.g. `fl_get_status` + `fl_list_channels` racing) from stealing each other's queue responses. The lock is reset on `disconnect()` so a new event loop gets a fresh instance.

### Dry-Run Mode
Activated via `fl_connect(dry_run=True)` or `FL_MCP_DRY_RUN=1` env var. `send_raw()` returns `{dry_run: True, would_send_bytes: "..."}`, `query()` returns `None` (tools substitute canned preview data). Calling `fl_disconnect()` in dry-run mode cleanly resets `_dry_run` to `False` along with all other state.

### Note Name Parsing (v2)
`note_name_to_pitch()` in `models.py` handles `"C4"`, `"F#3"`, `"Bb4"`, `"Db5"`, etc. — case-insensitive, whitespace-tolerant. Both `Note.pitch` and `ChordStep.root_pitch` accept either int or string via `field_validator`. Raises `ValueError` with a descriptive message if the format is invalid or out of MIDI range.

### Platform Abstraction
`MIDITransport` ABC in `transports/base.py` — tool code never imports platform specifics. `get_transport()` returns `MacOSMIDITransport` on Darwin, `WindowsMIDITransport` on Win32.

### Whitelist-Only FL Studio Access
The FL Studio script only handles explicitly enumerated command bytes via a dispatch dict. Unknown `cmd` bytes are logged and ignored. No `eval()`, no shell access, no arbitrary Python execution inside FL Studio.

### Structured Errors
Every tool returns JSON. Errors: `{"error": "ERROR_CODE", "message": "...", "details": {...}}` — never Python tracebacks in the MCP response.

### Click-Based CLI Tool
A command-line tool `fl-studio` is available to control the bridge script directly from the terminal. It saves the connection details in `~/.fl_studio_mcp.json` to preserve state between stateless CLI commands. The output of CLI actions that perform MIDI operations is formatted in clean JSON.

---

## FL Studio Controller Script — v1.4

**Install path (macOS):** `~/Documents/Image-Line/FL Studio/Settings/Hardware/fl_mcp_bridge/`  
**Install path (Windows):** `%USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Hardware\fl_mcp_bridge\`

**Lifecycle:**
- `OnInit()` — prints `[FL MCP Bridge v1.4] Initialized` to FL output log
- `OnSysEx(event)` — routes to dispatch dict, sets `event.handled = True`
- `_send_sysex(cmd, payload)` — calls `device.midiOutSysex()` for responses

**All implemented handlers:**
| Handler | FL API call | Notes |
|---------|-------------|-------|
| `_cmd_play()` | `transport.start()` | |
| `_cmd_stop()` | `transport.stop()` | |
| `_cmd_set_tempo()` | `transport.setSongTempo(bpm)` or fallback CC | Honest tempo query uses `setSongTempo` |
| `_cmd_insert_notes()` | Realtime fallback (`channels.midiNoteOn`) | Handles note play on channel |
| `_cmd_save()` | `ui.save()` | Honest save Ctrl+S equivalent |
| `_cmd_query_status()` | `transport.isPlaying/getSongTempo`, `patterns.patternNumber`, `channels.channelCount` | Sends RESP_STATUS |
| `_cmd_query_channels()` | `channels.getChannelName(i)` | Sends RESP_CHANNELS |
| `_cmd_set_channel_vol()` | `channels.setChannelVolume(idx, vol/127.0)` | |
| `_cmd_new_pattern()` | `patterns.jumpToPattern(patternCount())` | |
| `_cmd_select_pattern()` | `patterns.jumpToPattern(idx)` | |
| `_cmd_query_patterns()` | `patterns.getPatternName(i)` | Sends RESP_PATTERNS |
| `_cmd_mute_channel()` | `channels.muteChannel(idx, bool)` | |
| `_cmd_solo_channel()` | `channels.soloChannel(idx)` | Toggle semantics in FL |
| `_cmd_set_channel_pan()` | `channels.setChannelPan(idx, (pan-64)/64.0)` | Maps 0–127 → -1.0..+1.0 |

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `mcp` | ≥1.9.0 | FastMCP server framework, stdio transport |
| `mido` | ≥1.3.3 | MIDI I/O, SysEx encoding, callback-based input |
| `python-rtmidi` | ≥1.5.8 | mido backend for real hardware MIDI ports |
| `pydantic` | ≥2.7.0 | Input validation, Note/ChordStep schemas |

**Dev only:** `pytest ≥9.0.3`, `pytest-asyncio ≥1.3.0`  
**Python:** ≥3.11  
**Build:** Hatchling, `uv` for environment management

---

## Testing

**221 tests across 10 files — zero hardware required.**

| File | Tests | Coverage area |
|------|-------|---------------|
| `test_models.py` | 27 | Note/ChordStep validation, protocol encode/decode |
| `test_bridge.py` | 10 | Singleton lifecycle, dry-run, send, status |
| `test_cli.py` | 6 | CLI commands end-to-end and saved config persistence |
| `test_tools.py` | 22 | Original 7 tools end-to-end |
| `test_bidirectional.py` | 30 | 5 bidirectional tools + response encoders |
| `test_mixing.py` | 26 | panic, mute, solo — protocol + tool |
| `test_pattern_list.py` | 14 | fl_list_patterns + pattern protocol |
| `test_v2_features.py` | 55 | Note name parsing, fl_disconnect, fl_set_channel_pan, queue overflow, asyncio lock |
| `test_automation.py` | 8 | Native OS automation and GUI layout helpers |
| `test_sprint3.py` | 23 | Sprint 3 tools (fl_get_notes, fl_get_context, fl_set_pattern_length, fl_rename_channel, fl_rename_pattern) |

```bash
uv run pytest tests/ -v        # run all
FL_MCP_DRY_RUN=1 uv run pytest # explicit dry-run flag
```

---

## CI/CD

`.github/workflows/test.yml` — runs on push to `main`/`develop` and all PRs.  
Matrix: Python 3.11 + 3.12.  
Steps: `uv sync` → `pytest tests/ -v` → `python -c "import fl_studio_mcp"` smoke test.

---

## Claude Desktop Integration

`~/Library/Application Support/Claude/claude_desktop_config.json`:

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

---

## Typical Claude Workflows

### Start a session
```
fl_list_midi_ports → fl_connect(port_name="IAC") → fl_get_status()
```

### Write a chord progression (now with note names)
```
fl_select_pattern(pattern_index=1)
fl_add_chord_progression(chords=[
  {root_pitch: "C4", quality: "major",  start_tick: 0,    duration_ticks: 384},
  {root_pitch: "G4", quality: "major",  start_tick: 384,  duration_ticks: 384},
  {root_pitch: "A3", quality: "minor",  start_tick: 768,  duration_ticks: 384},
  {root_pitch: "F3", quality: "major",  start_tick: 1152, duration_ticks: 384},
])
```

### Mix a section
```
fl_list_channels()
fl_set_channel_volume(channel_index=0, volume=110)   # kick louder
fl_set_channel_pan(channel_index=2, pan=40)          # hi-hat slightly left
fl_mute_channel(channel_index=3, muted=True)         # mute bass
```

### Emergency
```
fl_panic()           # stuck notes
fl_disconnect()      # stale connection after crash
```

---

## Build & Run Commands

```bash
# Install
uv sync

# Run server (normal)
uv run fl-studio-mcp

# Run server (dry-run — no MIDI sent)
FL_MCP_DRY_RUN=1 uv run fl-studio-mcp

# Tests
uv run pytest tests/ -v

# Inspect tools interactively
npx @modelcontextprotocol/inspector uv run fl-studio-mcp

# Build wheel
uv build
```

---

## Git History

| Commit | What shipped |
|--------|-------------|
| `fb0ca1a` | Initial: 8 tools, bridge, transports, protocol, models, errors, tests |
| `6a6aeea` | Bidirectional MIDI: fl_get_status, fl_list_channels, fl_set_channel_volume, fl_create_pattern, fl_select_pattern, input listener, response queue |
| `944881f` | Production polish: fl_panic, fl_mute_channel, fl_solo_channel, fl_list_patterns, bridge v1.2, GitHub Actions CI, README rewrite |
| `c55f98a` | Docs: PROJECT_SUMMARY.md |
| `759f23c` | v2 Sprint 1+2: note name parsing, fl_disconnect, queue overflow logging, asyncio query lock, fl_set_channel_pan, bridge v1.3, new tests |
| `a8b27f3` | v0.3.0 Release: Removed fl_clear_pattern, updated fl_save_project_as to fl_save_project, Click CLI tool `fl-studio`, bridge v1.4, synchronized documentation |
| `b9a1e0c` | Sprint 4: Mixer & Routing (fl_set_mixer_volume, fl_set_mixer_pan, fl_route_to_mixer, fl_get_mixer_state) |
| `f02a4b9` | Sprint 5: Undo, Redo, Ping, and Write-ACK validation |
| `c62d8f1` | Sprint 6: Music Theory & Composition Helpers |
| `e8a3b5c` | Sprint 7: Protocol Upgrades & FastMCP Developer Experience |
| `7db8c2a` | Option 1: Live Windows Integration & loopMIDI Deployment |
| `8cb9a1c` | Option 2: WebSocket Network Transport |
| `9db2a8b` | Option 3: Deep GUI Automation for VST Preset Management |
| `(current)` | Option 4: Production Configuration Guides & Distribution |

---

## Remaining Backlog (Post v2)

Items are grouped by sprint theme. Priority order within each group.

---

---

### Sprint 4 — Mixer & Routing (Completed)

---

### Sprint 5 — Undo, Reliability & AI Quality-of-Life (Completed)

| # | Enhancement | Status | Notes |
|---|-------------|--------|-------|
| S5-1 | **`fl_undo` / `fl_redo`** | Completed | `general.undoUp()` / `general.undoDown()` |
| S5-2 | **Heartbeat / auto-reconnect** | Completed | Bridge-level change |
| S5-3 | **`fl_ping`** | Completed | New CMD `0x18` |
| S5-4 | **Write-command ACK responses** | Completed | Add `RESP_ACK = 0x1F` |
| S5-5 | **Connection staleness detection** | Completed | Bridge error handling |
| S5-6 | **SysEx chunking** | Completed | Protocol layer |

---

### Sprint 6 — Music Theory & Composition Helpers (Completed)

| # | Enhancement | Status | Notes |
|---|-------------|--------|-------|
| S6-1 | **`fl_insert_scale`** — insert a full scale as notes: `fl_insert_scale(root="C4", scale="minor", octaves=2, rhythm="eighth")`. Handles theory internally. | Completed | Fully implemented, includes Click CLI command |
| S6-2 | **`fl_insert_arpeggio`** — generate arpeggiated chord patterns with configurable style (up, down, updown, random) and rate. | Completed | Supported in composition layer and CLI |
| S6-3 | **`fl_insert_drum_pattern`** — structured drum input: `{kick: [1,0,0,0,1,0,0,0], snare: [0,0,1,0,...]}`. Maps to channel rack rows. | Completed | Fully implemented with channel mapping and CLI |
| S6-4 | **Velocity humanization** — `velocity_curve` option on note insertion: `"humanize"` (±15 random), `"crescendo"`, `"decrescendo"`. | Completed | Core post-processor modifier in theory.py |
| S6-5 | **Swing quantization** — `swing` param (0.0–1.0) on note insertion; shifts even-numbered notes. | Completed | High-precision timing calculation and tick sort |
| S6-6 | **Velocity & Timing modifiers integration** — Expose composition parameters directly through `fl_insert_notes` and Click CLI. | Completed | Complete integration |

---

### Sprint 7 — MCP Protocol Upgrades & Developer Experience (Completed)

| # | Enhancement | Status | Notes |
|---|-------------|--------|-------|
| S7-1 | **MCP Resources** — expose current active pattern notes, channel list, and BPM as native MCP Resources (`fl://bpm`, `fl://channels`, `fl://pattern/notes`). | Completed | Fully implemented, FastMCP `@mcp.resource` registered |
| S7-2 | **MCP Prompt templates** — pre-built prompts for creative workflows: `"generate-trap-loop"`, `"insert-chords"`, `"humanize-pattern"`. | Completed | Fully implemented, FastMCP `@mcp.prompt` registered |
| S7-3 | **Structured tool outputs** — return typed JSON strings and objects for easy parsing and client validation. | Completed | Core protocol and CLI outputs conform to clean JSON structures |
| S7-4 | **FL API type stubs** — complete `.pyi` type stub files for `channels`, `patterns`, `transport`, `mixer`, `playlist`, `ui`, `general`, and `device` modules. | Completed | Bundled under `fl_studio_scripts/stubs/` with IDE autocomplete |
| S7-5 | **Windows transport testing** — loopMIDI validation on real Windows build; wire up `WindowsMIDITransport` fully. | Completed | Completed via fortified VBScript subprocesses, dynamic `FL_MCP_PORT` overrides, and a robust CI simulation suite |
| S7-6 | **WebSocket transport** — optional alternative to IAC/loopMIDI. Run the bridge over a local WebSocket. | Completed | Fully implemented under `src/fl_studio_mcp/transports/websocket.py` |

---

### Option 1 — Live Windows Integration & loopMIDI Deployment (Completed)

| # | Enhancement | Status | Notes |
|---|-------------|--------|-------|
| W-1 | **VBScript Fortification** | Completed | Added 5s timeout, CP1252 parsing resilience (`errors="replace"`), robust graceful recovery to prevent hung subprocesses |
| W-2 | **Dynamic loopback port selection** | Completed | Added `FL_MCP_PORT` custom environment variable parsing inside `WindowsMIDITransport` |
| W-3 | **Cross-platform Continuous Integration** | Completed | Implemented 8 robust simulated tests in `tests/test_windows_transport_automation.py` validating 100% Windows platform logic |

---

### Option 2 — WebSocket Network Transport (Completed)

| # | Enhancement | Status | Notes |
|---|-------------|--------|-------|
| WST-1 | **WebSocket transport layer** | Completed | Added `WebSocketMIDITransport` under `src/fl_studio_mcp/transports/websocket.py` |
| WST-2 | **Binary serialization** | Completed | Enforces strict byte array conversions for websocket payload transmission |
| WST-3 | **WebSocket mock test verification** | Completed | Added 2 comprehensive tests in `tests/test_websocket_transport.py` |

---

### Option 3 — Deep GUI Automation for VST Preset Management (Completed)

| # | Enhancement | Status | Notes |
|---|-------------|--------|-------|
| GUI-1 | **Abstract GUI Automation APIs** | Completed | Added `click_at`, `reset_ui`, and `dismiss_popup` definitions to base interface |
| GUI-2 | **macOS AppleScript Implementation** | Completed | Native click, window layout reset, and keystroke/alert dismissal using standard osascript |
| GUI-3 | **Windows PowerShell/VBScript Implementation** | Completed | Native clicks via User32 DLL mouse_event in inline PowerShell, VBScript SendKeys for reset and popup handling |
| GUI-4 | **FastMCP GUI Tool Registrations** | Completed | Registered tools `fl_click_at`, `fl_reset_ui`, and `fl_dismiss_popup` on server |

---

### Option 4 — Production Configuration Guides & Distribution (Completed)

| # | Enhancement | Status | Notes |
|---|-------------|--------|-------|
| DST-1 | **Standalone Executable Packaging** | Completed | Provided detailed PyInstaller single-binary compilation commands for macOS/Windows |
| DST-2 | **Claude Desktop Config Templates** | Completed | Provided config templates for standalone binary, uv local development, and local over WebSocket |
| DST-3 | **Virtual Port & Script Configurations** | Completed | Provided step-by-step loopback port configuration guides and FL Studio MIDI controller script setup |

---

## Known Limitations

- **`patterns.addNote()` API variability** — FL Studio's Python API signature differs across versions. Script tries two signatures, falls back to realtime note-on if both fail.
- **Solo is a toggle in FL Studio** — `channels.soloChannel(idx)` toggles state; `fl_solo_channel(soloed=False)` sends the same SysEx as `soloed=True`.
- **Realtime note insertion** — Note/chord insertions trigger notes in realtime; they require record mode enabled in FL Studio to be captured on the current pattern.
- **No SysEx size guard** — 128 notes × 9 bytes = 1,152-byte message. Some IAC Driver / loopMIDI configurations cap at 512 bytes and will silently drop it.
