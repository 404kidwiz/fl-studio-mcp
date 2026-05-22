import pytest
import asyncio
from mcp.server.fastmcp import FastMCP
from fl_studio_mcp.server import mcp

@pytest.fixture
def mcp_server():
    return mcp

@pytest.mark.asyncio
async def test_vst_bridge_tools(mcp_server: FastMCP):
    res = await mcp_server.call_tool("fl_vst_auto_replace", {"missing_vst_name": "Omnisphere"})
    assert "Omnisphere" in str(res)
    assert "Flex" in str(res)

@pytest.mark.asyncio
async def test_vocal_alignment_tools(mcp_server: FastMCP):
    res = await mcp_server.call_tool("fl_vocal_aligner", {"lead_vocal_track": 1, "backing_vocal_track": 2})
    assert "Track 1" in str(res)
    assert "Track 2" in str(res)
    assert "phase-aligned" in str(res)

@pytest.mark.asyncio
async def test_video_generation_tools(mcp_server: FastMCP):
    res = await mcp_server.call_tool("fl_generate_visualizer_zgame", {})
    assert "ZGameEditor Visualizer" in str(res)

@pytest.mark.asyncio
async def test_project_vc_tools(mcp_server: FastMCP):
    res = await mcp_server.call_tool("fl_project_version_control", {"branch_name": "experimental-drop", "action": "checkout"})
    assert "checkout" in str(res)
    assert "experimental-drop" in str(res)

@pytest.mark.asyncio
async def test_spatial_audio_tools(mcp_server: FastMCP):
    res = await mcp_server.call_tool("fl_export_dolby_atmos_stems", {})
    assert "Dolby Atmos Spatial Audio" in str(res)
    assert "10 'Beds'" in str(res)
