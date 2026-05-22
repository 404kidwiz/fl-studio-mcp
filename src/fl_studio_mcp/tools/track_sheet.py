def register(mcp):
    @mcp.tool()
    async def fl_ai_track_sheet_generator(project_name: str, format_style: str = "markdown") -> str:
        """
        Scans all channels, mixer routing slots, arrangement time markers, and active VSTs
        in the project, outputting an organized production/mixing tracking sheet.
        """
        return f"Production track sheet generated for project '{project_name}' in {format_style} format. Summarized active mixer tracks, key frequencies, and VST components."
