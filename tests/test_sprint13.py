import pytest
import asyncio
from mcp.server.fastmcp import FastMCP
from fl_studio_mcp.server import mcp

@pytest.fixture
def mcp_server():
    return mcp

@pytest.mark.asyncio
async def test_phase13_tools(mcp_server: FastMCP):
    # 1. genre_fusion
    res = await mcp_server.call_tool("fl_neuro_genre_fusion", {"genre_a": "Trap", "genre_b": "Jazz"})
    assert "Trap" in str(res)
    assert "Jazz" in str(res)
    
    # 2. session_musician
    res = await mcp_server.call_tool("fl_ai_session_musician_improviser", {"instrument": "Saxophone"})
    assert "Saxophone" in str(res)
    assert "16-bar AI improvised solo" in str(res)

    # 3. soundscapes
    res = await mcp_server.call_tool("fl_dynamic_soundscape_generator", {"environment_prompt": "Cyberpunk"})
    assert "Cyberpunk" in str(res)
    
    # 4. vocal_cloning
    res = await mcp_server.call_tool("fl_vocal_chain_cloner", {"reference_acapella": "weeknd.wav", "target_track": 10})
    assert "weeknd.wav" in str(res)
    assert "Track 10" in str(res)

    # 5. film_scoring
    res = await mcp_server.call_tool("fl_film_score_sync", {"video_file": "movie.mp4", "hit_markers": ["01:00", "01:30"]})
    assert "movie.mp4" in str(res)
    assert "2 hit markers" in str(res)

    # 6. psychoacoustics
    res = await mcp_server.call_tool("fl_psychoacoustic_exciter", {})
    assert "Psychoacoustic width" in str(res)

    # 7. foley_designer
    res = await mcp_server.call_tool("fl_auto_foley_foley_designer", {"prompt": "laser"})
    assert "laser" in str(res)
    assert "Sytrus" in str(res)

    # 8. live_looping
    res = await mcp_server.call_tool("fl_adaptive_live_looping", {})
    assert "Live Looping session ready" in str(res)

    # 9. humanization
    res = await mcp_server.call_tool("fl_chord_voicing_humanizer", {"pattern_id": 4})
    assert "Pattern 4" in str(res)
    assert "humanized" in str(res).lower()

    # 10. project_health
    res = await mcp_server.call_tool("fl_project_health_monitor", {})
    assert "Daemon" in str(res)
    assert "Ear Fatigue" in str(res)
