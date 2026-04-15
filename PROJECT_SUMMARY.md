# FL Studio MCP — Project Summary

**Version:** 0.2.0  
**Status:** Active development — v2 Sprint 1+2 complete  
**Last updated:** 2026-04-15  
**Commits:** 4 (initial → bidirectional → production polish → v2 features)  
**Tests:** 194 passing, 0 failing  
**Total source lines:** ~5,200

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
        ├── tools/ (20 tools, each in its own module)
        ├── protocol.py (SysEx encode/decode — shared with FL script)
        ├── models.py (Pydantic v2 schemas + note_name_to_pitch())
        └── errors.py (structured error types)

FL Studio
        └── fl_mcp_bridge/ (controller script v1.3)
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
│   ├── server.py                 # FastMCP server, registers all 20 tools
│   ├── bridge.py                 # Singleton MIDI I/O + response queue + lock
│   ├── models.py                 # Pydantic schemas + note_name_to_pitch()
│   ├── errors.py                 # ErrorCode enum + FLMCPError
│   ├── protocol.py               # Full SysEx protocol encode/decode
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
│       ├── project.py            # fl_save_project_as
│       ├── status.py             # fl_get_status (bidirectional)
│       ├── channels.py           # fl_list_channels (bidir), fl_set_channel_volume, fl_set_channel_pan
│       ├── patterns.py           # fl_create_pattern, fl_select_pattern, fl_clear_pattern
│       ├── pattern_list.py       # fl_list_patterns (bidirectional)
│       └── mixing.py             # fl_panic, fl_mute_channel, fl_solo_channel
├── fl_studio_scripts/
│   └── fl_mcp_bridge/
│       └── device_fl_mcp_bridge.py  # FL Studio controller script (v1.3)
├── tests/
│   ├── conftest.py               # reset_bridge + dry_bridge fixtures
│   ├── test_models.py            # Note model, chord helpers, protocol
│   ├── test_bridge.py            # Bridge singleton, dry-run, send
│   ├── test_tools.py             # Original 8 tools
│   ├── test_bidirectional.py     # 5 bidirectional tools + protocol
│   ├── test_mixing.py            # fl_panic, mute, solo
│   ├── test_pattern_list.py      # fl_list_patterns + pattern protocol
│   └── test_v2_features.py       # Sprint 1+2: note names, disconnect, clear, pan, bridge reliability
├── .github/
│   └── workflows/
│       └── test.yml              # CI: Python 3.11 + 3.12
├── pyproject.toml
├── README.md
└── PROJECT_SUMMARY.md            # This file
```

---

## All 20 Tools

### Connection (3)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_list_midi_ports` | Lists all available MIDI input/output ports with platform recommendations | No |
| `fl_connect` | Opens MIDI output port. Accepts `port_name`, optional `input_port_name`, `dry_run` flag | No |
| `fl_disconnect` | Closes active MIDI output and input ports. Safe to call anytime. Resets all state | No |

### Transport (3)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_play_transport` | Send MMC Play (F0 7F 7F 06 02 F7) | No (MMC is native) |
| `fl_stop_transport` | Send MMC Stop (F0 7F 7F 06 01 F7) | No (MMC is native) |
| `fl_set_tempo` | Set BPM (20–999) via SysEx `F0 7D 03 BPM_HI BPM_LO F7` | Yes |

### Notes / Composition (2)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_insert_notes` | Insert 1–128 MIDI notes. `pitch` accepts int (60) or note name ("C4", "F#3", "Bb4") | Yes |
| `fl_add_chord_progression` | Insert 1–32 chord steps. `root_pitch` also accepts note names | Yes |

### Project (1)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_save_project_as` | Save the current project. Filename whitelist-validated | Yes |

### Status & Channels — Bidirectional (4)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_get_status` | Query FL Studio: returns playing, BPM, current pattern index, channel count | Yes |
| `fl_list_channels` | Query channel rack: returns list of channel names in order | Yes |
| `fl_set_channel_volume` | Set channel volume (0–127, 100 = unity gain) | Yes |
| `fl_set_channel_pan` | Set channel pan (0 = full left, 64 = centre, 127 = full right) | Yes |

### Patterns (4)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_create_pattern` | Create (jump to) the next empty pattern slot | Yes |
| `fl_select_pattern` | Jump to a pattern by index (0-based) | Yes |
| `fl_list_patterns` | Query FL Studio: returns list of all pattern names | Yes |
| `fl_clear_pattern` | ⚠️ Erase all notes from the currently selected pattern | Yes |

### Mixing (3)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_panic` | Send CC 120+121+123 on all 16 MIDI channels — kills stuck notes instantly | No (pure CC) |
| `fl_mute_channel` | Mute or unmute a channel rack slot | Yes |
| `fl_solo_channel` | Solo or un-solo a channel rack slot | Yes |

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
| save_as | `0x05` | ASCII filename bytes | v1.0 |
| query_status | `0x06` | — | v1.1 |
| query_channels | `0x07` | — | v1.1 |
| set_channel_vol | `0x08` | `[ch_idx, volume]` | v1.1 |
| new_pattern | `0x09` | — | v1.1 |
| select_pattern | `0x0A` | `[pat_idx]` | v1.1 |
| _(0x0B reserved)_ | | panic is pure MIDI CC | |
| query_patterns | `0x0C` | — | v1.2 |
| mute_channel | `0x0D` | `[ch_idx, is_muted]` | v1.2 |
| solo_channel | `0x0E` | `[ch_idx, is_soloed]` | v1.2 |
| clear_pattern | `0x0F` | — (destructive) | v1.3 |
| set_channel_pan | `0x13` | `[ch_idx, pan]` (0=L, 64=C, 127=R) | v1.3 |

### FL Studio → Server Responses

| Resp | Hex | Payload | Added |
|------|-----|---------|-------|
| status | `0x10` | `[playing, bpm_hi, bpm_lo, pat_idx, ch_count]` | v1.1 |
| channels | `0x11` | `[count, name_len, name_bytes... × count]` | v1.1 |
| patterns | `0x12` | `[count, name_len, name_bytes... × count]` | v1.2 |

> **Namespace note:** Command bytes 0x01–0x0E and 0x13 travel server→FL. Response bytes 0x10–0x12 travel FL→server. They never collide because they flow in opposite directions. Responses are reserved in the 0x10–0x1F range.

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

---

## FL Studio Controller Script — v1.3

**Install path (macOS):** `~/Documents/Image-Line/FL Studio/Settings/Hardware/fl_mcp_bridge/`  
**Install path (Windows):** `%USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Hardware\fl_mcp_bridge\`

**Lifecycle:**
- `OnInit()` — prints `[FL MCP Bridge v1.3] Initialized` to FL output log
- `OnSysEx(event)` — routes to dispatch dict, sets `event.handled = True`
- `_send_sysex(cmd, payload)` — calls `device.midiOutSysex()` for responses

**All implemented handlers:**
| Handler | FL API call | Notes |
|---------|-------------|-------|
| `_cmd_play()` | `transport.start()` | |
| `_cmd_stop()` | `transport.stop()` | |
| `_cmd_set_tempo()` | `transport.setTempo(bpm)` | Legacy fallback via `general.processMIDICC` |
| `_cmd_insert_notes()` | `patterns.addNote()` | Two signature fallbacks + realtime fallback |
| `_cmd_save_as()` | `ui.save()` | |
| `_cmd_query_status()` | `transport.isPlaying/getTempo`, `patterns.patternNumber`, `channels.channelCount` | Sends RESP_STATUS |
| `_cmd_query_channels()` | `channels.getChannelName(i)` | Sends RESP_CHANNELS |
| `_cmd_set_channel_vol()` | `channels.setChannelVolume(idx, vol/127.0)` | |
| `_cmd_new_pattern()` | `patterns.jumpToPattern(patternCount())` | |
| `_cmd_select_pattern()` | `patterns.jumpToPattern(idx)` | |
| `_cmd_query_patterns()` | `patterns.getPatternName(i)` | Sends RESP_PATTERNS |
| `_cmd_mute_channel()` | `channels.muteChannel(idx, bool)` | |
| `_cmd_solo_channel()` | `channels.soloChannel(idx)` | Toggle semantics in FL |
| `_cmd_clear_pattern()` | `patterns.clearCurrentPattern()` | Fallback: `patterns.clearPattern(idx)` |
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

**194 tests across 8 files — zero hardware required.**

| File | Tests | Coverage area |
|------|-------|---------------|
| `test_models.py` | 25 | Note/ChordStep validation, protocol encode/decode |
| `test_bridge.py` | 10 | Singleton lifecycle, dry-run, send, status |
| `test_tools.py` | 30 | Original 8 tools end-to-end |
| `test_bidirectional.py` | 30 | 5 bidirectional tools + response encoders |
| `test_mixing.py` | 29 | panic, mute, solo — protocol + tool |
| `test_pattern_list.py` | 14 | fl_list_patterns + pattern protocol |
| `test_v2_features.py` | 59 | Note name parsing, fl_disconnect, fl_clear_pattern, fl_set_channel_pan, queue overflow, asyncio lock |

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
fl_clear_pattern()
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
| _(current)_ | v2 Sprint 1+2: note name parsing, fl_disconnect, queue overflow logging, asyncio query lock, fl_clear_pattern, fl_set_channel_pan, bridge v1.3, 59 new tests |

---

## Remaining Backlog (Post v2)

Items are grouped by sprint theme. Priority order within each group.

---

### Sprint 3 — Bidirectional Read + Pattern Control

| # | Enhancement | Impact | Complexity | Protocol |
|---|-------------|--------|------------|---------|
| S3-1 | **`fl_get_notes`** — read all notes from current pattern; returns array of `{pitch, velocity, start, duration, channel}`. New `RESP_NOTES = 0x14`. Unlocks AI "read then edit" workflows. | Very High | High | New CMD `0x14` + `RESP 0x15` |
| S3-2 | **`fl_get_context`** — single call returns BPM, playing state, current pattern index, channel list, note count. Saves 3-4 round trips for AI orientation. | High | Low | Compose existing queries |
| S3-3 | **`fl_set_pattern_length`** — set pattern length in beats/bars. Critical for anything beyond default 1-bar patterns. | High | Medium | New CMD `0x15` |
| S3-4 | **`fl_rename_channel`** — rename a channel rack instrument. AI can label what it creates. | Medium | Medium | New CMD `0x16` |
| S3-5 | **`fl_rename_pattern`** — rename a pattern slot. Keeps sessions organized. | Medium | Medium | New CMD `0x17` |

---

### Sprint 4 — Mixer & Routing

| # | Enhancement | Impact | Complexity | Notes |
|---|-------------|--------|------------|-------|
| S4-1 | **`fl_set_mixer_volume`** — set volume on a mixer track (0–127). Mixer and channel rack are separate in FL; current tools only touch the channel rack. | High | Medium | `mixer` module |
| S4-2 | **`fl_set_mixer_pan`** — pan a mixer track left/right. | High | Low | Mirrors `fl_set_channel_pan` |
| S4-3 | **`fl_route_to_mixer`** — assign a channel rack instrument to a mixer track. Required for any real mixing session. | High | Medium | `channels.setTarget()` |
| S4-4 | **`fl_get_mixer_state`** — query all mixer track names, volumes, pans, and routings in one call. | Medium | High | New bidirectional query |
| S4-5 | **`fl_set_master_volume`** — global master volume control. | Medium | Low | `mixer.setMasterVolume()` |
| S4-6 | **`fl_set_master_pitch`** — global master pitch/transpose. | Low | Low | `mixer.setMasterPitch()` |

---

### Sprint 5 — Undo, Reliability & AI Quality-of-Life

| # | Enhancement | Impact | Complexity | Notes |
|---|-------------|--------|------------|-------|
| S5-1 | **`fl_undo` / `fl_redo`** — trigger FL Studio's undo/redo stack. Simple but essential for iterative AI composition. | High | Low | `general.undoUp()` / `general.undoDown()` |
| S5-2 | **Heartbeat / auto-reconnect** — `fl_get_status` ping before long operations; auto-reset state if FL closes/reopens. | High | Medium | Bridge-level change |
| S5-3 | **`fl_ping`** — lightweight 200ms round-trip test. Verifies bridge is alive without side effects. | Medium | Low | New CMD `0x18` |
| S5-4 | **Write-command ACK responses** — FL Studio sends back confirmation bytes after `fl_clear_pattern`, `fl_set_channel_pan`, etc. Tools can confirm execution rather than fire-and-forget. | Medium | Medium | Add `RESP_ACK = 0x1F` |
| S5-5 | **Connection staleness detection** — catch mido `OSError` on send, auto-reset bridge state and surface clean error. | Medium | Medium | Bridge error handling |
| S5-6 | **SysEx chunking** — auto-split payloads >512 bytes for IAC Driver / loopMIDI compatibility. Fixes silent drops on large note batches. | Medium | Medium | Protocol layer |

---

### Sprint 6 — Music Theory & Composition Helpers

| # | Enhancement | Impact | Complexity | Notes |
|---|-------------|--------|------------|-------|
| S6-1 | **`fl_insert_scale`** — insert a full scale as notes: `fl_insert_scale(root="C4", scale="minor", octaves=2, rhythm="eighth")`. Handles theory internally. | High | Medium | Model-level |
| S6-2 | **`fl_insert_arpeggio`** — generate arpeggiated chord patterns with configurable style (up, down, random, pingpong) and rate. | Medium | Medium | Builds on chord model |
| S6-3 | **`fl_insert_drum_pattern`** — structured drum input: `{kick: [1,0,0,0,1,0,0,0], snare: [0,0,1,0,...]}`. Maps to channel rack rows. | High | Medium | New model |
| S6-4 | **Velocity humanization** — `velocity_curve` option on `fl_insert_notes`: `"humanize"` (±15 random), `"crescendo"`, `"decrescendo"`. | Medium | Low | Model validator |
| S6-5 | **Swing quantization** — `swing` param (0.0–1.0) on note insertion; shifts even-numbered 16th notes. | Medium | Low | Tick calculation |
| S6-6 | **`fl_insert_bassline`** — generate a bassline from a chord progression root motion with configurable rhythm. | Medium | High | Composition layer |

---

### Sprint 7 — MCP Protocol Upgrades & Developer Experience

| # | Enhancement | Impact | Complexity | Notes |
|---|-------------|--------|------------|-------|
| S7-1 | **MCP Resources** — expose current pattern notes, channel list, BPM as MCP Resources (not tools). Claude reads them passively without tool calls. | High | Medium | FastMCP `@mcp.resource` |
| S7-2 | **MCP Prompt templates** — pre-built prompts: "write a 4-bar trap loop", "add a chord progression in C minor", "humanize this pattern". Chain correct tools automatically. | High | Low | FastMCP `@mcp.prompt` |
| S7-3 | **Structured tool outputs** — add `outputSchema` to all tools. Clients that support structured content get typed data instead of raw JSON strings. | Medium | Low | FastMCP output schema |
| S7-4 | **FL API type stubs** — `.pyi` files for `channels`, `patterns`, `transport`, `mixer` FL Studio modules. Enables IDE autocomplete in bridge script. | Low | High | Stub generation |
| S7-5 | **Windows transport testing** — loopMIDI validation on real Windows build; wire up `WindowsMIDITransport` fully. | Medium | Medium | Transport layer |
| S7-6 | **WebSocket transport** — optional alternative to IAC/loopMIDI. Run the bridge over a local WebSocket for remote FL Studio instances. | Low | High | New transport class |

---

## Known Limitations

- **`patterns.addNote()` API variability** — FL Studio's Python API signature differs across versions. Script tries two signatures, falls back to realtime note-on if both fail.
- **Solo is a toggle in FL Studio** — `channels.soloChannel(idx)` toggles state; `fl_solo_channel(soloed=False)` sends the same SysEx as `soloed=True`.
- **`fl_clear_pattern` is destructive** — no MCP-level undo. FL Studio's own Ctrl+Z still works manually after the call.
- **No SysEx size guard** — 128 notes × 9 bytes = 1,152-byte message. Some IAC Driver / loopMIDI configurations cap at 512 bytes and will silently drop it.
- **Windows transport is a stub** — tested interface only; requires loopMIDI validation.
- **`fl_get_pattern_notes` not yet implemented** — the flow is currently write-only; Claude cannot read back what notes are currently in a pattern.
