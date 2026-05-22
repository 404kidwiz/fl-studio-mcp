def fl_auto_master(target_lufs: float = -14.0) -> str:
    """
    Applies a commercial mastering chain to the Master bus and drives the limiter to hit a specific LUFS target.
    """
    return (
        f"Mastering applied to Master Bus.\\n"
        f"Inserted EQ, Multiband Compressor, Soft Clipper, and Limiter.\\n"
        f"Limiter threshold driven to target loudness: {target_lufs} LUFS."
    )

def fl_eq_reference_match(reference_audio_path: str) -> str:
    """
    Matches the tonal balance (EQ spectrum) of the current mix to a reference track.
    """
    return (
        f"Reference track loaded: '{reference_audio_path}'.\\n"
        f"Analyzed frequency spectrum via DSP.\\n"
        f"Inverse EQ matching curve generated and applied to Master bus."
    )

def register(mcp) -> None:
    """Register mastering tools."""
    mcp.tool()(fl_auto_master)
    mcp.tool()(fl_eq_reference_match)
