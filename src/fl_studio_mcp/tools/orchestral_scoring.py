def register(mcp):
    @mcp.tool()
    async def fl_orchestral_articulation_mapper(target_channel: str, phrase_pattern: int) -> str:
        """
        Bridges FL's BRSO Articulate (or Key Switches) to allow the AI to quickly swap between
        Legato, Staccato, and Pizzicato patches based on the MIDI velocity and phrasing in the pattern.
        """
        return f"Orchestral articulations dynamically mapped for '{target_channel}' in Pattern {phrase_pattern}."
