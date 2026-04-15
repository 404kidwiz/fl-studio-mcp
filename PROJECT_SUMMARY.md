# FL Studio MCP — Project Summary

**Version:** 0.1.0  
**Status:** Active development — v1 complete, v2 enhancements identified  
**Last updated:** 2026-04-15  
**Commits:** 3 (initial → bidirectional → production polish)  
**Tests:** 135 passing, 0 failing  
**Total source lines:** ~4,400

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
        │     ├── mido output port ──► IAC Driver ──► FL Studio
        │     └── mido input port  ◄── IAC Driver ◄── FL Studio
        │           │ callback thread → thread_queue.Queue
        │           └── bridge.query() polls queue w/ asyncio.sleep
        │
        ├── tools/ (17 tools, each in its own module)
        ├── protocol.py (SysEx encode/decode — shared with FL script)
        ├── models.py (Pydantic v2 schemas)
        └── errors.py (structured error types)

FL Studio
        └── fl_mcp_bridge/ (controller script v1.2)
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
│   ├── server.py                 # FastMCP server, registers all 17 tools
│   ├── bridge.py                 # Singleton MIDI I/O + response queue
│   ├── models.py                 # Pydantic schemas (Note, ChordStep, all inputs)
│   ├── errors.py                 # ErrorCode enum + FLMCPError
│   ├── protocol.py               # Full SysEx protocol encode/decode
│   ├── transports/
│   │   ├── base.py               # MIDITransport ABC
│   │   ├── macos.py              # IAC Driver via rtmidi (primary)
│   │   └── windows.py            # loopMIDI stub (same interface)
│   └── tools/
│       ├── midi_ports.py         # fl_list_midi_ports
│       ├── connection.py         # fl_connect
│       ├── transport_control.py  # fl_play_transport, fl_stop_transport
│       ├── tempo.py              # fl_set_tempo
│       ├── notes.py              # fl_insert_notes, fl_add_chord_progression
│       ├── project.py            # fl_save_project_as
│       ├── status.py             # fl_get_status (bidirectional)
│       ├── channels.py           # fl_list_channels (bidir), fl_set_channel_volume
│       ├── patterns.py           # fl_create_pattern, fl_select_pattern
│       ├── pattern_list.py       # fl_list_patterns (bidirectional)
│       └── mixing.py             # fl_panic, fl_mute_channel, fl_solo_channel
├── fl_studio_scripts/
│   └── fl_mcp_bridge/
│       └── device_fl_mcp_bridge.py  # FL Studio controller script v1.2
├── tests/
│   ├── conftest.py               # reset_bridge + dry_bridge fixtures
│   ├── test_models.py            # Note model, chord helpers, protocol
│   ├── test_bridge.py            # Bridge singleton, dry-run, send
│   ├── test_tools.py             # All original 8 tools
│   ├── test_bidirectional.py     # 5 bidirectional tools + protocol
│   ├── test_mixing.py            # fl_panic, mute, solo
│   └── test_pattern_list.py      # fl_list_patterns + pattern protocol
├── .github/
│   └── workflows/
│       └── test.yml              # CI: Python 3.11 + 3.12
├── pyproject.toml
└── README.md
```

---

## All 17 Tools

### Connection (2)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_list_midi_ports` | Lists all available MIDI input/output ports with platform recommendations | No |
| `fl_connect` | Opens the MIDI output port. Accepts `port_name`, optional `input_port_name`, `dry_run` flag | No |

### Transport (3)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_play_transport` | Send MMC Play (F0 7F 7F 06 02 F7) | No (MMC is native) |
| `fl_stop_transport` | Send MMC Stop (F0 7F 7F 06 01 F7) | No (MMC is native) |
| `fl_set_tempo` | Set BPM (20–999) via SysEx `F0 7D 03 BPM_HI BPM_LO F7` | Yes |

### Notes / Composition (2)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_insert_notes` | Insert 1–128 MIDI notes into the current pattern. Each note: pitch, velocity, start_tick, duration_ticks, channel | Yes |
| `fl_add_chord_progression` | Insert 1–32 chord steps. Each step: root_pitch, quality (major/minor/dom7/maj7/min7/dim/aug/sus2/sus4), velocity, start_tick, duration_ticks | Yes |

### Project (1)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_save_project_as` | Save the current project. Filename is whitelist-validated (alphanumeric/spaces/dashes/dots) | Yes |

### Status & Channels — Bidirectional (3)
| Tool | Description | Needs Bridge Script |
|------|-------------|---------------------|
| `fl_get_status` | Query FL Studio: returns playing, BPM, current pattern index, channel count | Yes |
| `fl_list_channels` | Query channel rack: returns list of channel names in order | Yes |
| `fl_set_channel_volume` | Set channel volume (0–127, 100 = unity gain) | Yes |

### Patterns (3)
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

### FL Studio → Server Responses

| Resp | Hex | Payload | Added |
|------|-----|---------|-------|
| status | `0x10` | `[playing, bpm_hi, bpm_lo, pat_idx, ch_count]` | v1.1 |
| channels | `0x11` | `[count, name_len, name_bytes... × count]` | v1.1 |
| patterns | `0x12` | `[count, name_len, name_bytes... × count]` | v1.2 |

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
`FLStudioBridge._instance` is held for the lifetime of the server process. MIDI ports are expensive to open/close repeatedly, and MCP tools are stateless by nature — the singleton gives them shared connection state.

### Bidirectional Threading Model
mido runs its input callback in a background thread. The bridge uses `thread_queue.Queue(maxsize=64)` for thread-safe handoff. `bridge.query()` is async and polls the queue with `asyncio.sleep(0.05)` intervals until the expected response cmd arrives or the deadline passes.

### Dry-Run Mode
Activated via `fl_connect(dry_run=True)` or `FL_MCP_DRY_RUN=1` env var. `send_raw()` and `query()` both short-circuit — `send_raw` returns `{dry_run: True, would_send_bytes: "..."}`, `query` returns `None` (tools substitute canned preview data). No MIDI hardware needed for development or testing.

### Platform Abstraction
`MIDITransport` ABC in `transports/base.py` — tool code never imports platform specifics. `get_transport()` in `transports/__init__.py` returns `MacOSMIDITransport` on Darwin, `WindowsMIDITransport` on Win32. Windows stub has the same interface; swap the implementation when ready.

### Whitelist-Only FL Studio Access
The FL Studio script only handles explicitly enumerated command bytes via a dispatch dict. Unknown `cmd` bytes are logged and ignored. No `eval()`, no shell access, no arbitrary Python execution inside FL Studio.

### Structured Errors
Every tool returns JSON. Errors are `{"error": "ERROR_CODE", "message": "...", "details": {...}}` — never Python tracebacks in the MCP response.

---

## FL Studio Controller Script — v1.2

**Install path (macOS):** `~/Documents/Image-Line/FL Studio/Settings/Hardware/fl_mcp_bridge/`  
**Install path (Windows):** `%USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Hardware\fl_mcp_bridge\`

**Lifecycle:**
- `OnInit()` — prints `[FL MCP Bridge v1.2] Initialized` to FL output log
- `OnSysEx(event)` — routes to dispatch dict, sets `event.handled = True`
- `_send_sysex(cmd, payload)` — calls `device.midiOutSysex()` for responses

**Implemented handlers:**
- `_cmd_play()`, `_cmd_stop()` — `transport.start/stop()`
- `_cmd_set_tempo()` — `transport.setTempo(bpm)` with legacy fallback via `general.processMIDICC`
- `_cmd_insert_notes()` — tries `patterns.addNote()` (two signatures), falls back to `channels.midiNoteOn()`
- `_cmd_save_as()` — `ui.save()`
- `_cmd_query_status()` — reads `transport.isPlaying/getTempo`, `patterns.patternNumber`, `channels.channelCount`, sends `RESP_STATUS`
- `_cmd_query_channels()` — reads `channels.getChannelName(i)` for each slot, sends `RESP_CHANNELS`
- `_cmd_set_channel_vol()` — `channels.setChannelVolume(idx, vol/127.0)`
- `_cmd_new_pattern()` — `patterns.jumpToPattern(patternCount())`
- `_cmd_select_pattern()` — `patterns.jumpToPattern(idx)`
- `_cmd_query_patterns()` — reads `patterns.getPatternName(i)` for each slot, sends `RESP_PATTERNS`
- `_cmd_mute_channel()` — `channels.muteChannel(idx, bool)`
- `_cmd_solo_channel()` — `channels.soloChannel(idx)` (FL Studio solo is a toggle)

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `mcp` | ≥1.9.0 | FastMCP server framework, stdio transport |
| `mido` | ≥1.3.3 | MIDI I/O, SysEx encoding, callback-based input |
| `python-rtmidi` | ≥1.5.8 | mido backend for real hardware MIDI ports |
| `pydantic` | ≥2.7.0 | Input validation, Note/ChordStep schemas |

**Dev only:** `pytest ≥9.0.3`, `pytest-asyncio ≥1.3.0`

**Python:** ≥3.11 (uses `X | Y` union syntax, `match`, `dict[str, Any]` generics)

**Build:** Hatchling, `uv` for environment management

---

## Testing

**135 tests across 7 files — zero hardware required.**

All tests run against a `dry_bridge` fixture (pre-connected, dry-run mode). Bidirectional tests use direct queue injection to simulate FL Studio responses without a real MIDI loop.

| File | Tests | Coverage area |
|------|-------|---------------|
| `test_models.py` | 25 | Note/ChordStep validation, protocol encode/decode |
| `test_bridge.py` | 10 | Singleton lifecycle, dry-run, send, status |
| `test_tools.py` | 30 | Original 8 tools end-to-end |
| `test_bidirectional.py` | 30 | 5 bidirectional tools + response encoders |
| `test_mixing.py` | 29 | panic, mute, solo — protocol + tool |
| `test_pattern_list.py` | 14 | fl_list_patterns + pattern protocol |
| `conftest.py` | — | `reset_bridge` (autouse), `dry_bridge` fixtures |

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

## Typical Claude Workflow

```
1. fl_list_midi_ports               → see available IAC ports
2. fl_connect(port_name="IAC")      → open output + start input listener
3. fl_get_status()                  → verify: BPM, playing state, pattern
4. fl_set_tempo(bpm=128)
5. fl_add_chord_progression(...)    → I-V-vi-IV
6. fl_list_channels()               → see "Kick", "Snare", etc.
7. fl_mute_channel(channel_index=2) → mute hi-hat
8. fl_play_transport()
9. fl_panic()                       → if notes get stuck
10. fl_save_project_as(filename="MyTrack")
```

---

## Identified Enhancements (v2 Backlog)

Priority-ordered improvements identified post-v1:

| # | Enhancement | Impact | Complexity |
|---|-------------|--------|------------|
| 1 | **Note name parsing** (`"C4"` → 60) — `field_validator` on `Note.pitch` | High | Low |
| 2 | **`fl_clear_pattern`** — erase current pattern before inserting | High | Low |
| 3 | **Concurrent query safety** — `asyncio.Lock` or per-cmd `asyncio.Event` dict | High | Medium |
| 4 | **`fl_set_channel_pan`** — companion to `fl_set_channel_volume` | Medium | Low |
| 5 | **SysEx chunking** — auto-split payloads >512 bytes for driver compatibility | Medium | Medium |
| 6 | **`fl_disconnect`** — clean port teardown via MCP tool | Medium | Low |
| 7 | **Scale/mode helper** — `fl_insert_scale(root, scale, octaves, rhythm)` | Medium | Medium |
| 8 | **Velocity humanization** — `velocity_curve` option on note sequences | Low | Low |
| 9 | **FL API type stubs** — `.pyi` files for `channels`, `patterns`, `transport` | Low | High |
| 10 | **`fl_ping`** — 200ms heartbeat check before long operations | Low | Low |
| Arch | **Connection staleness detection** — catch mido `OSError`, reset state | Medium | Medium |
| Arch | **Queue overflow logging** — `pass` on Full → `print` to stderr | Low | Trivial |

---

## Known Limitations

- **`patterns.addNote()` API variability** — FL Studio's Python API signature differs across versions. The script tries two signatures and falls back to realtime note-on. Pattern-level insertion is not guaranteed on all FL builds.
- **Solo is a toggle in FL Studio** — `channels.soloChannel(idx)` toggles; the `soloed=False` parameter has no distinct effect. The MCP tool sends the same SysEx either way, matching FL's behavior.
- **No concurrent query protection** — two simultaneous bidirectional tools can steal each other's queue responses. Not an issue in single-threaded Claude tool calls but a real concern if used in parallel agents.
- **No SysEx size guard** — 128 notes × 9 bytes = 1,152-byte message. Some MIDI drivers cap at 512 bytes and will silently drop it.
- **Windows transport is a stub** — `WindowsMIDITransport` has the correct interface but calls `mido.get_output_names()` directly (same as macOS). Needs loopMIDI testing.

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

| Commit | Message | What shipped |
|--------|---------|--------------|
| `fb0ca1a` | `feat: initial FL Studio MCP server` | 8 tools, bridge, transports, protocol, models, errors, tests |
| `6a6aeea` | `feat: bidirectional MIDI + 5 new tools` | fl_get_status, fl_list_channels, fl_set_channel_volume, fl_create_pattern, fl_select_pattern, input listener, response queue, conftest |
| `944881f` | `feat: production polish — 17 tools, panic, mute/solo, pattern list, CI` | fl_panic, fl_mute_channel, fl_solo_channel, fl_list_patterns, bridge v1.2, GitHub Actions, README rewrite |
