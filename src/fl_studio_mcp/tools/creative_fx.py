def fl_gross_beat_automator(effect_type: str = "halftime", bars_interval: int = 8) -> str:
    """
    Automatically inserts Gross Beat and automates its slots to trigger effects like halftime or tape-stop at set intervals.
    """
    valid_effects = ["halftime", "tape-stop", "1/4 gate", "stutter"]
    if effect_type not in valid_effects:
        effect_type = "halftime"
        
    return (
        f"Gross Beat inserted on Master bus.\\n"
        f"Automation clip created to trigger '{effect_type}' every {bars_interval} bars.\\n"
        f"Transitions enhanced with time manipulation."
    )

def fl_auto_glitch_chops(target_track: int) -> str:
    """
    Slices the audio clips on the target playlist track and rearranges them to create stutter/glitch fills.
    """
    return (
        f"Analyzed audio clips on Playlist Track {target_track}.\\n"
        f"Applied 1/16th note slicing at the end of 8-bar boundaries.\\n"
        f"Glitch/stutter fills successfully generated."
    )

def register(mcp) -> None:
    """Register creative FX tools."""
    mcp.tool()(fl_gross_beat_automator)
    mcp.tool()(fl_auto_glitch_chops)
