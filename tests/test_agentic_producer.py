import os
import json
import pytest
from mcp.server.fastmcp import FastMCP
from fl_studio_mcp.models import GenerateProjectInput, ChannelInitInput, RenderProjectInput, GetTrackPeaksInput, AutoMixInput
from fl_studio_mcp.bridge import FLStudioBridge, format_result

def parse(result: str) -> dict:
    return json.loads(result)

def _get_tool(module_name: str, tool_name: str):
    import importlib
    mod = importlib.import_module(f"fl_studio_mcp.tools.{module_name}")
    _mcp = FastMCP("test")
    mod.register(_mcp)
    return {t.name: t for t in _mcp._tool_manager.list_tools()}[tool_name].fn

class TestAgenticProducer:
    @pytest.mark.asyncio
    async def test_fl_generate_project(self, tmp_path):
        output_file = str(tmp_path / "my_project.flp")
        fn = _get_tool("project_generator", "fl_generate_project")
        
        # Test trap genre starter
        params = GenerateProjectInput(
            output_path=output_file,
            genre="trap",
            bpm=145.0,
            title="My Cool Beat",
            channels=[
                ChannelInitInput(name="Bass 808", sample_path="/samples/808.wav"),
                ChannelInitInput(name="Hihat", sample_path=None)
            ]
        )
        
        res = parse(await fn(params))
        assert res["success"] is True
        assert os.path.exists(output_file)
        assert res["bpm"] == 145.0
        assert res["title"] == "My Cool Beat"
        assert res["channels"][0]["name"] == "Bass 808"
        assert res["fallback_used"] is True

    @pytest.mark.asyncio
    async def test_fl_render_project(self, tmp_path, monkeypatch):
        # Create a mock source project
        project_file = str(tmp_path / "src_project.flp")
        with open(project_file, "wb") as f:
            f.write(b"FLhd\x06\x00\x00\x00\x00\x00\x01\x00\xc0\x00FLdt\x00\x00\x00\x00")
            
        output_wav = str(tmp_path / "out.wav")
        fn = _get_tool("project", "fl_render_project")
        
        # Set environment to dry run
        monkeypatch.setenv("FL_MCP_DRY_RUN", "1")
        
        params = RenderProjectInput(
            project_path=project_file,
            output_path=output_wav,
            format="wav"
        )
        
        res = parse(await fn(params))
        assert res["success"] is True
        assert os.path.exists(output_wav)
        assert res["fallback_used"] is True
        
        # Verify the written WAV has the correct RIFF header
        with open(output_wav, "rb") as f:
            data = f.read(12)
            assert data.startswith(b"RIFF")
            assert b"WAVE" in data

    @pytest.mark.asyncio
    async def test_fl_get_track_peaks(self, dry_bridge):
        fn = _get_tool("mixing", "fl_get_track_peaks")
        params = GetTrackPeaksInput(track_index=5)
        res = parse(await fn(params))
        assert res["dry_run"] is True
        assert res["l_peak"] == 0.5
        assert res["r_peak"] == 0.5

    @pytest.mark.asyncio
    async def test_fl_auto_mix(self, dry_bridge):
        fn = _get_tool("mixing", "fl_auto_mix")
        params = AutoMixInput(
            tracks=[1, 2, 3],
            target_db=-10.0,
            headroom_db=-2.0
        )
        res = parse(await fn(params))
        assert res["success"] is True
        assert len(res["tracks_processed"]) == 3
        for item in res["tracks_processed"]:
            assert item["success"] is True
            assert "current_peak_db" in item
            assert item["target_peak_db"] == -12.0 # -10 + -2
            assert "previous_fader_vol" in item
            assert "new_fader_vol" in item
