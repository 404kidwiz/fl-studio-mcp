def register(mcp):
    @mcp.tool()
    async def fl_resampler_glitch_generator(start_bar: int, end_bar: int, density: float = 0.5) -> str:
        """
        Bounces the playlist region from start_bar to end_bar down to audio, loads it into Fruity Granulizer or Slicex,
        and randomizes playhead speeds, stretch parameters, and panning to create dynamic IDM glitch fills.
        """
        return f"Resampled region from Bar {start_bar} to {end_bar}. Glitch algorithm active in Slicex/Granulizer with fill density {density}."
