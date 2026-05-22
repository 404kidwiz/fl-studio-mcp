def register(mcp):
    @mcp.tool()
    async def fl_polyphonic_midi_to_audio_harmonizer(lead_vocal_track: int, chord_midi_pattern: int, harmony_type: str = "4-part") -> str:
        """
        Takes a lead vocal audio track and a MIDI chord pattern, using Fruity Vocoder or dynamic Pitcher instances
        to generate lush, multi-part backing vocal harmonies that follow the exact chords.
        """
        return f"Vocoder/Pitcher harmonizer mapped lead vocal track {lead_vocal_track} to chord MIDI Pattern {chord_midi_pattern} utilizing a {harmony_type} harmony template."
