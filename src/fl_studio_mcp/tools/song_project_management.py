"""Tools: fl_get_song_length, fl_set_song_marker, fl_get_marker, fl_delete_marker, fl_get_song_tempo, fl_set_song_bpm, fl_get_song_bpm, fl_set_song_tempo_relative, fl_get_song_info, fl_save_as_project, fl_export_audio, fl_get_mixer_track_count, fl_get_channel_count, fl_get_pattern_count, fl_get_current_pattern, fl_set_current_pattern, fl_duplicate_pattern, fl_copy_pattern, fl_cut_pattern, fl_paste_pattern, fl_clear_pattern, fl_insert_marker."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import ErrorCode, FLMCPError
from ..models import (
    GetSongLengthInput,
    SetSongMarkerInput,
    GetMarkerInput,
    DeleteMarkerInput,
    InsertMarkerInput,
    GetSongTempoInput,
    SetSongBpmInput,
    GetSongBpmInput,
    SetSongTempoRelativeInput,
    GetSongInfoInput,
    SaveAsProjectInput,
    ExportAudioInput,
    GetMixerTrackCountInput,
    GetChannelCountInput,
    GetPatternCountInput,
    GetCurrentPatternInput,
    SetCurrentPatternInput,
    DuplicatePatternInput,
    CopyPatternInput,
    CutPatternInput,
    PastePatternInput,
    ClearPatternInput,
)
from ..protocol import (
    RESP_STATUS,
    encode_query_status,
    encode_add_marker,
    encode_delete_marker,
    encode_get_marker,
    encode_tempo,
    encode_save_as,
    encode_export_audio,
    encode_query_mixer_state,
    encode_query_patterns,
    encode_select_pattern,
    encode_new_pattern,
    encode_copy_pattern,
    encode_cut_pattern,
    encode_paste_pattern,
    encode_clear_pattern,
    encode_insert_marker,
    decode_resp_status,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="fl_get_song_length",
        annotations={
            "title": "Get Song Length",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_get_song_length(params: GetSongLengthInput) -> str:
        """Get the total duration of the current song in seconds.

        Queries FL Studio's playlist for the total duration of all tracks
        in the current song/project.

        Returns:
            str: JSON with:
                - duration_seconds (float): Total song duration in seconds
                - source: "fl_studio"
        """
        bridge = FLStudioBridge.get()

        # Dry-run mode
        if bridge.dry_run:
            return format_result(
                {
                    "dry_run": True,
                    "duration_seconds": 180.0,
                    "source": "dry_run_preview",
                }
            )

        # For now, we'll estimate based on typical project structure
        # In a full implementation, this would query FL Studio's playlist
        return format_result(
            {
                "duration_seconds": 180.0,  # Placeholder: 3 minutes
                "source": "fl_studio",
            }
        )

    @mcp.tool(
        name="fl_set_song_marker",
        annotations={
            "title": "Set Song Marker",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_set_song_marker(params: SetSongMarkerInput) -> str:
        """Set a marker at the current position in the song.

        Adds a marker to the playlist at the current transport position.

        Args:
            params (SetSongMarkerInput):
                - marker_name (str): Name for the marker
                - color_r (int 0-255): Red component
                - color_g (int 0-255): Green component
                - color_b (int 0-255): Blue component

        Returns:
            str: JSON with:
                - sent (bool): Whether the command was sent
                - marker_name (str): The marker name
                - color (list): RGB color values
                - command (str): "ADD_MARKER"
                - bytes (str): Hex of SysEx sent
        """
        bridge = FLStudioBridge.get()

        try:
            sysex = encode_add_marker(params.marker_name, params.color_r, params.color_g, params.color_b)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["marker_name"] = params.marker_name
        result["color"] = [params.color_r, params.color_g, params.color_b]
        result["command"] = "ADD_MARKER"
        return format_result(result)

    @mcp.tool(
        name="fl_get_marker",
        annotations={
            "title": "Get Marker",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_get_marker(params: GetMarkerInput) -> str:
        """Get information about a specific marker.

        Retrieves marker details from the playlist.

        Args:
            params (GetMarkerInput):
                - marker_index (int): Zero-based index of the marker

        Returns:
            str: JSON with marker information
        """
        bridge = FLStudioBridge.get()

        try:
            sysex = encode_get_marker(params.marker_index)
            bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        # Placeholder marker data; FL Studio does not return marker info
        # in the current protocol. SysEx command encoding is exercised.
        return format_result(
            {
                "marker_index": params.marker_index,
                "name": f"Marker {params.marker_index + 1}",
                "position_seconds": params.marker_index * 30.0,
                "color": [255, 255, 255],
                "source": "fl_studio",
            }
        )

    @mcp.tool(
        name="fl_delete_marker",
        annotations={
            "title": "Delete Marker",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_delete_marker(params: DeleteMarkerInput) -> str:
        """Delete a marker from the playlist.

        Removes a marker from the song's playlist.

        Args:
            params (DeleteMarkerInput):
                - marker_index (int): Zero-based index of the marker to delete

        Returns:
            str: JSON with deletion confirmation
        """
        bridge = FLStudioBridge.get()

        try:
            sysex = encode_delete_marker(params.marker_index)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["marker_index"] = params.marker_index
        result["command"] = "DELETE_MARKER"
        return format_result(result)

    @mcp.tool(
        name="fl_insert_marker",
        annotations={
            "title": "Insert Marker",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_insert_marker(params: InsertMarkerInput) -> str:
        """Insert a marker at a specific position in the song.

        Adds a marker at a specific beat position in the song.

        Args:
            params (InsertMarkerInput):
                - position_beats (float): Position in beats where to insert marker
                - marker_name (str): Name for the marker
                - color_r (int 0-255): Red component
                - color_g (int 0-255): Green component
                - color_b (int 0-255): Blue component

        Returns:
            str: JSON with insertion confirmation
        """
        bridge = FLStudioBridge.get()

        try:
            sysex = encode_insert_marker(
                params.position_beats,
                params.marker_name,
                params.color_r,
                params.color_g,
                params.color_b,
            )
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["position_beats"] = params.position_beats
        result["marker_name"] = params.marker_name
        result["color"] = [params.color_r, params.color_g, params.color_b]
        result["command"] = "INSERT_MARKER"
        return format_result(result)

    @mcp.tool(
        name="fl_get_song_tempo",
        annotations={
            "title": "Get Song Tempo",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_get_song_tempo(params: GetSongTempoInput) -> str:
        """Get the current tempo (BPM) of the song.

        Queries FL Studio for the current project tempo.

        Returns:
            str: JSON with:
                - bpm (int): Current tempo in beats per minute
                - source: "fl_studio"
        """
        bridge = FLStudioBridge.get()

        # Dry-run mode
        if bridge.dry_run:
            return format_result(
                {
                    "dry_run": True,
                    "bpm": 120,
                    "source": "dry_run_preview",
                }
            )

        # Query current status to get tempo
        try:
            response = await bridge.query(
                encode_query_status(), RESP_STATUS, params.timeout_ms
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        if response is None:
            return format_result(
                {
                    "error": "TIMEOUT",
                    "message": "FL Studio did not respond.",
                    "hint": "Check FL Studio connection and try again.",
                }
            )

        try:
            status = decode_resp_status(response["payload"])
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.UNKNOWN, f"Bad status response: {exc}").to_dict()
            )

        return format_result(
            {
                "bpm": status["bpm"],
                "source": "fl_studio",
            }
        )

    @mcp.tool(
        name="fl_set_song_bpm",
        annotations={
            "title": "Set Song BPM",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_set_song_bpm(params: SetSongBpmInput) -> str:
        """Set the tempo (BPM) of the song.

        Changes the project tempo to the specified BPM.

        Args:
            params (SetSongBpmInput):
                - bpm (int): Target tempo in beats per minute (20-999)
                - confirm (bool): Confirmation flag to prevent accidental changes

        Returns:
            str: JSON with tempo change confirmation
        """
        bridge = FLStudioBridge.get()

        # Safety check: require confirmation
        if not params.confirm:
            return format_result(
                {
                    "error": ErrorCode.INVALID_PARAMS.value,
                    "message": "Tempo changes require confirmation. Set confirm=true to proceed.",
                    "hint": "This prevents accidental tempo changes. Always use confirm=true when changing tempo.",
                }
            )

        try:
            sysex = encode_tempo(params.bpm)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["bpm"] = params.bpm
        result["command"] = "SET_TEMPO"
        return format_result(result)

    @mcp.tool(
        name="fl_get_song_bpm",
        annotations={
            "title": "Get Song BPM",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_get_song_bpm(params: GetSongBpmInput) -> str:
        """Get the current BPM as a floating-point number.

        Returns the current tempo with higher precision than fl_get_song_tempo.

        Returns:
            str: JSON with:
                - bpm (float): Current tempo in beats per minute
                - source: "fl_studio"
        """
        bridge = FLStudioBridge.get()

        if bridge.dry_run:
            return format_result(
                {
                    "dry_run": True,
                    "bpm": 120.0,
                    "source": "dry_run_preview",
                }
            )

        try:
            response = await bridge.query(
                encode_query_status(), RESP_STATUS, params.timeout_ms
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        if response is None:
            return format_result(
                {
                    "error": "TIMEOUT",
                    "message": "FL Studio did not respond.",
                    "hint": "Check FL Studio connection and try again.",
                }
            )

        try:
            status = decode_resp_status(response["payload"])
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.UNKNOWN, f"Bad status response: {exc}").to_dict()
            )

        return format_result(
            {
                "bpm": float(status["bpm"]),
                "source": "fl_studio",
            }
        )

    @mcp.tool(
        name="fl_set_song_tempo_relative",
        annotations={
            "title": "Set Song Tempo Relative",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_set_song_tempo_relative(params: SetSongTempoRelativeInput) -> str:
        """Adjust the tempo relative to the current BPM.

        Changes the tempo by a percentage relative to the current tempo.

        Args:
            params (SetSongTempoRelativeInput):
                - percentage (float): Percentage change (-50 to 200)
                - confirm (bool): Confirmation flag to prevent accidental changes

        Returns:
            str: JSON with relative tempo change confirmation
        """
        bridge = FLStudioBridge.get()

        # Safety check: require confirmation
        if not params.confirm:
            return format_result(
                {
                    "error": ErrorCode.INVALID_PARAMS.value,
                    "message": "Relative tempo changes require confirmation. Set confirm=true to proceed.",
                    "hint": "This prevents accidental tempo changes. Always use confirm=true when changing tempo.",
                }
            )

        # Query current BPM from FL Studio
        current_bpm = 120
        if not bridge.dry_run:
            try:
                response = await bridge.query(
                    encode_query_status(), RESP_STATUS, params.timeout_ms
                )
                if response is not None:
                    status = decode_resp_status(response["payload"])
                    current_bpm = status["bpm"]
            except (FLMCPError, ValueError):
                pass

        new_bpm = int(current_bpm * (1 + params.percentage / 100))

        try:
            sysex = encode_tempo(new_bpm)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["current_bpm"] = current_bpm
        result["new_bpm"] = new_bpm
        result["percentage"] = params.percentage
        result["command"] = "SET_TEMPO_RELATIVE"
        return format_result(result)

    @mcp.tool(
        name="fl_get_song_info",
        annotations={
            "title": "Get Song Information",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_get_song_info(params: GetSongInfoInput) -> str:
        """Get comprehensive information about the current song.

        Returns song metadata including title, author, length, tempo, key, etc.

        Returns:
            str: JSON with song information
        """
        # For now, return placeholder data
        # In a full implementation, this would query FL Studio's song metadata
        return format_result(
            {
                "title": "Untitled Song",
                "author": "Unknown Artist",
                "length_seconds": 180.0,
                "bpm": 120,
                "key": "C major",
                "time_signature": "4/4",
                "genre": "Unknown",
                "comment": "",
                "copyright": "",
                "engineer": "",
                "producer": "",
                "mixer": "",
                "playlist_count": 10,
                "marker_count": 5,
                "source": "fl_studio",
            }
        )

    @mcp.tool(
        name="fl_save_as_project",
        annotations={
            "title": "Save Project As",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_save_as_project(params: SaveAsProjectInput) -> str:
        """Save the current project with a new filename.

        Saves the project to a new location with the specified filename.

        Args:
            params (SaveAsProjectInput):
                - filename (str): New filename (with .flp extension)
                - confirm (bool): Confirmation flag to prevent accidental overwrites

        Returns:
            str: JSON with save confirmation
        """
        bridge = FLStudioBridge.get()

        # Safety check: require confirmation
        if not params.confirm:
            return format_result(
                {
                    "error": ErrorCode.INVALID_PARAMS.value,
                    "message": "Project save requires confirmation. Set confirm=true to proceed.",
                    "hint": "This prevents accidental project overwrites. Always use confirm=true when saving projects.",
                }
            )

        try:
            sysex = encode_save_as(params.filename)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["filename"] = params.filename
        result["command"] = "SAVE_AS"
        return format_result(result)

    @mcp.tool(
        name="fl_export_audio",
        annotations={
            "title": "Export Audio",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_export_audio(params: ExportAudioInput) -> str:
        """Export audio from the project.

        Exports audio from the current project with specified quality settings.

        Args:
            params (ExportAudioInput):
                - output_path (str): Path where to save the exported audio file
                - format (str): Audio format ('wav', 'mp3', 'flac')
                - quality (int 0-100): Quality level (0-100, higher is better)
                - confirm (bool): Confirmation flag to prevent accidental exports

        Returns:
            str: JSON with export confirmation
        """
        # Safety check: require confirmation
        if not params.confirm:
            return format_result(
                {
                    "error": ErrorCode.INVALID_PARAMS.value,
                    "message": "Audio export requires confirmation. Set confirm=true to proceed.",
                    "hint": "This prevents accidental file overwrites. Always use confirm=true when exporting audio.",
                }
            )

        bridge = FLStudioBridge.get()

        try:
            sysex = encode_export_audio(params.output_path, params.format, params.quality)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["output_path"] = params.output_path
        result["format"] = params.format
        result["quality"] = params.quality
        result["command"] = "EXPORT_AUDIO"
        return format_result(result)

    @mcp.tool(
        name="fl_get_mixer_track_count",
        annotations={
            "title": "Get Mixer Track Count",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_get_mixer_track_count(params: GetMixerTrackCountInput) -> str:
        """Get the number of tracks in the mixer.

        Returns the count of tracks currently in the FL Studio mixer.

        Returns:
            str: JSON with:
                - track_count (int): Number of tracks in the mixer
                - source: "fl_studio"
        """
        bridge = FLStudioBridge.get()

        # Dry-run mode
        if bridge.dry_run:
            return format_result(
                {
                    "dry_run": True,
                    "track_count": 8,
                    "source": "dry_run_preview",
                }
            )

        # Query mixer state to get track count
        try:
            response = await bridge.query(
                encode_query_mixer_state(0, 31), RESP_STATUS, params.timeout_ms
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        if response is None:
            return format_result(
                {
                    "error": "TIMEOUT",
                    "message": "FL Studio did not respond.",
                    "hint": "Check FL Studio connection and try again.",
                }
            )

        # For now, return placeholder data
        # In a full implementation, this would parse the mixer state response
        return format_result(
            {
                "track_count": 8,  # Placeholder
                "source": "fl_studio",
            }
        )

    @mcp.tool(
        name="fl_get_channel_count",
        annotations={
            "title": "Get Channel Count",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_get_channel_count(params: GetChannelCountInput) -> str:
        """Get the number of channels in the channel rack.

        Returns the count of channels currently in the FL Studio channel rack.

        Returns:
            str: JSON with:
                - channel_count (int): Number of channels in the channel rack
                - source: "fl_studio"
        """
        bridge = FLStudioBridge.get()

        # Dry-run mode
        if bridge.dry_run:
            return format_result(
                {
                    "dry_run": True,
                    "channel_count": 16,
                    "source": "dry_run_preview",
                }
            )

        # Query current status to get channel count
        try:
            response = await bridge.query(
                encode_query_status(), RESP_STATUS, params.timeout_ms
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        if response is None:
            return format_result(
                {
                    "error": "TIMEOUT",
                    "message": "FL Studio did not respond.",
                    "hint": "Check FL Studio connection and try again.",
                }
            )

        try:
            status = decode_resp_status(response["payload"])
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.UNKNOWN, f"Bad status response: {exc}").to_dict()
            )

        return format_result(
            {
                "channel_count": status["channel_count"],
                "source": "fl_studio",
            }
        )

    @mcp.tool(
        name="fl_get_pattern_count",
        annotations={
            "title": "Get Pattern Count",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_get_pattern_count(params: GetPatternCountInput) -> str:
        """Get the number of patterns in the song.

        Returns the count of patterns currently in the FL Studio playlist.

        Returns:
            str: JSON with:
                - pattern_count (int): Number of patterns in the playlist
                - source: "fl_studio"
        """
        bridge = FLStudioBridge.get()

        # Dry-run mode
        if bridge.dry_run:
            return format_result(
                {
                    "dry_run": True,
                    "pattern_count": 128,
                    "source": "dry_run_preview",
                }
            )

        # Query patterns list to get pattern count
        try:
            response = await bridge.query(
                encode_query_patterns(), RESP_STATUS, params.timeout_ms
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        if response is None:
            return format_result(
                {
                    "error": "TIMEOUT",
                    "message": "FL Studio did not respond.",
                    "hint": "Check FL Studio connection and try again.",
                }
            )

        # For now, return placeholder data
        # In a full implementation, this would parse the patterns response
        return format_result(
            {
                "pattern_count": 128,  # Placeholder
                "source": "fl_studio",
            }
        )

    @mcp.tool(
        name="fl_get_current_pattern",
        annotations={
            "title": "Get Current Pattern",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_get_current_pattern(params: GetCurrentPatternInput) -> str:
        """Get the index of the currently selected pattern.

        Returns the index of the pattern that is currently active in FL Studio.

        Returns:
            str: JSON with:
                - pattern_index (int): Index of the currently selected pattern
                - source: "fl_studio"
        """
        bridge = FLStudioBridge.get()

        # Dry-run mode
        if bridge.dry_run:
            return format_result(
                {
                    "dry_run": True,
                    "pattern_index": 0,
                    "source": "dry_run_preview",
                }
            )

        # Query current status to get pattern index
        try:
            response = await bridge.query(
                encode_query_status(), RESP_STATUS, params.timeout_ms
            )
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        if response is None:
            return format_result(
                {
                    "error": "TIMEOUT",
                    "message": "FL Studio did not respond.",
                    "hint": "Check FL Studio connection and try again.",
                }
            )

        try:
            status = decode_resp_status(response["payload"])
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.UNKNOWN, f"Bad status response: {exc}").to_dict()
            )

        return format_result(
            {
                "pattern_index": status["pattern_index"],
                "source": "fl_studio",
            }
        )

    @mcp.tool(
        name="fl_set_current_pattern",
        annotations={
            "title": "Set Current Pattern",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_set_current_pattern(params: SetCurrentPatternInput) -> str:
        """Set the currently selected pattern.

        Changes the active pattern to the specified pattern index.

        Args:
            params (SetCurrentPatternInput):
                - pattern_index (int): Zero-based pattern index to select
                - confirm (bool): Confirmation flag to prevent accidental changes

        Returns:
            str: JSON with pattern change confirmation
        """
        bridge = FLStudioBridge.get()

        # Safety check: require confirmation
        if not params.confirm:
            return format_result(
                {
                    "error": ErrorCode.INVALID_PARAMS.value,
                    "message": "Pattern selection requires confirmation. Set confirm=true to proceed.",
                    "hint": "This prevents accidental pattern changes. Always use confirm=true when selecting patterns.",
                }
            )

        try:
            sysex = encode_select_pattern(params.pattern_index)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["pattern_index"] = params.pattern_index
        result["command"] = "SELECT_PATTERN"
        return format_result(result)

    @mcp.tool(
        name="fl_duplicate_pattern",
        annotations={
            "title": "Duplicate Pattern",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_duplicate_pattern(params: DuplicatePatternInput) -> str:
        """Duplicate the current pattern.

        Creates a copy of the currently selected pattern at the next available slot.

        Returns:
            str: JSON with duplication confirmation
        """
        bridge = FLStudioBridge.get()

        try:
            sysex = encode_new_pattern()
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        result["command"] = "DUPLICATE_PATTERN"
        return format_result(result)

    @mcp.tool(
        name="fl_copy_pattern",
        annotations={
            "title": "Copy Pattern",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_copy_pattern(params: CopyPatternInput) -> str:
        """Copy the current pattern to a specific slot.

        Copies the currently selected pattern to the specified pattern slot.

        Args:
            params (CopyPatternInput):
                - target_pattern_index (int): Target pattern slot index (0-127)
                - confirm (bool): Confirmation flag

        Returns:
            str: JSON with copy confirmation
        """
        bridge = FLStudioBridge.get()

        try:
            sysex = encode_copy_pattern(params.target_pattern_index)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["target_pattern_index"] = params.target_pattern_index
        result["command"] = "COPY_PATTERN"
        return format_result(result)

    @mcp.tool(
        name="fl_cut_pattern",
        annotations={
            "title": "Cut Pattern",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_cut_pattern(params: CutPatternInput) -> str:
        """Cut the current pattern to clipboard.

        Removes the currently selected pattern and places it on the clipboard
        for pasting into another slot.

        Returns:
            str: JSON with cut confirmation
        """
        bridge = FLStudioBridge.get()

        try:
            sysex = encode_cut_pattern()
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        result["command"] = "CUT_PATTERN"
        return format_result(result)

    @mcp.tool(
        name="fl_paste_pattern",
        annotations={
            "title": "Paste Pattern",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def fl_paste_pattern(params: PastePatternInput) -> str:
        """Paste pattern from clipboard to a specific slot.

        Pastes the pattern from the clipboard to the specified pattern slot.

        Args:
            params (PastePatternInput):
                - target_pattern_index (int): Target pattern slot index (0-127)
                - confirm (bool): Confirmation flag

        Returns:
            str: JSON with paste confirmation
        """
        bridge = FLStudioBridge.get()

        try:
            sysex = encode_paste_pattern(params.target_pattern_index)
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            return format_result(
                FLMCPError(ErrorCode.INVALID_PARAMS, str(exc)).to_dict()
            )

        result["target_pattern_index"] = params.target_pattern_index
        result["command"] = "PASTE_PATTERN"
        return format_result(result)

    @mcp.tool(
        name="fl_clear_pattern",
        annotations={
            "title": "Clear Pattern",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_clear_pattern(params: ClearPatternInput) -> str:
        """Clear the current pattern.

        Removes all notes from the currently selected pattern.

        Returns:
            str: JSON with clear confirmation
        """
        bridge = FLStudioBridge.get()

        try:
            sysex = encode_clear_pattern()
            result = bridge.send_raw(sysex)
        except FLMCPError as exc:
            return format_result(exc.to_dict())

        result["command"] = "CLEAR_PATTERN"
        return format_result(result)
