# FL Studio MCP Workflows

Step-by-step tutorials for common production workflows using the FL Studio MCP tool suite.

---

## Table of Contents

1. [Complete Song Production Workflow](#1-complete-song-production-workflow)
2. [Marker Management](#2-marker-management)
3. [Tempo Automation](#3-tempo-automation)
4. [Project Management](#4-project-management)
5. [Pattern Operations](#5-pattern-operations)

---

## 1. Complete Song Production Workflow

**Goal**: Connect to FL Studio, create a pattern, add notes, add arrangement markers, set tempo, save, and export audio.

### Step 1: Connect and Verify

```json
// MCP Call
fl_connect(port_name="IAC Driver Bus 1")

// Response
{
  "connected": true,
  "port": "IAC Driver Bus 1",
  "dry_run": false,
  "platform_transport": "MacOSMIDITransport",
  "listening": true,
  "input_port": "IAC Driver Bus 1"
}
```

```bash
# CLI Equivalent
uv run fl-studio connect --port "IAC Driver Bus 1"
```

### Step 2: Check Current Status

```json
// MCP Call
fl_get_status(timeout_ms=2000)

// Response
{
  "playing": false,
  "bpm": 120,
  "pattern_index": 0,
  "channel_count": 5,
  "listening": true,
  "source": "fl_studio"
}
```

```bash
# CLI Equivalent
uv run fl-studio status
```

### Step 3: Create a New Pattern

```json
// MCP Call
fl_create_pattern()

// Response
{
  "sent": true,
  "command": "NEW_PATTERN",
  "bytes": "F0 7D 09 F7"
}
```

```bash
# CLI Equivalent
uv run fl-studio patterns create
```

### Step 4: Add MIDI Notes

```json
// MCP Call
fl_insert_notes(notes=[
  {pitch: "C4", velocity: 100, start_tick: 0, duration_ticks: 96},
  {pitch: "E4", velocity: 90, start_tick: 96, duration_ticks: 96},
  {pitch: "G4", velocity: 100, start_tick: 192, duration_ticks: 192}
])

// Response
{
  "sent": true,
  "note_count": 3,
  "notes_preview": [...],
  "chunks_sent": 1,
  "bytes": "F0 7D 04 ... F7"
}
```

```bash
# CLI Equivalent
uv run fl-studio notes insert --pitch C4 --velocity 100 --start 0 --duration 96
```

### Step 5: Add a Marker

```json
// MCP Call
fl_set_song_marker(marker_name="Intro", color_r=0, color_g=255, color_b=0)

// Response
{
  "sent": true,
  "marker_name": "Intro",
  "color": [0, 255, 0],
  "command": "ADD_MARKER",
  "bytes": "F0 7D 23 ... F7"
}
```

```bash
# CLI Equivalent
uv run fl-studio set-song-marker --marker-name "Intro" --color-r 0 --color-g 255 --color-b 0
```

### Step 6: Set Song Tempo

```json
// MCP Call
fl_set_song_bpm(bpm=128, confirm=true)

// Response
{
  "sent": true,
  "bpm": 128,
  "command": "SET_TEMPO",
  "bytes": "F0 7D 03 01 00 F7"
}
```

```bash
# CLI Equivalent
uv run fl-studio set-song-bpm --bpm 128 --confirm
```

### Step 7: Save the Project

```json
// MCP Call
fl_save_project(confirm=true)

// Response
{
  "sent": true,
  "command": "SAVE",
  "bytes": "F0 7D 05 F7"
}
```

```bash
# CLI Equivalent (Ctrl+S)
uv run fl-studio save
```

### Step 8: Export Audio

```json
// MCP Call
fl_export_audio(output_path="/Users/me/Desktop/track.wav", format="wav", quality=90, confirm=true)

// Response
{
  "output_path": "/Users/me/Desktop/track.wav",
  "format": "wav",
  "quality": 90,
  "command": "EXPORT_AUDIO",
  "status": "completed",
  "source": "fl_studio"
}
```

```bash
# CLI Equivalent
uv run fl-studio export-audio --output-path ~/Desktop/track.wav --format wav --quality 90 --confirm
```

---

## 2. Marker Management

**Goal**: Add, query, insert at specific positions, and delete markers in the playlist.

### Add a Marker at Current Position

```json
// MCP Call — adds a marker where the playhead is right now
fl_set_song_marker(marker_name="Drop", color_r=255, color_g=50, color_b=50)

// Response (dry-run)
{
  "dry_run": true,
  "marker_name": "Drop",
  "color": [255, 50, 50],
  "command": "ADD_MARKER",
  "bytes": "F0 7D 04 04 44 72 6F 70 ... F7",
  "source": "dry_run_preview"
}
```

### Insert a Marker at a Specific Beat Position

```json
// MCP Call — place marker at beat 16 (bar 4 in 4/4)
fl_insert_marker(position_beats=16.0, marker_name="Verse 1", color_r=0, color_g=200, color_b=255)

// Response
{
  "position_beats": 16.0,
  "marker_name": "Verse 1",
  "color": [0, 200, 255],
  "command": "INSERT_MARKER",
  "source": "fl_studio"
}
```

```bash
# CLI Equivalent
uv run fl-studio insert-marker --position-beats 16 --marker-name "Verse 1" --color-r 0 --color-g 200 --color-b 255
```

### Query a Marker

```json
// MCP Call
fl_get_marker(marker_index=0)

// Response
{
  "marker_index": 0,
  "name": "Marker 1",
  "position_seconds": 0.0,
  "color": [255, 255, 255],
  "source": "fl_studio"
}
```

```bash
# CLI Equivalent
uv run fl-studio get-marker --marker-index 0
```

### Delete a Marker

```json
// MCP Call
fl_delete_marker(marker_index=0)

// Response
{
  "sent": true,
  "marker_index": 0,
  "command": "DELETE_MARKER",
  "bytes": "F0 7D 00 F7"
}
```

```bash
# CLI Equivalent
uv run fl-studio delete-marker --marker-index 0
```

### Full Marker Workflow

```json
// 1. Add markers for song structure
fl_set_song_marker(marker_name="Intro", color_r=0, color_g=200, color_b=255)
fl_insert_marker(position_beats=8.0, marker_name="Verse", color_r=0, color_g=255, color_b=0)
fl_insert_marker(position_beats=24.0, marker_name="Chorus", color_r=255, color_g=200, color_b=0)
fl_insert_marker(position_beats=40.0, marker_name="Bridge", color_r=128, color_g=0, color_b=255)
fl_insert_marker(position_beats=56.0, marker_name="Outro", color_r=255, color_g=100, color_b=100)

// 2. List all markers by querying each
fl_get_marker(marker_index=0)  // Intro
fl_get_marker(marker_index=1)  // Verse

// 3. Remove the Bridge marker
fl_delete_marker(marker_index=3)

// 4. Get song info to see marker count
fl_get_song_info()
```

---

## 3. Tempo Automation

**Goal**: Query current tempo, set absolute BPM, apply relative tempo changes.

### Get Current Tempo

```json
// MCP Call
fl_get_song_tempo(timeout_ms=2000)

// Response
{
  "bpm": 120,
  "source": "fl_studio"
}
```

```bash
# CLI Equivalent
uv run fl-studio get-song-tempo
```

### Get BPM as Float

```json
// MCP Call
fl_get_song_bpm()

// Response
{
  "bpm": 120.0,
  "source": "fl_studio"
}
```

```bash
# CLI Equivalent
uv run fl-studio get-song-bpm
```

### Set Absolute BPM

```json
// MCP Call — set specific tempo (requires confirm=true)
fl_set_song_bpm(bpm=140, confirm=true)

// Response
{
  "sent": true,
  "bpm": 140,
  "command": "SET_TEMPO",
  "bytes": "F0 7D 03 01 0C F7"
}
```

```bash
# CLI Equivalent
uv run fl-studio set-song-bpm --bpm 140 --confirm
```

### Relative Tempo Change

```json
// MCP Call — speed up by 25% (120 → 150 BPM)
fl_set_song_tempo_relative(percentage=25, confirm=true)

// Response
{
  "sent": true,
  "current_bpm": 120,
  "new_bpm": 150,
  "percentage": 25,
  "command": "SET_TEMPO_RELATIVE",
  "bytes": "F0 7D 03 01 0E F7"
}
```

```bash
# CLI Equivalent
uv run fl-studio set-song-tempo-relative --percentage 25 --confirm
```

### Safety Note

All tempo-changing tools require `confirm=true` to prevent accidental changes. If omitted:

```json
// Without confirm flag
fl_set_song_bpm(bpm=140)

// Response
{
  "error": "INVALID_PARAMS",
  "message": "Tempo changes require confirmation. Set confirm=true to proceed.",
  "hint": "This prevents accidental tempo changes. Always use confirm=true when changing tempo."
}
```

---

## 4. Project Management

**Goal**: Save the current project with a new filename, export audio with quality settings.

### Save Project (Ctrl+S Equivalent)

```json
// MCP Call — saves to current filename
fl_save_project(confirm=true)

// Response
{
  "sent": true,
  "command": "SAVE",
  "bytes": "F0 7D 05 F7"
}
```

```bash
# CLI Equivalent
uv run fl-studio save
```

### Save As New Filename

```json
// MCP Call — save with a new filename
fl_save_as_project(filename="My Finished Track.flp", confirm=true)

// Response
{
  "sent": true,
  "filename": "My Finished Track.flp",
  "command": "SAVE_AS",
  "bytes": "F0 7D 31 14 ... F7"
}
```

```bash
# CLI Equivalent
uv run fl-studio save-as-project --filename "My Finished Track.flp" --confirm
```

### Export Audio

```json
// MCP Call — export as high-quality WAV
fl_export_audio(output_path="/Users/me/Desktop/final_mix.wav", format="wav", quality=95, confirm=true)

// Response
{
  "output_path": "/Users/me/Desktop/final_mix.wav",
  "format": "wav",
  "quality": 95,
  "command": "EXPORT_AUDIO",
  "status": "completed",
  "source": "fl_studio"
}
```

```bash
# CLI Equivalent
uv run fl-studio export-audio --output-path ~/Desktop/final_mix.wav --format wav --quality 95 --confirm
```

### Export as MP3

```json
fl_export_audio(output_path="/Users/me/Desktop/preview.mp3", format="mp3", quality=80, confirm=true)
```

### Export as FLAC

```json
fl_export_audio(output_path="/Users/me/Desktop/archive.flac", format="flac", quality=100, confirm=true)
```

### Get Song Info

```json
// MCP Call — comprehensive project metadata
fl_get_song_info()

// Response
{
  "title": "Untitled Song",
  "author": "Unknown Artist",
  "length_seconds": 180.0,
  "bpm": 120,
  "key": "C major",
  "time_signature": "4/4",
  "genre": "Unknown",
  "comment": "",
  "copyright": "",
  "engineer": "",
  "producer": "",
  "mixer": "",
  "playlist_count": 10,
  "marker_count": 5,
  "source": "fl_studio"
}
```

```bash
# CLI Equivalent
uv run fl-studio get-song-info
```

---

## 5. Pattern Operations

**Goal**: Get/set the current pattern, duplicate, copy, cut, paste, and clear patterns.

### Get Current Pattern Index

```json
// MCP Call
fl_get_current_pattern(timeout_ms=2000)

// Response
{
  "pattern_index": 2,
  "source": "fl_studio"
}
```

```bash
# CLI Equivalent
uv run fl-studio get-current-pattern
```

### Set Current Pattern

```json
// MCP Call — switch to pattern 5
fl_set_current_pattern(pattern_index=5, confirm=true)

// Response
{
  "sent": true,
  "pattern_index": 5,
  "command": "SELECT_PATTERN",
  "bytes": "F0 7D 0A 05 F7"
}
```

```bash
# CLI Equivalent
uv run fl-studio set-current-pattern --pattern-index 5 --confirm
```

### List All Patterns

```json
// MCP Call
fl_list_patterns(timeout_ms=2000)

// Response
{
  "patterns": ["Pattern 1", "Verse", "Chorus", "Bridge", "Outro"],
  "count": 5,
  "source": "fl_studio"
}
```

```bash
# CLI Equivalent
uv run fl-studio patterns list
```

### Duplicate Pattern

```json
// MCP Call — creates a copy at the next empty slot
fl_duplicate_pattern()

// Response
{
  "sent": true,
  "command": "DUPLICATE_PATTERN",
  "bytes": "F0 7D 09 F7"
}
```

```bash
# CLI Equivalent
uv run fl-studio duplicate-pattern
```

### Copy Pattern to Specific Slot

```json
// MCP Call — copy current pattern to slot 8
fl_copy_pattern(target_pattern_index=8, confirm=true)

// Response
{
  "target_pattern_index": 8,
  "command": "COPY_PATTERN",
  "status": "completed",
  "source": "fl_studio"
}
```

```bash
# CLI Equivalent
uv run fl-studio copy-pattern --target-pattern-index 8
```

### Cut Pattern to Clipboard

```json
// MCP Call — remove current pattern and store in clipboard
fl_cut_pattern()

// Response
{
  "command": "CUT_PATTERN",
  "status": "completed",
  "source": "fl_studio"
}
```

```bash
# CLI Equivalent
uv run fl-studio cut-pattern
```

### Paste Pattern from Clipboard

```json
// MCP Call — paste clipboard into slot 3
fl_paste_pattern(target_pattern_index=3, confirm=true)

// Response
{
  "target_pattern_index": 3,
  "command": "PASTE_PATTERN",
  "status": "completed",
  "source": "fl_studio"
}
```

```bash
# CLI Equivalent
uv run fl-studio paste-pattern --target-pattern-index 3
```

### Clear Current Pattern

```json
// MCP Call — delete all notes in current pattern
fl_clear_pattern()

// Response
{
  "command": "CLEAR_PATTERN",
  "status": "completed",
  "source": "fl_studio"
}
```

```bash
# CLI Equivalent
uv run fl-studio clear-pattern
```

### Pattern Production Workflow

```json
// 1. Quick-check which pattern you're on
fl_get_current_pattern(timeout_ms=2000)

// 2. Navigate to the Chorus pattern
fl_set_current_pattern(pattern_index=2, confirm=true)

// 3. Duplicate it for a variation
fl_duplicate_pattern()

// 4. The duplicate is now active — clear it
fl_clear_pattern()

// 5. Switch back to the original
fl_set_current_pattern(pattern_index=2, confirm=true)

// 6. Copy it to a backup slot
fl_copy_pattern(target_pattern_index=10, confirm=true)

// 7. Verify the new slot
fl_get_current_pattern(timeout_ms=2000)
```

---

## Workflow: Get Counts

Quick diagnostic to understand project scale:

```json
// MCP Calls
fl_get_channel_count(timeout_ms=2000)
// → {"channel_count": 12, "source": "fl_studio"}

fl_get_mixer_track_count(timeout_ms=2000)
// → {"track_count": 8, "source": "fl_studio"}

fl_get_pattern_count(timeout_ms=2000)
// → {"pattern_count": 8, "source": "fl_studio"}

fl_get_song_length()
// → {"duration_seconds": 180.0, "source": "fl_studio"}
```

```bash
# CLI Equivalents
uv run fl-studio get-channel-count
uv run fl-studio get-mixer-track-count
uv run fl-studio get-pattern-count
uv run fl-studio get-song-length
```
