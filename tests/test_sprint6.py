"""Tests for Sprint 6: Song/Project Management Tools.

Includes protocol tests, MCP tool behaviors, and Click CLI commands for song/project management.
"""

import json
import pytest
import unittest.mock
from click.testing import CliRunner

from fl_studio_mcp.bridge import FLStudioBridge
from fl_studio_mcp.cli import main
from fl_studio_mcp.models import (
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
from fl_studio_mcp.protocol import (
    CMD_ADD_MARKER,
    CMD_DELETE_MARKER,
    CMD_GET_MARKER,
    CMD_SET_TEMPO_RELATIVE,
    CMD_GET_BPM,
    CMD_SAVE_AS,
    CMD_EXPORT_AUDIO,
    CMD_QUERY_MIXER_STATE,
    CMD_QUERY_CHANNELS,
    CMD_QUERY_PATTERNS,
    CMD_SELECT_PATTERN,
    CMD_NEW_PATTERN,
    CMD_DUPLICATE_PATTERN,
    CMD_COPY_PATTERN,
    CMD_CUT_PATTERN,
    CMD_PASTE_PATTERN,
    CMD_CLEAR_PATTERN,
    CMD_INSERT_MARKER,
    CMD_QUERY_STATUS,
    RESP_STATUS,
    encode_add_marker,
    encode_delete_marker,
    encode_get_marker,
    encode_tempo,
    encode_get_bpm,
    encode_set_tempo_relative,
    encode_save_as,
    encode_export_audio,
    encode_query_mixer_state,
    encode_query_channels,
    encode_query_patterns,
    encode_select_pattern,
    encode_new_pattern,
    encode_duplicate_pattern,
    encode_copy_pattern,
    encode_cut_pattern,
    encode_paste_pattern,
    encode_clear_pattern,
    encode_insert_marker,
    decode_sysex,
    decode_resp_status,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse(result: str) -> dict:
    return json.loads(result)


def _inject_response(bridge: FLStudioBridge, cmd: int, payload: list) -> None:
    bridge._response_queue.put_nowait({"cmd": cmd, "payload": payload})


def _tool(module_name: str, tool_name: str):
    from mcp.server.fastmcp import FastMCP

    if module_name == "connection":
        from fl_studio_mcp.tools import connection as mod
    else:
        from fl_studio_mcp.tools import song_project_management as mod
    _mcp = FastMCP("test")
    mod.register(_mcp)
    return {t.name: t for t in _mcp._tool_manager.list_tools()}[tool_name].fn


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# 1. Protocol Tests
# ---------------------------------------------------------------------------


class TestSongProjectProtocol:
    def test_encode_add_marker(self):
        raw = encode_add_marker("Intro", 255, 0, 128)
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x2B
        assert raw[3] == len("Intro")
        assert raw[4:9] == bytes([ord(c) for c in "Intro"])
        assert raw[9] == 0x0F  # r_hi
        assert raw[10] == 0x0F  # r_lo
        assert raw[11] == 0x00  # g_hi
        assert raw[12] == 0x00  # g_lo
        assert raw[13] == 0x08  # b_hi
        assert raw[14] == 0x00  # b_lo
        assert raw[-1] == 0xF7

    def test_encode_add_marker_bounds(self):
        with pytest.raises(ValueError):
            encode_add_marker("", 0, 0, 0)
        with pytest.raises(ValueError):
            encode_add_marker("A" * 129, 0, 0, 0)
        with pytest.raises(ValueError):
            encode_add_marker("Test", 256, 0, 0)
        with pytest.raises(ValueError):
            encode_add_marker("Test", -1, 0, 0)

    def test_encode_delete_marker(self):
        raw = encode_delete_marker(5)
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x2C
        assert raw[3] == 5
        assert raw[-1] == 0xF7

    def test_encode_delete_marker_bounds(self):
        with pytest.raises(ValueError):
            encode_delete_marker(-1)
        with pytest.raises(ValueError):
            encode_delete_marker(128)

    def test_encode_get_marker(self):
        raw = encode_get_marker(3)
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x2D
        assert raw[3] == 3
        assert raw[-1] == 0xF7

    def test_encode_get_marker_bounds(self):
        with pytest.raises(ValueError):
            encode_get_marker(-1)
        with pytest.raises(ValueError):
            encode_get_marker(128)

    def test_encode_insert_marker(self):
        raw = encode_insert_marker(120.5, "Verse 1", 255, 128, 0)
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x2E
        assert raw[3] == 0x5E  # pos_hi
        assert raw[4] == 0x12  # pos_lo
        assert raw[5] == len("Verse 1")
        assert raw[6:13] == bytes([ord(c) for c in "Verse 1"])
        assert raw[13] == 0x0F  # r_hi
        assert raw[14] == 0x0F  # r_lo
        assert raw[15] == 0x08  # g_hi
        assert raw[16] == 0x00  # g_lo
        assert raw[17] == 0x00  # b_hi
        assert raw[18] == 0x00  # b_lo
        assert raw[-1] == 0xF7

    def test_encode_insert_marker_bounds(self):
        with pytest.raises(ValueError):
            encode_insert_marker(-1.0, "Test", 0, 0, 0)
        with pytest.raises(ValueError):
            encode_insert_marker(999.0, "Test", 0, 0, 0)
        with pytest.raises(ValueError):
            encode_insert_marker(0.0, "", 0, 0, 0)
        with pytest.raises(ValueError):
            encode_insert_marker(0.0, "A" * 129, 0, 0, 0)

    def test_encode_tempo(self):
        raw = encode_tempo(120)
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x03
        assert raw[3] == 0
        assert raw[4] == 120
        assert raw[-1] == 0xF7

    def test_encode_tempo_bounds(self):
        with pytest.raises(ValueError):
            encode_tempo(-1)
        with pytest.raises(ValueError):
            encode_tempo(0)
        with pytest.raises(ValueError):
            encode_tempo(1000)

    def test_encode_get_bpm(self):
        raw = encode_get_bpm()
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x30
        assert raw[-1] == 0xF7

    def test_encode_set_tempo_relative(self):
        raw = encode_set_tempo_relative(20)
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x2F
        assert raw[3] == 20
        assert raw[-1] == 0xF7

    def test_encode_set_tempo_relative_bounds(self):
        with pytest.raises(ValueError):
            encode_set_tempo_relative(-51)
        with pytest.raises(ValueError):
            encode_set_tempo_relative(201)

    def test_encode_save_as(self):
        raw = encode_save_as("My Song.flp")
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x31
        assert raw[3] == len("My Song.flp")
        assert raw[4:4+len("My Song.flp")] == bytes([ord(c) for c in "My Song.flp"])
        assert raw[-1] == 0xF7

    def test_encode_save_as_bounds(self):
        with pytest.raises(ValueError):
            encode_save_as("")
        with pytest.raises(ValueError):
            encode_save_as("A" * 129)

    def test_encode_export_audio(self):
        path = "/path/to/song.wav"
        raw = encode_export_audio(path, "wav", 80)
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x32
        assert raw[3] == len(path)
        plen = raw[3]
        assert raw[4:4+plen] == bytes([ord(c) for c in path])
        assert raw[4+plen] == 0  # wav format code
        assert raw[4+plen+1] == 80
        assert raw[-1] == 0xF7

    def test_encode_export_audio_bounds(self):
        with pytest.raises(ValueError):
            encode_export_audio("", "wav", 80)
        with pytest.raises(ValueError):
            encode_export_audio("A" * 129, "wav", 80)
        with pytest.raises(ValueError):
            encode_export_audio("/path/to/song", "invalid", 80)
        with pytest.raises(ValueError):
            encode_export_audio("/path/to/song", "wav", -1)
        with pytest.raises(ValueError):
            encode_export_audio("/path/to/song", "wav", 101)

    def test_encode_query_mixer_state(self):
        raw = encode_query_mixer_state(0, 15)
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x1C
        assert raw[3] == 0
        assert raw[4] == 15
        assert raw[-1] == 0xF7

    def test_encode_query_mixer_state_bounds(self):
        with pytest.raises(ValueError):
            encode_query_mixer_state(-1, 15)
        with pytest.raises(ValueError):
            encode_query_mixer_state(0, 128)
        with pytest.raises(ValueError):
            encode_query_mixer_state(10, 5)
        with pytest.raises(ValueError):
            encode_query_mixer_state(0, 32)

    def test_encode_query_channels(self):
        raw = encode_query_channels()
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x07
        assert raw[-1] == 0xF7

    def test_encode_query_patterns(self):
        raw = encode_query_patterns()
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x0C
        assert raw[-1] == 0xF7

    def test_encode_select_pattern(self):
        raw = encode_select_pattern(5)
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x0A
        assert raw[3] == 5
        assert raw[-1] == 0xF7

    def test_encode_select_pattern_bounds(self):
        with pytest.raises(ValueError):
            encode_select_pattern(-1)
        with pytest.raises(ValueError):
            encode_select_pattern(128)

    def test_encode_new_pattern(self):
        raw = encode_new_pattern()
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x09
        assert raw[-1] == 0xF7

    def test_encode_duplicate_pattern(self):
        raw = encode_duplicate_pattern()
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x35
        assert raw[-1] == 0xF7

    def test_encode_copy_pattern(self):
        raw = encode_copy_pattern(7)
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x36
        assert raw[3] == 7
        assert raw[-1] == 0xF7

    def test_encode_copy_pattern_bounds(self):
        with pytest.raises(ValueError):
            encode_copy_pattern(-1)
        with pytest.raises(ValueError):
            encode_copy_pattern(128)

    def test_encode_cut_pattern(self):
        raw = encode_cut_pattern()
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x37
        assert raw[-1] == 0xF7

    def test_encode_paste_pattern(self):
        raw = encode_paste_pattern(10)
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x38
        assert raw[3] == 10
        assert raw[-1] == 0xF7

    def test_encode_paste_pattern_bounds(self):
        with pytest.raises(ValueError):
            encode_paste_pattern(-1)
        with pytest.raises(ValueError):
            encode_paste_pattern(128)

    def test_encode_clear_pattern(self):
        raw = encode_clear_pattern()
        assert raw[0] == 0xF0
        assert raw[1] == 0x7D
        assert raw[2] == 0x39
        assert raw[-1] == 0xF7


# ---------------------------------------------------------------------------
# 2. MCP Tool Tests
# ---------------------------------------------------------------------------


class TestSongProjectTools:
    async def test_fl_get_song_length_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_get_song_length")
        result = parse(await fn(GetSongLengthInput()))
        assert result["dry_run"] is True
        assert result["duration_seconds"] == 180.0
        assert result["source"] == "dry_run_preview"

    async def test_fl_get_song_length_live_success(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        def mock_send(msg):
            cmd, payload = decode_sysex(msg.bytes())
            if cmd == CMD_QUERY_STATUS:
                _inject_response(dry_bridge, RESP_STATUS, [1, 0, 120, 0, 16])

        dry_bridge._output_port.send = mock_send

        fn = _tool("song_project_management", "fl_get_song_length")
        result = parse(await fn(GetSongLengthInput(timeout_ms=500)))
        assert result["source"] == "fl_studio"
        assert "duration_seconds" in result

        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_set_song_marker_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_set_song_marker")
        result = parse(await fn(SetSongMarkerInput(marker_name="Intro", color_r=255, color_g=0, color_b=0)))
        # bridge.send_raw() in dry_run returns dry_run=True, would_send_bytes
        assert result["dry_run"] is True
        assert result["marker_name"] == "Intro"
        assert result["color"] == [255, 0, 0]
        assert result["command"] == "ADD_MARKER"
        assert "F0 7D 2B" in result["would_send_bytes"]

    async def test_fl_set_song_marker_live_success(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        def mock_send(msg):
            cmd, payload = decode_sysex(msg.bytes())
            if cmd == CMD_ADD_MARKER:
                _inject_response(dry_bridge, 0x1F, [CMD_ADD_MARKER])

        dry_bridge._output_port.send = mock_send

        fn = _tool("song_project_management", "fl_set_song_marker")
        result = parse(await fn(SetSongMarkerInput(marker_name="Intro", color_r=255, color_g=0, color_b=0, confirm=True, timeout_ms=500)))
        assert result["sent"] is True
        assert result["marker_name"] == "Intro"
        assert result["color"] == [255, 0, 0]
        assert result["command"] == "ADD_MARKER"

        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_get_marker_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_get_marker")
        result = parse(await fn(GetMarkerInput(marker_index=2)))
        assert result["marker_index"] == 2
        assert result["name"] == "Marker 3"
        assert result["position_seconds"] == 60.0
        assert result["color"] == [255, 255, 255]
        assert result["source"] == "fl_studio"

    async def test_fl_delete_marker_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_delete_marker")
        result = parse(await fn(DeleteMarkerInput(marker_index=3)))
        # bridge.send_raw() in dry_run returns dry_run=True, would_send_bytes
        assert result["dry_run"] is True
        assert result["marker_index"] == 3
        assert result["command"] == "DELETE_MARKER"
        assert "F0 7D 2C 03 F7" in result["would_send_bytes"]

    async def test_fl_insert_marker_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_insert_marker")
        result = parse(await fn(InsertMarkerInput(position_beats=120.5, marker_name="Verse 1", color_r=255, color_g=128, color_b=0)))
        assert result["dry_run"] is True
        assert result["position_beats"] == 120.5
        assert result["marker_name"] == "Verse 1"
        assert result["color"] == [255, 128, 0]
        assert result["command"] == "INSERT_MARKER"
        assert "F0 7D 2E" in result["would_send_bytes"]

    async def test_fl_insert_marker_live_success(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        def mock_send(msg):
            cmd, payload = decode_sysex(msg.bytes())
            if cmd == CMD_INSERT_MARKER:
                _inject_response(dry_bridge, 0x1F, [CMD_INSERT_MARKER])

        dry_bridge._output_port.send = mock_send

        fn = _tool("song_project_management", "fl_insert_marker")
        result = parse(await fn(InsertMarkerInput(position_beats=120.5, marker_name="Verse 1", color_r=255, color_g=128, color_b=0)))
        assert result["sent"] is True
        assert result["position_beats"] == 120.5
        assert result["marker_name"] == "Verse 1"
        assert result["color"] == [255, 128, 0]
        assert result["command"] == "INSERT_MARKER"

        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_get_song_tempo_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_get_song_tempo")
        result = parse(await fn(GetSongTempoInput()))
        assert result["dry_run"] is True
        assert result["bpm"] == 120
        assert result["source"] == "dry_run_preview"

    async def test_fl_get_song_tempo_live_success(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        def mock_send(msg):
            cmd, payload = decode_sysex(msg.bytes())
            if cmd == CMD_QUERY_STATUS:
                _inject_response(dry_bridge, RESP_STATUS, [1, 0, 140, 0, 16])

        dry_bridge._output_port.send = mock_send

        fn = _tool("song_project_management", "fl_get_song_tempo")
        result = parse(await fn(GetSongTempoInput(timeout_ms=500)))
        assert result["bpm"] == 140
        assert result["source"] == "fl_studio"

        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_set_song_bpm_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_set_song_bpm")
        result = parse(await fn(SetSongBpmInput(bpm=130, confirm=True)))
        # bridge.send_raw() in dry_run returns dry_run=True, would_send_bytes
        assert result["dry_run"] is True
        assert result["bpm"] == 130
        assert result["command"] == "SET_TEMPO"
        assert "F0 7D 03" in result["would_send_bytes"]

    async def test_fl_set_song_bpm_requires_confirmation(self, dry_bridge):
        fn = _tool("song_project_management", "fl_set_song_bpm")
        result = parse(await fn(SetSongBpmInput(bpm=130, confirm=False)))
        assert result["error"] == "INVALID_PARAMS"

    async def test_fl_get_song_bpm_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_get_song_bpm")
        result = parse(await fn(GetSongBpmInput()))
        assert result["dry_run"] is True
        assert result["bpm"] == 120.0
        assert result["source"] == "dry_run_preview"

    async def test_fl_get_song_bpm_live_success(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        def mock_send(msg):
            cmd, payload = decode_sysex(msg.bytes())
            if cmd == CMD_QUERY_STATUS:
                _inject_response(dry_bridge, RESP_STATUS, [1, 0, 140, 0, 16])

        dry_bridge._output_port.send = mock_send

        fn = _tool("song_project_management", "fl_get_song_bpm")
        result = parse(await fn(GetSongBpmInput(timeout_ms=500)))
        assert result["bpm"] == 140.0
        assert result["source"] == "fl_studio"

        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_set_song_tempo_relative_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_set_song_tempo_relative")
        result = parse(await fn(SetSongTempoRelativeInput(percentage=20, confirm=True)))
        # bridge.send_raw() in dry_run returns dry_run=True, would_send_bytes
        assert result["dry_run"] is True
        assert result["current_bpm"] == 120
        assert result["new_bpm"] == 144
        assert result["percentage"] == 20
        assert result["command"] == "SET_TEMPO_RELATIVE"

    async def test_fl_set_song_tempo_relative_requires_confirmation(self, dry_bridge):
        fn = _tool("song_project_management", "fl_set_song_tempo_relative")
        result = parse(await fn(SetSongTempoRelativeInput(percentage=20, confirm=False)))
        assert result["error"] == "INVALID_PARAMS"

    async def test_fl_get_song_info_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_get_song_info")
        result = parse(await fn(GetSongInfoInput()))
        assert result["title"] == "Untitled Song"
        assert result["author"] == "Unknown Artist"
        assert result["bpm"] == 120
        assert result["source"] == "fl_studio"

    async def test_fl_save_as_project_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_save_as_project")
        result = parse(await fn(SaveAsProjectInput(filename="My Song.flp", confirm=True)))
        # bridge.send_raw() in dry_run returns dry_run=True, would_send_bytes
        assert result["dry_run"] is True
        assert result["filename"] == "My Song.flp"
        assert result["command"] == "SAVE_AS"
        assert "F0 7D 31" in result["would_send_bytes"]

    async def test_fl_save_as_project_requires_confirmation(self, dry_bridge):
        fn = _tool("song_project_management", "fl_save_as_project")
        result = parse(await fn(SaveAsProjectInput(filename="My Song.flp", confirm=False)))
        assert result["error"] == "INVALID_PARAMS"

    async def test_fl_export_audio_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_export_audio")
        result = parse(await fn(ExportAudioInput(output_path="/path/to/song.wav", format="wav", quality=80, confirm=True)))
        assert result["dry_run"] is True
        assert result["output_path"] == "/path/to/song.wav"
        assert result["format"] == "wav"
        assert result["quality"] == 80
        assert result["command"] == "EXPORT_AUDIO"
        assert "F0 7D 32" in result["would_send_bytes"]

    async def test_fl_export_audio_live_success(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        def mock_send(msg):
            cmd, payload = decode_sysex(msg.bytes())
            if cmd == CMD_EXPORT_AUDIO:
                _inject_response(dry_bridge, 0x1F, [CMD_EXPORT_AUDIO])

        dry_bridge._output_port.send = mock_send

        fn = _tool("song_project_management", "fl_export_audio")
        result = parse(await fn(ExportAudioInput(output_path="/path/to/song.wav", format="wav", quality=80, confirm=True)))
        assert result["sent"] is True
        assert result["output_path"] == "/path/to/song.wav"
        assert result["format"] == "wav"
        assert result["quality"] == 80
        assert result["command"] == "EXPORT_AUDIO"

        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_export_audio_requires_confirmation(self, dry_bridge):
        fn = _tool("song_project_management", "fl_export_audio")
        result = parse(await fn(ExportAudioInput(output_path="/path/to/song.wav", format="wav", quality=80, confirm=False)))
        assert result["error"] == "INVALID_PARAMS"

    async def test_fl_get_mixer_track_count_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_get_mixer_track_count")
        result = parse(await fn(GetMixerTrackCountInput()))
        assert result["dry_run"] is True
        assert result["track_count"] == 8
        assert result["source"] == "dry_run_preview"

    async def test_fl_get_channel_count_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_get_channel_count")
        result = parse(await fn(GetChannelCountInput()))
        assert result["dry_run"] is True
        assert result["channel_count"] == 16

    async def test_fl_get_pattern_count_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_get_pattern_count")
        result = parse(await fn(GetPatternCountInput()))
        assert result["dry_run"] is True
        assert result["pattern_count"] == 128

    async def test_fl_get_current_pattern_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_get_current_pattern")
        result = parse(await fn(GetCurrentPatternInput()))
        assert result["dry_run"] is True
        assert result["pattern_index"] == 0

    async def test_fl_set_current_pattern_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_set_current_pattern")
        result = parse(await fn(SetCurrentPatternInput(pattern_index=5, confirm=True)))
        # bridge.send_raw() in dry_run returns dry_run=True, would_send_bytes
        assert result["dry_run"] is True
        assert result["pattern_index"] == 5
        assert result["command"] == "SELECT_PATTERN"
        assert "F0 7D 0A 05 F7" in result["would_send_bytes"]

    async def test_fl_set_current_pattern_requires_confirmation(self, dry_bridge):
        fn = _tool("song_project_management", "fl_set_current_pattern")
        result = parse(await fn(SetCurrentPatternInput(pattern_index=5, confirm=False)))
        assert result["error"] == "INVALID_PARAMS"

    async def test_fl_duplicate_pattern_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_duplicate_pattern")
        result = parse(await fn(DuplicatePatternInput()))
        assert result["dry_run"] is True
        assert result["command"] == "DUPLICATE_PATTERN"
        assert "F0 7D 09 F7" in result["would_send_bytes"]

    async def test_fl_copy_pattern_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_copy_pattern")
        result = parse(await fn(CopyPatternInput(target_pattern_index=10)))
        assert result["dry_run"] is True
        assert result["target_pattern_index"] == 10
        assert result["command"] == "COPY_PATTERN"
        assert "F0 7D 36 0A F7" in result["would_send_bytes"]

    async def test_fl_copy_pattern_live_success(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        def mock_send(msg):
            cmd, payload = decode_sysex(msg.bytes())
            if cmd == CMD_COPY_PATTERN:
                _inject_response(dry_bridge, 0x1F, [CMD_COPY_PATTERN])

        dry_bridge._output_port.send = mock_send

        fn = _tool("song_project_management", "fl_copy_pattern")
        result = parse(await fn(CopyPatternInput(target_pattern_index=10)))
        assert result["sent"] is True
        assert result["target_pattern_index"] == 10
        assert result["command"] == "COPY_PATTERN"

        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_cut_pattern_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_cut_pattern")
        result = parse(await fn(CutPatternInput()))
        assert result["dry_run"] is True
        assert result["command"] == "CUT_PATTERN"
        assert "F0 7D 37 F7" in result["would_send_bytes"]

    async def test_fl_cut_pattern_live_success(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        def mock_send(msg):
            cmd, payload = decode_sysex(msg.bytes())
            if cmd == CMD_CUT_PATTERN:
                _inject_response(dry_bridge, 0x1F, [CMD_CUT_PATTERN])

        dry_bridge._output_port.send = mock_send

        fn = _tool("song_project_management", "fl_cut_pattern")
        result = parse(await fn(CutPatternInput()))
        assert result["sent"] is True
        assert result["command"] == "CUT_PATTERN"

        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_paste_pattern_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_paste_pattern")
        result = parse(await fn(PastePatternInput(target_pattern_index=7)))
        assert result["dry_run"] is True
        assert result["target_pattern_index"] == 7
        assert result["command"] == "PASTE_PATTERN"
        assert "F0 7D 38 07 F7" in result["would_send_bytes"]

    async def test_fl_paste_pattern_live_success(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        def mock_send(msg):
            cmd, payload = decode_sysex(msg.bytes())
            if cmd == CMD_PASTE_PATTERN:
                _inject_response(dry_bridge, 0x1F, [CMD_PASTE_PATTERN])

        dry_bridge._output_port.send = mock_send

        fn = _tool("song_project_management", "fl_paste_pattern")
        result = parse(await fn(PastePatternInput(target_pattern_index=7, confirm=True)))
        assert result["sent"] is True
        assert result["target_pattern_index"] == 7
        assert result["command"] == "PASTE_PATTERN"

        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None

    async def test_fl_clear_pattern_dry_run(self, dry_bridge):
        fn = _tool("song_project_management", "fl_clear_pattern")
        result = parse(await fn(ClearPatternInput()))
        assert result["dry_run"] is True
        assert result["command"] == "CLEAR_PATTERN"
        assert "F0 7D 39 F7" in result["would_send_bytes"]

    async def test_fl_clear_pattern_live_success(self, dry_bridge):
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        def mock_send(msg):
            cmd, payload = decode_sysex(msg.bytes())
            if cmd == CMD_CLEAR_PATTERN:
                _inject_response(dry_bridge, 0x1F, [CMD_CLEAR_PATTERN])

        dry_bridge._output_port.send = mock_send

        fn = _tool("song_project_management", "fl_clear_pattern")
        result = parse(await fn(ClearPatternInput()))
        assert result["sent"] is True
        assert result["command"] == "CLEAR_PATTERN"

        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None


# ---------------------------------------------------------------------------
# 3. Error Injection Tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test graceful failure when bridge is disconnected or encoding fails."""

    async def test_tool_without_connected_bridge_returns_error(self, dry_bridge):
        """No bridge connected → FLMCPError with DISCONNECTED error code."""
        dry_bridge._dry_run = False
        dry_bridge._connected = False

        fn = _tool("song_project_management", "fl_set_song_marker")
        result = parse(await fn(SetSongMarkerInput(marker_name="Test", color_r=255, color_g=0, color_b=0)))
        assert "error" in result

        dry_bridge._connected = True
        dry_bridge._dry_run = True

    async def test_send_raw_disconnected_returns_error(self, dry_bridge):
        """send_raw when not connected returns error dict, not exception."""
        dry_bridge._dry_run = False
        dry_bridge._connected = False

        fn = _tool("song_project_management", "fl_delete_marker")
        result = parse(await fn(DeleteMarkerInput(marker_index=3)))
        assert "error" in result

        dry_bridge._connected = True
        dry_bridge._dry_run = True

    async def test_invalid_pattern_index_returns_error(self, dry_bridge):
        """Copy/cut/paste with out-of-range index returns validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CopyPatternInput(target_pattern_index=-1)
        with pytest.raises(ValidationError):
            CopyPatternInput(target_pattern_index=128)

        # Valid index but negative in paste → Pydantic rejects
        with pytest.raises(ValidationError):
            PastePatternInput(target_pattern_index=-1)
        with pytest.raises(ValidationError):
            PastePatternInput(target_pattern_index=128)

    async def test_query_timeout_returns_timeout_error(self, dry_bridge):
        """When query times out (no response injected), return TIMEOUT error."""
        dry_bridge._dry_run = False
        dry_bridge._input_port = unittest.mock.Mock()
        dry_bridge._output_port = unittest.mock.Mock()

        fn = _tool("song_project_management", "fl_get_song_tempo")
        result = parse(await fn(GetSongTempoInput(timeout_ms=100)))
        assert result["error"] == "TIMEOUT"

        dry_bridge._dry_run = True
        dry_bridge._input_port = None
        dry_bridge._output_port = None


# ---------------------------------------------------------------------------
# 4. CLI Command Tests
# ---------------------------------------------------------------------------


class TestSongProjectCLI:
    def test_cli_help_shows_all_commands(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        for cmd in [
            "get-song-length", "set-song-marker", "get-marker", "delete-marker",
            "insert-marker", "get-song-tempo", "set-song-bpm", "get-song-bpm",
            "set-song-tempo-relative", "get-song-info", "save-as-project",
            "export-audio", "get-mixer-track-count", "get-channel-count",
            "get-pattern-count", "get-current-pattern", "set-current-pattern",
            "duplicate-pattern", "copy-pattern", "cut-pattern", "paste-pattern",
            "clear-pattern", "connect", "disconnect", "status",
        ]:
            assert cmd in result.output, f"Missing command: {cmd}"

    def test_cli_get_song_length_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["get-song-length"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["duration_seconds"] == 180.0

    def test_cli_set_song_marker_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["set-song-marker", "--marker-name", "Intro", "--color-r", "255", "--color-g", "0", "--color-b", "0"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["marker_name"] == "Intro"

    def test_cli_get_marker_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["get-marker", "--marker-index", "2"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["marker_index"] == 2
        assert data["name"] == "Marker 3"

    def test_cli_delete_marker_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["delete-marker", "--marker-index", "3"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["marker_index"] == 3

    def test_cli_insert_marker_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["insert-marker", "--position-beats", "120.5", "--marker-name", "Verse 1", "--color-r", "255", "--color-g", "128", "--color-b", "0"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["position_beats"] == 120.5
        assert data["marker_name"] == "Verse 1"

    def test_cli_get_song_tempo_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["get-song-tempo"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["bpm"] == 120

    def test_cli_set_song_bpm_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["set-song-bpm", "--bpm", "130", "--confirm"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["bpm"] == 130

    def test_cli_set_song_bpm_requires_confirmation(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["set-song-bpm", "--bpm", "130"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["error"] == "INVALID_PARAMS"

    def test_cli_get_song_bpm_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["get-song-bpm"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["bpm"] == 120.0

    def test_cli_set_song_tempo_relative_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["set-song-tempo-relative", "--percentage", "20", "--confirm"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["current_bpm"] == 120
        assert data["new_bpm"] == 144
        assert data["percentage"] == 20

    def test_cli_set_song_tempo_relative_requires_confirmation(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["set-song-tempo-relative", "--percentage", "20"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["error"] == "INVALID_PARAMS"

    def test_cli_get_song_info_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["get-song-info"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["title"] == "Untitled Song"
        assert data["author"] == "Unknown Artist"

    def test_cli_save_as_project_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["save-as-project", "--filename", "My Song.flp", "--confirm"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["filename"] == "My Song.flp"

    def test_cli_save_as_project_requires_confirmation(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["save-as-project", "--filename", "My Song.flp"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["error"] == "INVALID_PARAMS"

    def test_cli_export_audio_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["export-audio", "--output-path", "/path/to/song.wav", "--format", "wav", "--quality", "80", "--confirm"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["output_path"] == "/path/to/song.wav"
        assert data["format"] == "wav"
        assert data["quality"] == 80

    def test_cli_export_audio_requires_confirmation(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["export-audio", "--output-path", "/path/to/song.wav", "--format", "wav", "--quality", "80"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["error"] == "INVALID_PARAMS"

    def test_cli_get_mixer_track_count_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["get-mixer-track-count"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["track_count"] == 8

    def test_cli_get_channel_count_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["get-channel-count"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["channel_count"] == 16

    def test_cli_get_pattern_count_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["get-pattern-count"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["pattern_count"] == 128

    def test_cli_get_current_pattern_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["get-current-pattern"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["pattern_index"] == 0

    def test_cli_set_current_pattern_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["set-current-pattern", "--pattern-index", "5", "--confirm"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True
        assert data["pattern_index"] == 5

    def test_cli_set_current_pattern_requires_confirmation(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["set-current-pattern", "--pattern-index", "5"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["error"] == "INVALID_PARAMS"

    def test_cli_duplicate_pattern_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["duplicate-pattern"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["dry_run"] is True

    def test_cli_copy_pattern_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["copy-pattern", "--target-pattern-index", "10"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["target_pattern_index"] == 10

    def test_cli_cut_pattern_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["cut-pattern"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["command"] == "CUT_PATTERN"

    def test_cli_paste_pattern_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["paste-pattern", "--target-pattern-index", "7"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["target_pattern_index"] == 7

    def test_cli_clear_pattern_dry_run(self, mock_home):
        runner = CliRunner()
        runner.invoke(main, ["connect", "--port", "Test Port", "--dry-run"])
        result = runner.invoke(main, ["clear-pattern"])
        assert result.exit_code == 0
        data = parse(result.output)
        assert data["command"] == "CLEAR_PATTERN"