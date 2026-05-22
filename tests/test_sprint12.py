import pytest
import asyncio
from mcp.server.fastmcp import FastMCP
from fl_studio_mcp.server import mcp

@pytest.fixture
def mcp_server():
    return mcp

@pytest.mark.asyncio
async def test_performance_tools(mcp_server: FastMCP):
    res = await mcp_server.call_tool("fl_live_performance_mode", {"action": "trigger", "clip_id": "A1"})
    assert "Performance Mode Active" in str(res)
    assert "A1" in str(res)

@pytest.mark.asyncio
async def test_remix_tools(mcp_server: FastMCP):
    res = await mcp_server.call_tool("fl_stem_separation_remix", {"audio_file_path": "song.wav"})
    assert "song.wav" in str(res)
    assert "Stem Separation" in str(res)
    
    res = await mcp_server.call_tool("fl_foley_to_drumkit", {"foley_audio_path": "rain.wav"})
    assert "rain.wav" in str(res)
    assert "Slicex" in str(res)

@pytest.mark.asyncio
async def test_generative_vocals_tools(mcp_server: FastMCP):
    res = await mcp_server.call_tool("fl_vocal_synth_vocodex", {"vocal_track": 1, "synth_track": 2})
    assert "Vocodex" in str(res)
    assert "Track 1 routed as Modulator" in str(res)
    
    res = await mcp_server.call_tool("fl_lyric_to_vocal_take", {"lyrics": "Hello world", "key": "C", "scale": "Major"})
    assert "Hello world" in str(res)
    assert "C Major" in str(res)

@pytest.mark.asyncio
async def test_hardware_tools(mcp_server: FastMCP):
    res = await mcp_server.call_tool("fl_hardware_cv_gate_bridge", {"lfo_speed": 4.0, "target_audio_output": 3})
    assert "4.0 Hz" in str(res)
    assert "Output 3" in str(res)

@pytest.mark.asyncio
async def test_optimization_tools(mcp_server: FastMCP):
    res = await mcp_server.call_tool("fl_advanced_groove_extractor", {"reference_audio": "dilla.wav", "target_pattern": 5})
    assert "dilla.wav" in str(res)
    assert "Pattern 5" in str(res)
    
    res = await mcp_server.call_tool("fl_cpu_optimizer_bounce", {})
    assert "Bounced Track 5 in Place" in str(res)

@pytest.mark.asyncio
async def test_release_tools(mcp_server: FastMCP):
    res = await mcp_server.call_tool("fl_collaborative_cloud_sync", {"bucket_url": "s3://bucket"})
    assert "s3://bucket" in str(res)
    
    res = await mcp_server.call_tool("fl_industry_metadata_tagger", {"isrc_code": "US-123", "ascap_splits": "50/50"})
    assert "US-123" in str(res)
    assert "50/50" in str(res)
