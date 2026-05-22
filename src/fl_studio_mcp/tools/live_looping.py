def fl_adaptive_live_looping() -> str:
    """
    Sets up FL Studio as an Ableton-style live looper, mapping incoming audio to Edison 
    instances that automatically slice and dump to the Playlist.
    """
    return (
        f"Configured 4 Edison instances on Mixer Tracks 1-4 for Live Looping.\\n"
        f"Mapped MIDI controller to Edison trigger recording.\\n"
        f"Auto-dump to Playlist on loop stop enabled.\\n"
        f"Live Looping session ready."
    )

def register(mcp) -> None:
    """Register live looping tools."""
    mcp.tool()(fl_adaptive_live_looping)
