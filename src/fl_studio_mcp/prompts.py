"""MCP Prompts implementation for FL Studio MCP server."""

from mcp.server.fastmcp import FastMCP

def register(mcp: FastMCP) -> None:
    """Register all pre-built developer and creative prompts on the FastMCP instance."""

    @mcp.prompt("generate-trap-loop")
    def generate_trap_loop(tempo: int = 140) -> str:
        """Create a prompt instructions template for generating a standard 4-bar Trap drum loop.

        Args:
            tempo (int): Playback BPM tempo (default 140).

        Returns:
            str: The creative instruction prompt text.
        """
        return (
            f"You are an expert music producer specializing in modern Trap production. "
            f"Generate a standard 4-bar Trap drum loop at {tempo} BPM.\n\n"
            f"Instructions:\n"
            f"1. Check connection with fl_get_status.\n"
            f"2. Set the project tempo using fl_set_tempo to {tempo}.\n"
            f"3. Insert high-energy 808s, rolling hi-hats, sharp snares, and hard-hitting kicks using fl_insert_drum_pattern or fl_insert_notes.\n"
            f"4. Apply classic Trap hi-hat triplets and snare rolls. Play the snare on the 3rd beat of every bar."
        )

    @mcp.prompt("insert-chords")
    def insert_chords(key: str = "C", scale: str = "minor") -> str:
        """Create a prompt instructions template for generating a rich chord progression in a key/scale.

        Args:
            key (str): The root key, e.g. "C" or "A#".
            scale (str): The scale quality, e.g. "major" or "minor".

        Returns:
            str: The creative instruction prompt text.
        """
        return (
            f"Create a soulful, professional 4-chord progression in the key of {key} {scale}.\n\n"
            f"Instructions:\n"
            f"1. Generate a progression such as i-VI-III-VII (or a classic jazz progression).\n"
            f"2. Use fl_add_chord_progression to insert the chords sequentially.\n"
            f"3. Make sure to specify the correct root pitches (e.g. {key}4 = 60 or translated MIDI values) and quality (e.g. 'minor', 'major', 'maj7', 'min7').\n"
            f"4. Space each chord 384 ticks apart (a whole note at default 96 PPQ) so they cover 4 full bars."
        )

    @mcp.prompt("humanize-pattern")
    def humanize_pattern(swing: float = 0.1) -> str:
        """Create a prompt instructions template for humanizing timing and velocity of the current pattern.

        Args:
            swing (float): Micro-timing swing shift factor (default 0.1).

        Returns:
            str: The creative instruction prompt text.
        """
        return (
            f"Enhance the current active pattern notes with realistic human groove and micro-timing adjustments using a swing factor of {swing}.\n\n"
            f"Instructions:\n"
            f"1. Retrieve the active pattern notes using fl_get_notes or query resource fl://pattern/notes.\n"
            f"2. For each note in the pattern:\n"
            f"   - Add slight velocity randomization (micro-dynamics) of +/- 10 velocity points.\n"
            f"   - Apply micro-timing shifts (timing offsets) proportional to swing={swing}.\n"
            f"3. Re-insert the adjusted notes into a new or active pattern using fl_insert_notes to commit the groove."
        )
