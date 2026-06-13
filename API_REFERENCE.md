# FL Studio MCP — Complete API Reference

**166 tools** organized by category. Each entry lists the tool name, source module, description, and key parameters.

---

## Contents

1. [Connection & Diagnostics (4)](#1-connection--diagnostics)
2. [Transport, Tempo & Project (10)](#2-transport-tempo--project)
3. [Realtime Notes & Input (2)](#3-realtime-notes--input)
4. [Status, Channels & Mixer (18)](#4-status-channels--mixer)
5. [Patterns & Pattern Control (9)](#5-patterns--pattern-control)
6. [Song/Project Management (22)](#6-songproject-management)
7. [GUI Automation & UI (6)](#7-gui-automation--ui)
8. [VST, Plugins & Library (11)](#8-vst-plugins--library)
9. [Algorithmic Composition (3)](#9-algorithmic-composition)
10. [Music Theory & Patterns (4)](#10-music-theory--patterns)
11. [DSP, Stems & Vision (8)](#11-dsp-stems--vision)
12. [Mix Engineering (3)](#12-mix-engineering)
13. [Arrangement & Song Structure (11)](#13-arrangement--song-structure)
14. [Vocal Processing & Audio (4)](#14-vocal-processing--audio)
15. [Performance & Live (10)](#15-performance--live)
16. [Genre & Sound Design (10)](#16-genre--sound-design)
17. [Arrangement Builders (10)](#17-arrangement-builders)
18. [Post-Production (10)](#18-post-production)
19. [Advanced MIDI & Audio (10)](#19-advanced-midi--audio)

---

## 1. Connection & Diagnostics (4 tools)

### fl_list_midi_ports
- **Module**: midi_ports
- **Description**: List all available MIDI input and output ports. No connection required.
- **Parameters**: None
- **CLI**: `uv run fl-studio ports`

### fl_connect
- **Module**: connection
- **Description**: Open a MIDI output port and optional input port for FL Studio communication. Most tools require this first.
- **Parameters**: `port_name` (str, required), `input_port_name` (str, optional), `dry_run` (bool, default false)
- **CLI**: `uv run fl-studio connect --port "IAC Driver Bus 1"`

### fl_disconnect
- **Module**: connection
- **Description**: Close active MIDI ports and reset bridge state.
- **Parameters**: None
- **CLI**: `uv run fl-studio disconnect`

### fl_ping
- **Module**: connection
- **Description**: Send a lightweight ping to verify connection and script responsiveness. Measures round-trip latency.
- **Parameters**: `challenge` (int 0-127, default 42), `timeout_ms` (int 100-10000, default 1000)
- **CLI**: `uv run fl-studio ping --challenge 42`

---

## 2. Transport, Tempo & Project (10 tools)

### fl_play_transport
- **Module**: transport_control
- **Description**: Start playback via MMC — equivalent to pressing Play.
- **Parameters**: `ack` (bool, default false), `timeout_ms` (int 50-10000, default 200)
- **CLI**: `uv run fl-studio play`

### fl_stop_transport
- **Module**: transport_control
- **Description**: Stop playback via MMC — equivalent to pressing Stop.
- **Parameters**: `ack` (bool, default false), `timeout_ms` (int 50-10000, default 200)
- **CLI**: `uv run fl-studio stop`

### fl_set_tempo
- **Module**: tempo
- **Description**: Set the project tempo (BPM 20-999) via custom SysEx.
- **Parameters**: `bpm` (int 20-999, required), `ack` (bool, default false), `timeout_ms` (int 50-10000, default 200)

### fl_set_time_selection
- **Module**: transport_control
- **Description**: Set the loop/time selection bar range in the arrangement.
- **Parameters**: `start_bar` (int 0-999, required), `end_bar` (int 0-999, required)

### fl_save_project
- **Module**: project
- **Description**: Save the current project (Ctrl+S equivalent). Requires `confirm=true`.
- **Parameters**: `confirm` (bool, required), `ack` (bool, default false), `timeout_ms` (int 50-10000, default 200)
- **CLI**: `uv run fl-studio save`

### fl_undo
- **Module**: project
- **Description**: Step backward in FL Studio's history stack (Ctrl+Z equivalent).
- **Parameters**: `ack` (bool, default false), `timeout_ms` (int 50-10000, default 200)
- **CLI**: `uv run fl-studio undo`

### fl_redo
- **Module**: project
- **Description**: Step forward in FL Studio's history stack (Ctrl+Y equivalent).
- **Parameters**: `ack` (bool, default false), `timeout_ms` (int 50-10000, default 200)
- **CLI**: `uv run fl-studio redo`

### fl_render_project
- **Module**: project
- **Description**: Render a .flp project to audio using headless FL Studio CLI mode. Falls back to synthesized WAV if CLI unavailable.
- **Parameters**: `project_path` (str, required), `output_path` (str, required), `format` (str: wav/mp3/ogg/flac/mid, default "wav"), `bitrate` (int, optional)

### fl_mute_playlist_track
- **Module**: project
- **Description**: Mute or unmute a specific track in the Playlist arrangement.
- **Parameters**: `track_index` (int 0-127, required), `muted` (bool, required)

### fl_solo_playlist_track
- **Module**: project
- **Description**: Solo or unsolo a specific track in the Playlist arrangement.
- **Parameters**: `track_index` (int 0-127, required), `soloed` (bool, required)

---

## 3. Realtime Notes & Input (2 tools)

### fl_insert_notes
- **Module**: notes
- **Description**: Play 1-128 MIDI notes in realtime. To record into a pattern, enable Record mode first. Chunked into batches of 32.
- **Parameters**: `notes` (list[Note], 1-128), `velocity_curve` (str: none/humanize/crescendo/decrescendo), `swing` (float 0.0-1.0), `ack` (bool), `timeout_ms` (int)
- **CLI**: `uv run fl-studio notes insert --pitch C4 --velocity 100`

### fl_add_chord_progression
- **Module**: notes
- **Description**: Insert 1-32 chord steps. Expands each ChordStep into individual notes using interval tables.
- **Parameters**: `chords` (list[ChordStep], 1-32), `ack` (bool), `timeout_ms` (int)
- **CLI**: `uv run fl-studio chord C4 major`

---

## 4. Status, Channels & Mixer (18 tools)

### fl_get_status
- **Module**: status
- **Description**: Bidirectional — query FL Studio's current playback state, BPM, pattern index, and channel count.
- **Parameters**: `timeout_ms` (int 100-10000, default 2000)
- **CLI**: `uv run fl-studio status`

### fl_health_check
- **Module**: status
- **Description**: Run a full system diagnostic — OS info, Python version, MIDI ports, connection status.
- **Parameters**: None

### fl_list_channels
- **Module**: channels
- **Description**: Bidirectional — list all channel rack instrument names and indices.
- **Parameters**: `timeout_ms` (int 100-10000, default 2000)
- **CLI**: `uv run fl-studio channels list`

### fl_set_channel_volume
- **Module**: channels
- **Description**: Set volume of a channel rack slot (0-127, 100 = unity gain).
- **Parameters**: `channel_index` (int 0-127), `volume` (int 0-127, default 100)
- **CLI**: `uv run fl-studio channels volume 0 100`

### fl_set_channel_pan
- **Module**: channels
- **Description**: Set panning of a channel rack slot (0=left, 64=centre, 127=right).
- **Parameters**: `channel_index` (int 0-127), `pan` (int 0-127, default 64)
- **CLI**: `uv run fl-studio channels pan 0 64`

### fl_set_channel_name
- **Module**: channels
- **Description**: Rename a channel in the channel rack.
- **Parameters**: `channel_index` (int), `name` (str)
- **CLI**: `uv run fl-studio channels rename 0 "Kick"`

### fl_set_channel_color
- **Module**: channels
- **Description**: Set the display color of a channel rack slot.
- **Parameters**: `channel_index` (int 0-127), `r` (int 0-255), `g` (int 0-255), `b` (int 0-255)

### fl_set_channel_mixer_track
- **Module**: channels
- **Description**: Route a channel rack channel to a specific mixer insert track.
- **Parameters**: `channel_index` (int), `track_index` (int, 0=Master)

### fl_set_step_sequence
- **Module**: channels
- **Description**: Set a single step on/off in the classic step sequencer grid.
- **Parameters**: `channel_index` (int 0-127), `step_index` (int 0-127), `value` (int 0 or 1)

### fl_panic
- **Module**: mixing
- **Description**: Send MIDI All Notes Off + All Sound Off on all 16 channels. Kills stuck notes.
- **Parameters**: None
- **CLI**: `uv run fl-studio panic`

### fl_mute_channel
- **Module**: mixing
- **Description**: Mute or unmute a channel rack slot.
- **Parameters**: `channel_index` (int 0-127), `muted` (bool, default true)
- **CLI**: `uv run fl-studio channels mute 1`

### fl_solo_channel
- **Module**: mixing
- **Description**: Solo or un-solo a channel rack slot.
- **Parameters**: `channel_index` (int 0-127), `soloed` (bool, default true)
- **CLI**: `uv run fl-studio channels solo 1`

### fl_set_mixer_volume
- **Module**: mixing
- **Description**: Set volume of a mixer track (0-127, 100 = unity gain).
- **Parameters**: `track_index` (int 0-127, default 0), `volume` (int 0-127, default 100)
- **CLI**: `uv run fl-studio mixer volume 1 90`

### fl_set_mixer_pan
- **Module**: mixing
- **Description**: Set panning of a mixer track (0=left, 64=centre, 127=right).
- **Parameters**: `track_index` (int 0-127), `pan` (int 0-127, default 64)
- **CLI**: `uv run fl-studio mixer pan 1 64`

### fl_route_to_mixer
- **Module**: mixing
- **Description**: Route a channel rack instrument to a dedicated mixer track.
- **Parameters**: `channel_index` (int 0-127), `track_index` (int 0-127)
- **CLI**: `uv run fl-studio mixer route 0 1`

### fl_get_mixer_state
- **Module**: mixing
- **Description**: Bidirectional — query volume, pan, and name for a range of mixer tracks (max 32).
- **Parameters**: `start_track` (int 0-127, default 0), `end_track` (int 0-127, default 16), `timeout_ms` (int)
- **CLI**: `uv run fl-studio mixer state --start 0 --end 8`

### fl_get_track_peaks
- **Module**: mixing
- **Description**: Get the current Left and Right audio peak levels for a mixer track.
- **Parameters**: `track_index` (int 0-127, default 0)

### fl_auto_mix
- **Module**: mixing
- **Description**: Dynamic mixer assistant — reads peak levels, calculates dB adjustments, sends corrective volume commands.
- **Parameters**: `tracks` (list[int]), `target_db` (float, default -12.0), `headroom_db` (float, default -3.0)

---

## 5. Patterns & Pattern Control (9 tools)

### fl_create_pattern
- **Module**: patterns
- **Description**: Create a new empty pattern at the next available slot.
- **Parameters**: `ack` (bool, default false), `timeout_ms` (int)
- **CLI**: `uv run fl-studio patterns create`

### fl_select_pattern
- **Module**: patterns
- **Description**: Jump to a specific pattern by 0-based index.
- **Parameters**: `pattern_index` (int 0-127, required)
- **CLI**: `uv run fl-studio patterns select 2`

### fl_set_pattern_color
- **Module**: patterns
- **Description**: Set the display color of a pattern.
- **Parameters**: `pattern_index` (int), `color_hex` (int, 24-bit RGB)

### fl_list_patterns
- **Module**: pattern_list
- **Description**: Bidirectional — list all pattern names and indices.
- **Parameters**: `timeout_ms` (int 100-10000, default 2000)
- **CLI**: `uv run fl-studio patterns list`

### fl_get_notes
- **Module**: pattern_control
- **Description**: Bidirectional — read MIDI notes of the active pattern from FL Studio's session cache.
- **Parameters**: `timeout_ms` (int 100-10000, default 2000)
- **CLI**: `uv run fl-studio patterns notes`

### fl_get_context
- **Module**: pattern_control
- **Description**: Bidirectional — consolidate status, channel rack list, and active pattern notes in one call.
- **Parameters**: `timeout_ms` (int 100-10000, default 2000)
- **CLI**: `uv run fl-studio context`

### fl_set_pattern_length
- **Module**: pattern_control
- **Description**: Resize a pattern's length in beats.
- **Parameters**: `pattern_index` (int 0-999), `length_beats` (int 1-999)
- **CLI**: `uv run fl-studio patterns length 0 16`

### fl_rename_channel
- **Module**: pattern_control
- **Description**: Rename a channel rack slot (ASCII, max 14 chars).
- **Parameters**: `channel_index` (int 0-127), `name` (str 1-14)
- **CLI**: `uv run fl-studio channels rename 0 "Kick"`

### fl_rename_pattern
- **Module**: pattern_control
- **Description**: Rename a pattern slot (ASCII, max 14 chars).
- **Parameters**: `pattern_index` (int 0-999), `name` (str 1-14)
- **CLI**: `uv run fl-studio patterns rename 0 "Verse"`

---

## 6. Song/Project Management (22 tools)

### Song Info & Length

#### fl_get_song_length
- **Module**: song_project_management
- **Description**: Get the total duration of the current song in seconds.
- **Parameters**: None
- **CLI**: `uv run fl-studio get-song-length`

#### fl_get_song_info
- **Module**: song_project_management
- **Description**: Get comprehensive song metadata (title, author, BPM, key, time signature, markers, etc.).
- **Parameters**: None
- **CLI**: `uv run fl-studio get-song-info`

### Markers

#### fl_set_song_marker
- **Module**: song_project_management
- **Description**: Add a marker at the current transport position with name and RGB color.
- **Parameters**: `marker_name` (str, required), `color_r` (int 0-255), `color_g` (int 0-255), `color_b` (int 0-255)
- **CLI**: `uv run fl-studio set-song-marker --marker-name "Drop" --color-r 255 --color-g 50 --color-b 50`

#### fl_get_marker
- **Module**: song_project_management
- **Description**: Get information about a specific marker by index.
- **Parameters**: `marker_index` (int >= 0, required)
- **CLI**: `uv run fl-studio get-marker --marker-index 0`

#### fl_delete_marker
- **Module**: song_project_management
- **Description**: Delete a marker from the playlist by index.
- **Parameters**: `marker_index` (int >= 0, required)
- **CLI**: `uv run fl-studio delete-marker --marker-index 0`

#### fl_insert_marker
- **Module**: song_project_management
- **Description**: Insert a marker at a specific beat position with name and RGB color.
- **Parameters**: `position_beats` (float >= 0), `marker_name` (str), `color_r/g/b` (int 0-255)
- **CLI**: `uv run fl-studio insert-marker --position-beats 8 --marker-name "Verse"`

### Tempo

#### fl_get_song_tempo
- **Module**: song_project_management
- **Description**: Query current tempo as integer BPM via bidirectional status.
- **Parameters**: `timeout_ms` (int 100-10000, default 2000)
- **CLI**: `uv run fl-studio get-song-tempo`

#### fl_get_song_bpm
- **Module**: song_project_management
- **Description**: Query current BPM as float (higher precision).
- **Parameters**: None
- **CLI**: `uv run fl-studio get-song-bpm`

#### fl_set_song_bpm
- **Module**: song_project_management
- **Description**: Set project tempo to absolute BPM (20-999). Requires `confirm=true`.
- **Parameters**: `bpm` (int 20-999), `confirm` (bool, default false)
- **CLI**: `uv run fl-studio set-song-bpm --bpm 128 --confirm`

#### fl_set_song_tempo_relative
- **Module**: song_project_management
- **Description**: Adjust tempo by percentage relative to current BPM (-50% to +200%). Requires `confirm=true`.
- **Parameters**: `percentage` (float -50 to 200), `confirm` (bool, default false)
- **CLI**: `uv run fl-studio set-song-tempo-relative --percentage 25 --confirm`

### Save & Export

#### fl_save_as_project
- **Module**: song_project_management
- **Description**: Save project with a new filename. Requires `confirm=true`.
- **Parameters**: `filename` (str, .flp extension), `confirm` (bool, default false)
- **CLI**: `uv run fl-studio save-as-project --filename "Track.flp" --confirm`

#### fl_export_audio
- **Module**: song_project_management
- **Description**: Export audio (wav/mp3/flac) with quality 0-100. Requires `confirm=true`.
- **Parameters**: `output_path` (str), `format` (str: wav/mp3/flac), `quality` (int 0-100, default 90), `confirm` (bool)
- **CLI**: `uv run fl-studio export-audio --output-path ~/Desktop/track.wav --format wav --quality 90 --confirm`

### Count Queries

#### fl_get_mixer_track_count
- **Module**: song_project_management
- **Description**: Get number of tracks in the mixer.
- **Parameters**: `timeout_ms` (int 100-10000, default 2000)
- **CLI**: `uv run fl-studio get-mixer-track-count`

#### fl_get_channel_count
- **Module**: song_project_management
- **Description**: Get number of channels in the channel rack.
- **Parameters**: `timeout_ms` (int 100-10000, default 2000)
- **CLI**: `uv run fl-studio get-channel-count`

#### fl_get_pattern_count
- **Module**: song_project_management
- **Description**: Get number of patterns in the song.
- **Parameters**: `timeout_ms` (int 100-10000, default 2000)
- **CLI**: `uv run fl-studio get-pattern-count`

### Pattern Operations

#### fl_get_current_pattern
- **Module**: song_project_management
- **Description**: Get the index of the currently selected pattern.
- **Parameters**: `timeout_ms` (int 100-10000, default 2000)
- **CLI**: `uv run fl-studio get-current-pattern`

#### fl_set_current_pattern
- **Module**: song_project_management
- **Description**: Set the active pattern by index. Requires `confirm=true`.
- **Parameters**: `pattern_index` (int >= 0), `confirm` (bool, default false)
- **CLI**: `uv run fl-studio set-current-pattern --pattern-index 2 --confirm`

#### fl_duplicate_pattern
- **Module**: song_project_management
- **Description**: Create a copy of the current pattern at the next available slot.
- **Parameters**: None
- **CLI**: `uv run fl-studio duplicate-pattern`

#### fl_copy_pattern
- **Module**: song_project_management
- **Description**: Copy current pattern to a specific target slot (0-127). Requires `confirm=true`.
- **Parameters**: `target_pattern_index` (int 0-127), `confirm` (bool, default false)
- **CLI**: `uv run fl-studio copy-pattern --target-pattern-index 5`

#### fl_cut_pattern
- **Module**: song_project_management
- **Description**: Cut current pattern to clipboard.
- **Parameters**: None
- **CLI**: `uv run fl-studio cut-pattern`

#### fl_paste_pattern
- **Module**: song_project_management
- **Description**: Paste pattern from clipboard to a specific slot (0-127). Requires `confirm=true`.
- **Parameters**: `target_pattern_index` (int 0-127), `confirm` (bool, default false)
- **CLI**: `uv run fl-studio paste-pattern --target-pattern-index 3`

#### fl_clear_pattern
- **Module**: song_project_management
- **Description**: Remove all notes from the currently selected pattern.
- **Parameters**: None
- **CLI**: `uv run fl-studio clear-pattern`

---

## 7. GUI Automation & UI (6 tools)

### fl_click_at
- **Module**: gui_automation
- **Description**: Simulate a mouse click at specific screen coordinates for VST preset navigation, etc.
- **Parameters**: `x` (int), `y` (int), `delay_ms` (int, default 100), `relative` (bool, default true)

### fl_reset_ui
- **Module**: gui_automation
- **Description**: Reset/arrange FL Studio windows to standard layout (Ctrl+Shift+H equivalent).
- **Parameters**: `layout` (str, default "default")

### fl_dismiss_popup
- **Module**: gui_automation
- **Description**: Dismiss an active modal dialog in FL Studio (Enter or Escape).
- **Parameters**: `action` (str: "confirm" or "cancel", default "confirm")

### fl_show_window
- **Module**: gui_automation
- **Description**: Show a specific FL Studio internal window (Mixer, Channel Rack, Playlist, etc.).
- **Parameters**: `window` (str: mixer/channel_rack/playlist/piano_roll/browser/plugin), `channel_index` (int)

### fl_browser_nav
- **Module**: gui_automation
- **Description**: Navigate the FL Studio Browser (up/down/left/right/enter).
- **Parameters**: `action` (str: up/down/left/right/enter)

### fl_ui_navigate
- **Module**: ui
- **Description**: Navigate FL Studio UI programmatically.
- **Parameters**: `action_id` (int)

---

## 8. VST, Plugins & Library (11 tools)

### fl_list_installed_plugins
- **Module**: vst_scanner
- **Description**: Scan FL Studio plugin database and optionally system VST/VST3/AU folders.
- **Parameters**: `scan_system` (bool, default false)
- **CLI**: `uv run fl-studio plugins list --scan-system`

### fl_load_plugin
- **Module**: vst_scanner
- **Description**: Focus FL Studio, open Plugin Picker (F8), search for plugin name, press Enter.
- **Parameters**: `name` (str)
- **CLI**: `uv run fl-studio plugins load "Serum"`

### fl_list_library
- **Module**: library
- **Description**: Scan FL Studio user data folders for scores, presets, templates, audio files.
- **Parameters**: `library_type` (str: scores/channels/mixer/templates/audio/all)
- **CLI**: `uv run fl-studio library list --type scores`

### fl_load_file
- **Module**: library
- **Description**: Open a preset (.fst), project (.flp), score (.fsc), or audio file.
- **Parameters**: `file_path` (str)
- **CLI**: `uv run fl-studio library load /path/to/file.flp`

### fl_index_sample_library
- **Module**: library
- **Description**: Scan a sample directory and extract acoustic features into a local SQLite vector database.
- **Parameters**: `directory_path` (str)

### fl_semantic_sample_search
- **Module**: library
- **Description**: Query the local sample index using natural language (e.g. "dark punchy 808").
- **Parameters**: `query` (str), `auto_load_to_channel` (bool, default true)

### fl_set_plugin_param
- **Module**: plugins
- **Description**: Set a VST plugin parameter value by index.
- **Parameters**: `target_type` (int 0-1), `track_or_chan_idx` (int), `slot_idx` (int), `param_idx` (int 0-4095), `value` (float 0.0-1.0)

### fl_get_plugin_param
- **Module**: plugins
- **Description**: Get a VST plugin parameter value.
- **Parameters**: `target_type` (int 0-1), `track_or_chan_idx` (int), `slot_idx` (int), `param_idx` (int 0-4095)

### fl_catalog_vst_preset
- **Module**: presets
- **Description**: Save click coordinates and metadata for a VST preset.
- **Parameters**: `vst_name` (str), `preset_name` (str), `x` (int), `y` (int), `category` (str), `tags` (list[str]|null), `notes` (str)

### fl_search_vst_presets
- **Module**: presets
- **Description**: Search cataloged VST presets by keyword, VST name, tag, or category.
- **Parameters**: `query` (str, optional), `vst_name` (str, optional), `tag` (str, optional), `category` (str, optional)

### fl_load_vst_preset
- **Module**: presets
- **Description**: Look up saved coordinates for a preset and simulate a mouse click to load it.
- **Parameters**: `vst_name` (str), `preset_name` (str)

---

## 9. Algorithmic Composition (3 tools)

### fl_insert_euclidean_drums
- **Module**: algorithmic
- **Description**: Generate step-sequencer drum patterns using Bjorklund's Euclidean rhythm algorithm.
- **Parameters**: `mapping` (str JSON), `rhythm` (str), `hits` (int 1-64), `steps` (int 1-128), `rotation` (int), `velocity_curve` (str), `swing` (float)

### fl_generate_markov_melody
- **Module**: algorithmic
- **Description**: Generate an organic, scale-constrained single-voice melody using Markov chains.
- **Parameters**: `root` (str), `scale` (str), `length_beats` (float), `rate` (str), `channel_index` (int), `velocity_curve` (str), `swing` (float)

### fl_insert_voice_led_progression
- **Module**: algorithmic
- **Description**: Insert a chord progression with minimum-transposition voice-leading optimization.
- **Parameters**: `progression` (str), `rate` (str), `channel_index` (int), `velocity_curve` (str), `swing` (float)

---

## 10. Music Theory & Patterns (4 tools)

### fl_insert_scale
- **Module**: composition
- **Description**: Generate and insert a sequence of scale notes across configurable octaves.
- **Parameters**: `root` (str), `scale` (str, supports 12 scale types), `octaves` (int 1-8), `rhythm` (str), `channel_index` (int)
- **CLI**: `uv run fl-studio composition scale --root C4 --scale minor`

### fl_insert_arpeggio
- **Module**: composition
- **Description**: Generate an arpeggiated chord pattern with configurable style (up/down/updown/random).
- **Parameters**: `root` (str), `chord_type` (str), `style` (str), `rate` (str), `octaves` (int 1-8)
- **CLI**: `uv run fl-studio composition arpeggio --root C4`

### fl_insert_drum_pattern
- **Module**: composition
- **Description**: Create step-sequencer style drum pattern across channels with hit maps.
- **Parameters**: `mapping` (str JSON), `rhythm` (str), `velocity_curve` (str), `swing` (float)
- **CLI**: `uv run fl-studio composition drums --mapping '{"0": [1,0,0,1]}'`

### fl_add_marker
- **Module**: composition
- **Description**: Add an arrangement time marker at the current song position.
- **Parameters**: `name` (str, max 14 chars)

---

## 11. DSP, Stems & Vision (8 tools)

### fl_analyze_sample
- **Module**: dsp
- **Description**: Analyze a .wav file for BPM, key, and transient detection (librosa).
- **Parameters**: `file_path` (str), `dry_run` (bool, default false)

### fl_auto_slice
- **Module**: dsp
- **Description**: Chop audio loops into discrete samples based on DSP transient detection.
- **Parameters**: `file_path` (str)

### fl_separate_stems
- **Module**: stems
- **Description**: Separate mixed audio into stems (vocals, drums, bass, other) using Demucs.
- **Parameters**: `path` (str), `output_dir` (str), `model` (str, default "htdemucs"), `dry_run` (bool)

### fl_render_stems
- **Module**: stems
- **Description**: Bounce isolated tracks iteratively using headless render macro.
- **Parameters**: Varies

### fl_vision_read_vst
- **Module**: vision
- **Description**: Capture screen and use a VLM to "read" non-automatable synth UIs.
- **Parameters**: Varies

### fl_vision_click_vst
- **Module**: vision
- **Description**: Execute coordinate-based clicks on Vision-derived UI nodes.
- **Parameters**: Varies

### fl_generate_sequence
- **Module**: midi_gen
- **Description**: Simulate a generative MIDI transformer for realistic drum/melody grooves.
- **Parameters**: Varies

### fl_sync_session
- **Module**: collaboration
- **Description**: Zip .flp and audio files, send a webhook alert (e.g., Discord).
- **Parameters**: `webhook_url` (str)

---

## 12. Mix Engineering (3 tools)

### fl_auto_mix_balance
- **Module**: mix_engineer
- **Description**: Calculate RMS of all tracks and balance faders to a pink-noise reference curve.
- **Parameters**: `target_rms_db` (float, default -14.0)

### fl_auto_sidechain
- **Module**: mix_engineer
- **Description**: Route kick to bass and insert Fruity Limiter for automatic pumping sidechain ducking.
- **Parameters**: `kick_track_name` (str), `target_track_name` (str), `threshold_db` (float), `ratio` (float)

### fl_vocal_chain_builder
- **Module**: mix_engineer
- **Description**: Insert genre-specific vocal FX chains (Modern Pop, Rap, Lo-Fi, Podcast).
- **Parameters**: `target_track_name` (str), `style` (str)

---

## 13. Arrangement & Song Structure (12 tools)

### fl_generate_song_structure
- **Module**: arranger
- **Description**: Expand existing patterns into a full macro arrangement in the Playlist using templates.
- **Parameters**: `bars` (int, default 64), `style` (str: Pop/EDM/Hip-Hop)

### fl_generate_transitions
- **Module**: arranger
- **Description**: Generate risers, crashes, and reverse sounds between song sections.
- **Parameters**: `density` (str, default "Medium")

### fl_generate_synth_preset
- **Module**: sound_design
- **Description**: Generate synthesizer preset parameters from a natural language prompt.
- **Parameters**: `prompt` (str), `synth_target` (str, default "Vital")

### fl_auto_master
- **Module**: mastering
- **Description**: Apply a mastering chain (EQ, Multiband Compressor, Soft Clipper, Limiter) to hit target LUFS.
- **Parameters**: `target_lufs` (float, default -14.0)

### fl_eq_reference_match
- **Module**: mastering
- **Description**: Match the tonal balance of the current mix to a reference track.
- **Parameters**: `reference_audio_path` (str)

### fl_gross_beat_automator
- **Module**: creative_fx
- **Description**: Automate Gross Beat for instant halftime, tape-stop, and gated FX.
- **Parameters**: Varies

### fl_auto_glitch_chops
- **Module**: creative_fx
- **Description**: Automatically slice and rearrange playlist audio clips for glitch fills.
- **Parameters**: Varies

### fl_audio_to_midi
- **Module**: audio_ai
- **Description**: Extract harmonic pitch data from audio and convert to MIDI notes.
- **Parameters**: Varies

### fl_generate_counter_melody
- **Module**: audio_ai
- **Description**: Analyze a chord progression to generate a complementary counter-melody.
- **Parameters**: Varies

### fl_build_patcher_instrument
- **Module**: workflow_advanced
- **Description**: Build a complex layered instrument using FL Studio's Patcher.
- **Parameters**: Varies

### fl_vst_auto_replace
- **Module**: vst_bridge
- **Description**: Auto-replace or swap VST plugins while preserving routing.
- **Parameters**: Varies

### fl_generate_project
- **Module**: project_generator
- **Description**: Generate or modify an FL Studio project offline with genre templates (trap, house, synthwave, empty).
- **Parameters**: `output_path` (str), `genre` (str), `bpm` (float, optional), `title` (str, optional), `channels` (list, optional)

---

## 14. Vocal Processing & Audio (4 tools)

### fl_vocal_aligner
- **Module**: vocal_alignment
- **Description**: Align multiple vocal takes/harmonies to a lead vocal track.
- **Parameters**: Varies

### fl_generate_visualizer_zgame
- **Module**: video_generation
- **Description**: Generate reactive visuals based on track stems using ZGameEditor Visualizer.
- **Parameters**: Varies

### fl_project_version_control
- **Module**: project_vc
- **Description**: Track and manage multiple versions/mixes of an FLP project.
- **Parameters**: Varies

### fl_export_dolby_atmos_stems
- **Module**: spatial_audio
- **Description**: Export Dolby Atmos / binaural spatial audio stems.
- **Parameters**: Varies

---

## 15. Performance & Live (10 tools)

### fl_live_performance_mode
- **Module**: performance
- **Description**: Trigger loops and clips in FL Studio's Performance Mode.
- **Parameters**: Varies

### fl_stem_separation_remix
- **Module**: remix
- **Description**: Use FL Studio's Stem Separation to rip acapella and generate a new instrumental beat.
- **Parameters**: `audio_file_path` (str)

### fl_foley_to_drumkit
- **Module**: remix
- **Description**: Take a field recording, slice transients, and map to FPC/Slicex.
- **Parameters**: `foley_audio_path` (str)

### fl_vocal_synth_vocodex
- **Module**: generative_vocals
- **Description**: Route vocals and synths into Vocodex automatically.
- **Parameters**: Varies

### fl_lyric_to_vocal_take
- **Module**: generative_vocals
- **Description**: Generate TTS audio and align it using Pitcher.
- **Parameters**: Varies

### fl_hardware_cv_gate_bridge
- **Module**: hardware
- **Description**: Send CV signals to external modular gear.
- **Parameters**: Varies

### fl_advanced_groove_extractor
- **Module**: optimization
- **Description**: Extract groove from audio and apply to MIDI patterns.
- **Parameters**: Varies

### fl_cpu_optimizer_bounce
- **Module**: optimization
- **Description**: Identify high-CPU VSTs and bounce them in place.
- **Parameters**: Varies

### fl_collaborative_cloud_sync
- **Module**: release
- **Description**: Package and upload project for remote collaboration.
- **Parameters**: Varies

### fl_industry_metadata_tagger
- **Module**: release
- **Description**: Embed ISRC codes and metadata into exported WAV files.
- **Parameters**: Varies

---

## 16. Genre & Sound Design (10 tools)

### fl_neuro_genre_fusion
- **Module**: genre_fusion
- **Description**: Mathematically blend properties of two distinct genres.
- **Parameters**: Varies

### fl_ai_session_musician_improviser
- **Module**: session_musician
- **Description**: Generate humanized AI improvised solos.
- **Parameters**: Varies

### fl_dynamic_soundscape_generator
- **Module**: soundscapes
- **Description**: Create generative, multi-layered ambient beds from text descriptions.
- **Parameters**: Varies

### fl_vocal_chain_cloner
- **Module**: vocal_cloning
- **Description**: Clone EQ, compression, and FX chains from a reference acapella.
- **Parameters**: Varies

### fl_film_score_sync
- **Module**: film_scoring
- **Description**: Sync tension strings and impacts to specific video timecodes.
- **Parameters**: Varies

### fl_psychoacoustic_exciter
- **Module**: psychoacoustics
- **Description**: Maximize perceived loudness via mid-side EQ and phase manipulation.
- **Parameters**: Varies

### fl_auto_foley_foley_designer
- **Module**: foley_designer
- **Description**: Synthesize complex foley sounds from scratch via FM routing.
- **Parameters**: Varies

### fl_adaptive_live_looping
- **Module**: live_looping
- **Description**: Setup Ableton-style auto-slice live looping with Edison.
- **Parameters**: Varies

### fl_chord_voicing_humanizer
- **Module**: humanization
- **Description**: Spread chord voicings and humanize strum velocities.
- **Parameters**: Varies

### fl_project_health_monitor
- **Module**: project_health
- **Description**: Background daemon to detect phase issues, CPU spikes, and ear fatigue.
- **Parameters**: Varies

---

## 17. Arrangement Builders (10 tools)

### fl_macro_arrangement_builder
- **Module**: arrangement_builder
- **Description**: Place arrangement markers and dummy blocks from structural text descriptions.
- **Parameters**: Varies

### fl_vocal_chop_kaleidoscope
- **Module**: vocal_chops
- **Description**: Slice vocal transients and generate glitchy, key-locked rhythmic sequences.
- **Parameters**: Varies

### fl_polyphonic_bass_extractor
- **Module**: audio_extraction
- **Description**: Extract low-end sub frequencies from complex loops and convert to MIDI.
- **Parameters**: Varies

### fl_auto_gain_staging_assistant
- **Module**: gain_staging
- **Description**: Normalize mixer faders to a pink-noise reference curve (-18dBFS).
- **Parameters**: Varies

### fl_drum_pattern_euclidean
- **Module**: euclidean_drums
- **Description**: Generate complex polyrhythmic grooves via Euclidean math.
- **Parameters**: Varies

### fl_sidechain_matrix_wizard
- **Module**: routing_wizard
- **Description**: Route all bass/synths to a Ghost Kick channel automatically.
- **Parameters**: Varies

### fl_generative_transition_fx
- **Module**: transition_fx
- **Description**: Synthesize risers, sweeps, and drops automatically before song sections.
- **Parameters**: Varies

### fl_hardware_synth_patch_dumper
- **Module**: hardware_midi
- **Description**: Bridge SysEx to pull and save patches from external hardware gear.
- **Parameters**: Varies

### fl_plugin_latency_compensator
- **Module**: latency
- **Description**: Auto-detect and fix manual track delays for PDC phase smearing.
- **Parameters**: Varies

### fl_holographic_mixer_ui
- **Module**: custom_ui
- **Description**: Build a Patcher dashboard of the top 10 most-automated project parameters.
- **Parameters**: Varies

---

## 18. Post-Production (10 tools)

### fl_podcast_auto_editor
- **Module**: podcast_editing
- **Description**: Detect silence, cross-talk, and apply gating/ducking for broadcast podcasts.
- **Parameters**: Varies

### fl_spectral_morphing_engine
- **Module**: spectral_morphing
- **Description**: Use Harmor to morph spectral characteristics of two distinct samples.
- **Parameters**: Varies

### fl_automated_remix_contest_parser
- **Module**: remix_contest
- **Description**: Unpack stems, detect key/BPM, and map to Playlist.
- **Parameters**: Varies

### fl_polyphonic_aftertouch_generator
- **Module**: mpe_generation
- **Description**: Generate complex MPE automation data for block chords.
- **Parameters**: Varies

### fl_orchestral_articulation_mapper
- **Module**: orchestral_scoring
- **Description**: Swap orchestral articulations based on MIDI phrasing.
- **Parameters**: Varies

### fl_generative_lyric_video_sync
- **Module**: lyric_video
- **Description**: Map lyric text to vocal transients via ZGameEditor Visualizer.
- **Parameters**: Varies

### fl_master_bus_clipper_optimizer
- **Module**: master_bus
- **Description**: Mathematically soft-clip master bus to save headroom.
- **Parameters**: Varies

### fl_lofi_degradation_matrix
- **Module**: lofi_fx
- **Description**: Apply automated tape wow, flutter, and vinyl crackle via parallel processing.
- **Parameters**: Varies

### fl_song_structure_mutator
- **Module**: arrangement_mutator
- **Description**: Algorithmic rearrangement of Playlist blocks to IDM/Glitch hop sequences.
- **Parameters**: `entropy_level` (float, default 0.7), `slice_resolution` (str, default "1/4 beat")

### fl_vst_preset_ai_curator
- **Module**: preset_curator
- **Description**: Scan local .fst libraries and NLP-tag presets for instant loading.
- **Parameters**: Varies

---

## 19. Advanced MIDI & Audio (10 tools)

### fl_neural_rhythm_quantizer
- **Module**: neural_quantizer
- **Description**: Extract timing/groove swing from live audio to create FL Groove Templates.
- **Parameters**: Varies

### fl_sub_bass_harmonic_synthesizer
- **Module**: harmonic_synth
- **Description**: Generate matching sub-bass MIDI patterns with harmonic saturation.
- **Parameters**: Varies

### fl_dynamic_vocal_rider
- **Module**: vocal_rider
- **Description**: Balance vocal levels against instrumental mixes using volume automation.
- **Parameters**: Varies

### fl_intelligent_transient_splitter
- **Module**: transient_splitter
- **Description**: Split audio into separate Transient and Sustain channels.
- **Parameters**: Varies

### fl_chord_progression_voicer
- **Module**: chord_voicer
- **Description**: Voice MIDI chord progressions using keyboard voice-leading rules.
- **Parameters**: `pattern_index` (int), `target_instrument` (str), `complexity_level` (float)

### fl_multiband_stereo_widener_matrix
- **Module**: stereo_widener
- **Description**: Split signals into Low (mono), Mid (Haas), and High (delay) bands.
- **Parameters**: Varies

### fl_polyphonic_midi_to_audio_harmonizer
- **Module**: audio_harmonizer
- **Description**: Generate multi-part backing harmonies from vocal audio and MIDI chords.
- **Parameters**: `lead_vocal_track` (int), `chord_midi_pattern` (int), `harmony_type` (str)

### fl_resampler_glitch_generator
- **Module**: glitch_generator
- **Description**: Bounce playlist regions to audio, load into Slicex/Granulizer, randomize.
- **Parameters**: Varies

### fl_intelligent_sidechain_carver
- **Module**: sidechain_carver
- **Description**: Set up dynamic frequency-specific sidechain ducking.
- **Parameters**: Varies

### fl_ai_track_sheet_generator
- **Module**: track_sheet
- **Description**: Auto-scan project layout and compile a professional track sheet.
- **Parameters**: Varies
