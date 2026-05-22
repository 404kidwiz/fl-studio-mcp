import pytest
import asyncio
from mcp.server.fastmcp import FastMCP
from fl_studio_mcp.server import mcp

@pytest.fixture
def mcp_server():
    return mcp

@pytest.mark.asyncio
async def test_phase14_tools(mcp_server: FastMCP):
    # 1. arrangement_builder
    res = await mcp_server.call_tool("fl_macro_arrangement_builder", {"structure": "Intro 8"})
    assert "Intro 8" in str(res)
    assert "Time Markers" in str(res)
    
    # 2. vocal_chops
    res = await mcp_server.call_tool("fl_vocal_chop_kaleidoscope", {"vocal_file": "vox.wav", "key": "D Minor"})
    assert "vox.wav" in str(res)
    assert "D Minor" in str(res)

    # 3. audio_extraction
    res = await mcp_server.call_tool("fl_polyphonic_bass_extractor", {"audio_loop": "loop.wav"})
    assert "loop.wav" in str(res)
    assert "lowpass" in str(res)

    # 4. gain_staging
    res = await mcp_server.call_tool("fl_auto_gain_staging_assistant", {})
    assert "Pink Noise contour" in str(res)

    # 5. euclidean_drums
    res = await mcp_server.call_tool("fl_drum_pattern_euclidean", {"hits": 5, "steps": 16})
    assert "5 hits" in str(res)
    assert "16 steps" in str(res)

    # 6. routing_wizard
    res = await mcp_server.call_tool("fl_sidechain_matrix_wizard", {})
    assert "Ghost Kick" in str(res)

    # 7. transition_fx
    res = await mcp_server.call_tool("fl_generative_transition_fx", {"bar_target": 17})
    assert "Bar 17" in str(res)
    assert "white noise riser" in str(res)

    # 8. hardware_midi
    res = await mcp_server.call_tool("fl_hardware_synth_patch_dumper", {"midi_port": 1, "synth_name": "Moog"})
    assert "Port 1" in str(res)
    assert "Moog" in str(res)

    # 9. latency
    res = await mcp_server.call_tool("fl_plugin_latency_compensator", {})
    assert "PDC" in str(res)
    assert "Phase smearing resolved" in str(res)

    # 10. custom_ui
    res = await mcp_server.call_tool("fl_holographic_mixer_ui", {})
    assert "10 most-automated parameters" in str(res)
