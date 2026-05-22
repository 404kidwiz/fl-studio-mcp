import pytest
from mcp.server.fastmcp import FastMCP
from fl_studio_mcp.server import mcp

@pytest.fixture
def mcp_server():
    return mcp

@pytest.mark.asyncio
async def test_fl_neural_rhythm_quantizer(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_neural_rhythm_quantizer", {"audio_file_path": "groove.wav", "target_channel": "Drums", "groove_intensity": 0.85})
    assert "groove.wav" in str(result)
    assert "Drums" in str(result)
    assert "0.85" in str(result)

@pytest.mark.asyncio
async def test_fl_sub_bass_harmonic_synthesizer(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_sub_bass_harmonic_synthesizer", {"melody_channel": "Lead Synth", "target_synth_channel": "Sub Bass", "saturation_amount": 0.6})
    assert "Lead Synth" in str(result)
    assert "Sub Bass" in str(result)
    assert "0.6" in str(result)

@pytest.mark.asyncio
async def test_fl_dynamic_vocal_rider(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_dynamic_vocal_rider", {"vocal_mixer_track": 4, "instrumental_bus_track": 12, "target_db_range": 4.0})
    assert "Vocal Track 4" in str(result)
    assert "Instrumental Bus Track 12" in str(result)
    assert "4.0" in str(result)

@pytest.mark.asyncio
async def test_fl_intelligent_transient_splitter(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_intelligent_transient_splitter", {"source_mixer_track": 6, "transient_track": 7, "sustain_track": 8})
    assert "Source Track 6" in str(result)
    assert "Transient Track 7" in str(result)
    assert "Sustain Track 8" in str(result)

@pytest.mark.asyncio
async def test_fl_chord_progression_voicer(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_chord_progression_voicer", {"pattern_index": 5, "target_instrument": "Keys", "complexity_level": 0.7})
    assert "Pattern 5" in str(result)
    assert "Keys" in str(result)
    assert "0.7" in str(result)

@pytest.mark.asyncio
async def test_fl_multiband_stereo_widener_matrix(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_multiband_stereo_widener_matrix", {"target_mixer_track": 9, "low_cross_hz": 150.0, "high_cross_hz": 4000.0})
    assert "Track 9" in str(result)
    assert "150.0" in str(result)
    assert "4000.0" in str(result)

@pytest.mark.asyncio
async def test_fl_polyphonic_midi_to_audio_harmonizer(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_polyphonic_midi_to_audio_harmonizer", {"lead_vocal_track": 11, "chord_midi_pattern": 3, "harmony_type": "5-part"})
    assert "track 11" in str(result)
    assert "Pattern 3" in str(result)
    assert "5-part" in str(result)

@pytest.mark.asyncio
async def test_fl_resampler_glitch_generator(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_resampler_glitch_generator", {"start_bar": 9, "end_bar": 13, "density": 0.75})
    assert "Bar 9" in str(result)
    assert "13" in str(result)
    assert "0.75" in str(result)

@pytest.mark.asyncio
async def test_fl_intelligent_sidechain_carver(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_intelligent_sidechain_carver", {"kick_mixer_track": 2, "bass_mixer_track": 3, "frequency_hz": 90.0})
    assert "Bass Track 3" in str(result)
    assert "Kick Track 2" in str(result)
    assert "90.0" in str(result)

@pytest.mark.asyncio
async def test_fl_ai_track_sheet_generator(mcp_server: FastMCP):
    result = await mcp_server.call_tool("fl_ai_track_sheet_generator", {"project_name": "UltraHit", "format_style": "markdown"})
    assert "UltraHit" in str(result)
    assert "markdown" in str(result)
