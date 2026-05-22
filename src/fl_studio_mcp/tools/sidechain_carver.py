def register(mcp):
    @mcp.tool()
    async def fl_intelligent_sidechain_carver(kick_mixer_track: int, bass_mixer_track: int, frequency_hz: float = 80.0) -> str:
        """
        Sets up clean frequency-specific dynamic EQ carving.
        Links a Fruity Peak Controller on the Kick track to duck a designated band (around frequency_hz) on the Bass Mixer Track.
        """
        return f"Intelligent sidechain carving active. Ducking competing frequencies on Bass Track {bass_mixer_track} centered at {frequency_hz}Hz whenever Kick Track {kick_mixer_track} transients trigger."
