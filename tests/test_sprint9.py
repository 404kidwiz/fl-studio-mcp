import pytest
from fl_studio_mcp.server import mcp

@pytest.fixture
def fast_mcp():
    return mcp

@pytest.mark.asyncio
async def test_mix_engineer(fast_mcp):
    res = await fast_mcp.call_tool("fl_auto_mix_balance", {"target_rms_db": -12.0})
    assert "target -12.0" in str(res) or "Mix balanced successfully" in str(res)

    res = await fast_mcp.call_tool("fl_auto_sidechain", {"kick_track_name": "Kick", "target_track_name": "Bass"})
    assert "Sidechain" in str(res)

    res = await fast_mcp.call_tool("fl_vocal_chain_builder", {"target_track_name": "Vocals", "style": "Rap"})
    assert "chain" in str(res).lower() or "Rap" in str(res)

@pytest.mark.asyncio
async def test_arranger(fast_mcp):
    res = await fast_mcp.call_tool("fl_generate_song_structure", {"bars": 128, "style": "EDM"})
    assert "EDM" in str(res) or "structure" in str(res)

    res = await fast_mcp.call_tool("fl_generate_transitions", {"density": "High"})
    assert "riser" in str(res).lower()

@pytest.mark.asyncio
async def test_sound_design(fast_mcp):
    res = await fast_mcp.call_tool("fl_generate_synth_preset", {"prompt": "dubstep bass", "synth_target": "Serum"})
    assert "Serum" in str(res) or "preset" in str(res).lower()

@pytest.mark.asyncio
async def test_library_search(fast_mcp):
    # These return synchronously formatted text strings or mock dry run responses
    res = await fast_mcp.call_tool("fl_index_sample_library", {"directory_path": "/fake/dir"})
    assert "Indexer" in str(res)

    res = await fast_mcp.call_tool("fl_semantic_sample_search", {"query": "808"})
    assert "808" in str(res)
