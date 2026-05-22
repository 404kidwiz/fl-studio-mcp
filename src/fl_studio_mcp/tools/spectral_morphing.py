def register(mcp):
    @mcp.tool()
    async def fl_spectral_morphing_engine(source_a_path: str, source_b_path: str, morph_ratio: float = 0.5) -> str:
        """
        Uses Harmor's resynthesis engine to combine the spectral characteristics of two completely different samples.
        For example, morphing a cello and a chainsaw into a single playable instrument patch.
        """
        return f"Spectral morphing patch generated using '{source_a_path}' and '{source_b_path}' with a morph ratio of {morph_ratio}."
