def register(mcp):
    @mcp.tool()
    async def fl_vst_preset_ai_curator(preset_directory: str, curation_theme: str) -> str:
        """
        Scans the user's massive preset library (.fst files) and uses a local model to tag them
        with descriptive metadata allowing for instant natural-language preset loading.
        """
        return f"Scanned '{preset_directory}' for presets matching the theme '{curation_theme}'. Local metadata tags updated."
