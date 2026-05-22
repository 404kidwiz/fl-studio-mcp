import pytest
from mcp.server.fastmcp import FastMCP
from fl_studio_mcp.server import mcp

@pytest.fixture
def mcp_server():
    return mcp

@pytest.mark.asyncio
async def test_fl_podcast_auto_editor(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_podcast_auto_editor", {"target_mixer_tracks": [1, 2], "noise_floor_db": -50.0, "ducking_ratio": 3.0})
    assert "Podcast auto-edited for 2 tracks" in str(result)
    assert "-50.0dB" in str(result)
    assert "3.0:1" in str(result)

@pytest.mark.asyncio
async def test_fl_spectral_morphing_engine(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_spectral_morphing_engine", {"source_a_path": "cello.wav", "source_b_path": "saw.wav", "morph_ratio": 0.6})
    assert "cello.wav" in str(result)
    assert "saw.wav" in str(result)
    assert "0.6" in str(result)

@pytest.mark.asyncio
async def test_fl_automated_remix_contest_parser(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_automated_remix_contest_parser", {"zip_file_path": "contest.zip", "target_playlist_track_start": 5})
    assert "contest.zip" in str(result)
    assert "track 5" in str(result)

@pytest.mark.asyncio
async def test_fl_polyphonic_aftertouch_generator(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_polyphonic_aftertouch_generator", {"target_channel": "Serum", "chord_progression_pattern": 2, "complexity": 0.9})
    assert "Serum" in str(result)
    assert "Pattern 2" in str(result)
    assert "0.9" in str(result)

@pytest.mark.asyncio
async def test_fl_orchestral_articulation_mapper(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_orchestral_articulation_mapper", {"target_channel": "Kontakt Violins", "phrase_pattern": 3})
    assert "Kontakt Violins" in str(result)
    assert "Pattern 3" in str(result)

@pytest.mark.asyncio
async def test_fl_generative_lyric_video_sync(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_generative_lyric_video_sync", {"lyrics_text_file": "lyrics.txt", "vocal_mixer_track": 10, "visualizer_preset": "Cyber"})
    assert "ZGameEditor" in str(result)
    assert "Cyber" in str(result)
    assert "Track 10" in str(result)

@pytest.mark.asyncio
async def test_fl_master_bus_clipper_optimizer(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_master_bus_clipper_optimizer", {"target_lufs": -8.0, "detection_sensitivity": 0.9})
    assert "-8.0 LUFS" in str(result)
    assert "0.9" in str(result)

@pytest.mark.asyncio
async def test_fl_lofi_degradation_matrix(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_lofi_degradation_matrix", {"target_mixer_track": 5, "wow_flutter_amount": 0.5, "crackle_level": 0.3})
    assert "Track 5" in str(result)
    assert "Wow/Flutter: 0.5" in str(result)
    assert "Crackle: 0.3" in str(result)

@pytest.mark.asyncio
async def test_fl_song_structure_mutator(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_song_structure_mutator", {"entropy_level": 0.8, "slice_resolution": "1/2 beat"})
    assert "entropy 0.8" in str(result)
    assert "1/2 beat" in str(result)

@pytest.mark.asyncio
async def test_fl_vst_preset_ai_curator(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_vst_preset_ai_curator", {"preset_directory": "/Presets/Serum", "curation_theme": "Cyberpunk"})
    assert "/Presets/Serum" in str(result)
    assert "Cyberpunk" in str(result)
