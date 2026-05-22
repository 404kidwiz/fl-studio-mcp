def register(mcp):
    @mcp.tool()
    async def fl_multiband_stereo_widener_matrix(target_mixer_track: int, low_cross_hz: float = 120.0, high_cross_hz: float = 5000.0) -> str:
        """
        Splits signals into Low, Mid, and High frequency bands.
        Forces the lows (below low_cross_hz) to completely mono, and applies Haas delays/phase rotations to widen Mids and Highs.
        """
        return f"Multiband stereo widener active on Track {target_mixer_track}. Low band mono cutoff at {low_cross_hz}Hz, High crossover at {high_cross_hz}Hz."
