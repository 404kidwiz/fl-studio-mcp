"""FL Studio MCP server entry point.

Run via:
    uv run fl-studio-mcp          # installed package
    python -m fl_studio_mcp.server  # development

The server communicates over stdio (Claude Desktop / MCP clients) and bridges
commands to FL Studio via MIDI using the IAC Driver on macOS.
"""

import os

from mcp.server.fastmcp import FastMCP

from .tools import connection, midi_ports, notes, project, tempo, transport_control

mcp = FastMCP(
    "fl_studio_mcp",
    instructions=(
        "Control FL Studio via MIDI. "
        "Start with fl_list_midi_ports to discover available ports, "
        "then fl_connect to open the connection, "
        "then use transport/tempo/notes/project tools. "
        "Set dry_run=true in fl_connect to preview without sending MIDI."
    ),
)

# Register all tools
midi_ports.register(mcp)
connection.register(mcp)
transport_control.register(mcp)
tempo.register(mcp)
notes.register(mcp)
project.register(mcp)


def main() -> None:
    """Entry point for the fl-studio-mcp CLI command."""
    dry_run = os.getenv("FL_MCP_DRY_RUN", "0") == "1"
    if dry_run:
        import sys
        print("FL Studio MCP starting in DRY-RUN mode (no MIDI will be sent)", file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    main()
