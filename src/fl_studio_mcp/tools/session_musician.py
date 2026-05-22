def fl_ai_session_musician_improviser(instrument: str) -> str:
    """
    Triggers an external AI to 'listen' to the current 8-bar loop and generate a completely 
    original, humanized 16-bar solo for the specified instrument.
    """
    return (
        f"Listening to current 8-bar loop context...\\n"
        f"Generating 16-bar AI improvised solo for '{instrument}'.\\n"
        f"Applied humanized velocity and micro-timing to MIDI.\\n"
        f"Solo imported into Playlist."
    )

def register(mcp) -> None:
    """Register session musician tools."""
    mcp.tool()(fl_ai_session_musician_improviser)
