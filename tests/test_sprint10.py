import pytest
import asyncio
from mcp.server.fastmcp import FastMCP
from fl_studio_mcp.server import mcp

@pytest.fixture
def mcp_server():
    return mcp

@pytest.mark.asyncio
async def test_mastering_tools(mcp_server: FastMCP):
    res = await mcp_server.call_tool("fl_auto_master", {"target_lufs": -12.0})
    assert "Mastering applied" in str(res)
    assert "-12.0 LUFS" in str(res)

    res = await mcp_server.call_tool("fl_eq_reference_match", {"reference_audio_path": "/path/to/ref.wav"})
    assert "Reference track loaded" in str(res)
    assert "/path/to/ref.wav" in str(res)

@pytest.mark.asyncio
async def test_creative_fx_tools(mcp_server: FastMCP):
    res = await mcp_server.call_tool("fl_gross_beat_automator", {"effect_type": "tape-stop", "bars_interval": 4})
    assert "Gross Beat inserted" in str(res)
    assert "tape-stop" in str(res)
    assert "4 bars" in str(res)

    res = await mcp_server.call_tool("fl_auto_glitch_chops", {"target_track": 2})
    assert "Playlist Track 2" in str(res)
    assert "stutter fills" in str(res)

@pytest.mark.asyncio
async def test_audio_ai_tools(mcp_server: FastMCP):
    res = await mcp_server.call_tool("fl_audio_to_midi", {"audio_path": "vocal.wav", "target_pattern": 5, "target_channel": 1})
    assert "Analyzed pitch data" in str(res)
    assert "Pattern 5" in str(res)

    res = await mcp_server.call_tool("fl_generate_counter_melody", {"reference_pattern": 3, "target_pattern": 4, "key": "D", "scale": "Major"})
    assert "Pattern 3 (D Major)" in str(res)
    assert "Pattern 4" in str(res)

@pytest.mark.asyncio
async def test_workflow_advanced_tools(mcp_server: FastMCP):
    res = await mcp_server.call_tool("fl_build_patcher_instrument", {"preset_name": "SuperBass", "components": ["Serum", "Fruity EQ 2", "CamelCrusher"]})
    assert "SuperBass" in str(res)
    assert "Serum, Fruity EQ 2, CamelCrusher" in str(res)
