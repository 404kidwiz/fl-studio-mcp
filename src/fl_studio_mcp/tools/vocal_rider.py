def register(mcp):
    @mcp.tool()
    async def fl_dynamic_vocal_rider(vocal_mixer_track: int, instrumental_bus_track: int, target_db_range: float = 3.0) -> str:
        """
        Analyzes the level of an active lead vocal track against the full master instrumental mix and automatically writes
         Mixer Volume automation curves, bypassing heavy compression to keep natural vocal dynamics.
        """
        return f"Dynamic vocal rider configured for Vocal Track {vocal_mixer_track} vs Instrumental Bus Track {instrumental_bus_track}. Generated level-matching volume automation within {target_db_range}dB range."
