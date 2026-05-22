# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] - 2026-05-22

### Added
- **`fl-studio install-bridge` CLI**: New command to automatically install the `device_fl_mcp_bridge.py` controller script into the correct macOS or Windows FL Studio User Data folder.
- **`fl-studio status` Diagnostics**: New CLI command (and `fl_health_check` MCP tool) to output environment diagnostics, bridge statuses, open MIDI ports, and python versions.
- **Input Sanitization**: macOS (AppleScript) and Windows (VBScript) automation inputs are now aggressively sanitized to prevent OS-level injection vulnerabilities.
- **GUI Automation Stability**: Asynchronous `_with_retry` wrapper automatically retries inherently flaky GUI automation calls up to 3 times to handle FL Studio window focus contention.
- **OS Subprocess Logging**: AppleScript, VBScript, and PowerShell errors (`stderr`) are now captured and bubbled up to MCP logs instead of failing silently.
- **Windows CI Support**: Automated testing pipeline now supports Windows runners and Python 3.13.

### Changed
- Standardized `device_fl_mcp_bridge.py` version string to match `0.8.0`.
- **`fl_save_project` Safety**: The save tool now requires `confirm: true` to prevent AI agents from accidentally overwriting user projects.

## [0.7.0] - 2026-05-21

### Added
- **Full Windows Support**: Replaced previous macOS-only AppleScript automation with dual-platform support. Added `windows.py` using `cscript` (VBScript) and PowerShell for cross-platform GUI automation (loading plugins, navigating menus).
- **GUI Automation Tools**: New suite of tools for mouse and keyboard control (`click_at`, `press_key`, `type_text`).
- **Plugin Management**: `load_plugin` tool now works seamlessly on Windows via `TFruityLoopsInstance` process detection.

### Fixed
- Fixed hardcoded macOS paths in distribution guides.

## [0.6.0] - 2026-05-20

### Added
- Comprehensive Pytest suite covering MIDI encode/decode, MCP tool routing, and automation interfaces.

## [0.5.0] - 2026-05-19

### Added
- Advanced algorithmic composition tools (Markov melodies, Euclidean rhythms).
- Preset librarian tools.

## [0.4.0] - 2026-05-18

### Added
- Extensive channel, mixer, and pattern management tools (`fl_set_channel_pan`, `fl_set_mixer_volume`, `fl_route_to_mixer`).

## [0.3.0] - 2026-05-17

### Added
- `fl-studio` Click CLI entry point.
- Renamed save tools for clarity (`fl_save_project_as` to `fl_save_project`).

## [0.2.0] - 2026-05-16

### Added
- Initial FastMCP integration.
- Bidirectional MIDI SysEx transport layer (`FLStudioBridge`).

## [0.1.0] - 2026-05-15

### Added
- Initial proof-of-concept for bridging FL Studio to external scripts via virtual MIDI ports.
