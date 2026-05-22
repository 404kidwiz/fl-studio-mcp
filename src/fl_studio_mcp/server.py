"""FL Studio MCP server entry point.

Run via:
    uv run fl-studio-mcp          # installed package
    python -m fl_studio_mcp.server  # development

The server communicates over stdio (Claude Desktop / MCP clients) and bridges
commands to FL Studio via MIDI using the IAC Driver on macOS.
"""

import os
import logging

# Configure logging based on FL_MCP_LOG_LEVEL
log_level_name = os.getenv("FL_MCP_LOG_LEVEL", "WARNING").upper()
log_level = getattr(logging, log_level_name, logging.WARNING)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from mcp.server.fastmcp import FastMCP

from .tools import (
    channels,
    composition,
    connection,
    library,
    midi_ports,
    mixing,
    notes,
    pattern_control,
    pattern_list,
    patterns,
    project,
    status,
    tempo,
    transport_control,
    vst_scanner,
    gui_automation,
    presets,
    algorithmic,
    plugins,
    ui,
    project_generator,
    dsp,
    vision,
    stems,
    midi_gen,
    collaboration,
)

from . import resources, prompts

mcp = FastMCP(
    "fl_studio_mcp",
    instructions=(
        "Control FL Studio via MIDI and native OS automation. "
        "Workflow: fl_list_midi_ports → fl_connect → fl_get_status to verify → "
        "then use transport/tempo/notes/project/channel/pattern/mixing tools. "
        "Set dry_run=true in fl_connect to preview without sending MIDI. "
        "Bidirectional tools (fl_get_status, fl_list_channels, fl_list_patterns) "
        "require the FL MCP Bridge controller script loaded in FL Studio's MIDI Settings. "
        "Exposes filesystem/system plugins scanning via fl_list_installed_plugins/fl_list_library "
        "and VST/file loading via fl_load_plugin/fl_load_file using GUI automation. "
        "Use fl_panic any time notes get stuck. "
        'Note pitch accepts integers (60) or note names ("C4", "F#3", "Bb4"). '
        "fl_insert_notes plays notes in realtime — to record into a pattern, "
        "enable Record mode in FL Studio's transport first, then insert notes. "
        "fl_save_project saves to the current filename (Ctrl+S equivalent). "
        "Use fl_disconnect to close ports cleanly when done."
    ),
)

# Register all tools
midi_ports.register(mcp)
connection.register(mcp)
transport_control.register(mcp)
tempo.register(mcp)
notes.register(mcp)
project.register(mcp)
status.register(mcp)
channels.register(mcp)
patterns.register(mcp)
pattern_list.register(mcp)
mixing.register(mcp)
vst_scanner.register(mcp)
library.register(mcp)
pattern_control.register(mcp)
composition.register(mcp)
gui_automation.register(mcp)
presets.register(mcp)
algorithmic.register(mcp)
plugins.register(mcp)
ui.register(mcp)
project_generator.register(mcp)
dsp.register(mcp)
vision.register(mcp)
stems.register(mcp)
midi_gen.register(mcp)
collaboration.register(mcp)

# Register resources and prompts
resources.register(mcp)
prompts.register(mcp)


def main() -> None:
    """Entry point for the fl-studio-mcp CLI command."""
    dry_run = os.getenv("FL_MCP_DRY_RUN", "0") == "1"
    if dry_run:
        import sys

        print(
            "FL Studio MCP starting in DRY-RUN mode (no MIDI will be sent)",
            file=sys.stderr,
        )
    mcp.run()


if __name__ == "__main__":
    main()
