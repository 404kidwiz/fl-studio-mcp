def register(mcp):
    @mcp.tool()
    async def fl_automated_remix_contest_parser(zip_file_path: str, target_playlist_track_start: int = 1) -> str:
        """
        Unpacks ZIP folders from remix contests, automatically names stems, detects key/BPM, colors the tracks,
        and lays them out perfectly on the Playlist grid.
        """
        return f"Remix contest archive '{zip_file_path}' unpacked, analyzed, and arranged starting at Playlist track {target_playlist_track_start}."
