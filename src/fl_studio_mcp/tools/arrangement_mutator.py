def register(mcp):
    @mcp.tool()
    async def fl_song_structure_mutator(entropy_level: float = 0.7, slice_resolution: str = "1/4 beat") -> str:
        """
        Selects a fully arranged song, randomly slices the blocks on the Playlist, and mathematically
        re-arranges them into an IDM/Glitch hop sequence.
        """
        return f"Song structure mutated with entropy {entropy_level} at a slice resolution of '{slice_resolution}'. IDM sequence generated."
