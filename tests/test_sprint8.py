"""
Tests for Phase 8: Super-Producer Features.
Tests the graceful dry_run execution of the new advanced architectures.
"""

import json
import pytest

from fl_studio_mcp.tools.dsp import fl_analyze_sample, fl_auto_slice
from fl_studio_mcp.tools.vision import fl_vision_read_vst, fl_vision_click_vst
from fl_studio_mcp.tools.stems import fl_separate_stems, fl_render_stems
from fl_studio_mcp.tools.midi_gen import fl_generate_sequence
from fl_studio_mcp.tools.collaboration import fl_sync_session

@pytest.mark.asyncio
async def test_dsp_dry_run():
    res = fl_analyze_sample("mock.wav", dry_run=True)
    data = json.loads(res)
    assert data["status"] == "success"
    assert "DRY RUN" in data["message"]
    
    res2 = fl_auto_slice("mock.wav", "/tmp/slices", dry_run=True)
    data2 = json.loads(res2)
    assert data2["status"] == "success"
    assert "DRY RUN" in data2["message"]

@pytest.mark.asyncio
async def test_vision_dry_run():
    res = fl_vision_read_vst("Serum", dry_run=True)
    data = json.loads(res)
    assert data["status"] == "success"
    assert "Serum" in data["data"]["plugin_name"]

    res2 = fl_vision_click_vst(100, 200, "double_click", dry_run=True)
    data2 = json.loads(res2)
    assert data2["status"] == "success"
    assert "double_click" in data2["message"]

@pytest.mark.asyncio
async def test_stems_dry_run():
    res = fl_separate_stems("beat.wav", "/tmp/stems", dry_run=True)
    data = json.loads(res)
    assert data["status"] == "success"
    assert len(data["data"]["stems"]) == 4

    res2 = fl_render_stems("/tmp/stems", track_count=2, dry_run=True)
    data2 = json.loads(res2)
    assert data2["status"] == "success"

@pytest.mark.asyncio
async def test_midi_gen_dry_run():
    res = fl_generate_sequence(1, style="house", length_bars=8, dry_run=True)
    data = json.loads(res)
    assert data["status"] == "success"
    assert "DRY RUN" in data["message"]

@pytest.mark.asyncio
async def test_collaboration_dry_run():
    res = fl_sync_session("/tmp/project", "http://mock.url", message="hello", dry_run=True)
    data = json.loads(res)
    assert data["status"] == "success"
    assert "hello" in data["message"]
