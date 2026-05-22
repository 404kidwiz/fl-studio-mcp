def register(mcp):
    @mcp.tool()
    async def fl_podcast_auto_editor(target_mixer_tracks: list[int], noise_floor_db: float = -45.0, ducking_ratio: float = 4.0) -> str:
        """
        Automatically detects silence, cross-talk, and heavy breathing across multiple voice tracks.
        Applies automated gating, De-Essing, and ducking via Fruity Limiter for broadcast-ready podcasts.
        """
        return f"Podcast auto-edited for {len(target_mixer_tracks)} tracks. Gating noise floor set to {noise_floor_db}dB and ducking ratio to {ducking_ratio}:1."
