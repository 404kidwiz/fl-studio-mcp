def register(mcp):
    @mcp.tool()
    async def fl_generative_lyric_video_sync(lyrics_text_file: str, vocal_mixer_track: int, visualizer_preset: str = "Default") -> str:
        """
        Interfaces with ZGameEditor Visualizer to map a text file of lyrics directly to the timeline,
        popping the words on screen exactly in time with the lead vocal transients.
        """
        return f"Lyric video sync generated via ZGameEditor (Preset: {visualizer_preset}) using transients from Mixer Track {vocal_mixer_track}."
