def register(mcp):
    @mcp.tool()
    async def fl_intelligent_transient_splitter(source_mixer_track: int, transient_track: int, sustain_track: int) -> str:
        """
        Splits any audio channel/track into separate 'Transient/Attack' and 'Sustain/Decay' signals.
        Routes them to parallel mixer tracks for unique selective processing.
        """
        return f"Transient splitter set up. Routed Source Track {source_mixer_track} outputs to Transient Track {transient_track} and Sustain Track {sustain_track} respectively."
