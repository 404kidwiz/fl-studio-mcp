"""Tests for Sprint 7: MCP Protocol Upgrades & Developer Experience.

Includes resource resolution tests, prompt generation tests, and type stub compliance tests.
"""

import os
import json
import pytest
from fl_studio_mcp.server import mcp
from fl_studio_mcp.bridge import FLStudioBridge

def parse(result: str) -> dict:
    return json.loads(result)

class TestSprint7Resources:
    @pytest.mark.asyncio
    async def test_resource_bpm_dry_run(self, dry_bridge):
        # Retrieve get_bpm resource
        resources = {str(r.uri): r for r in mcp._resource_manager.list_resources()}
        assert "fl://bpm" in resources
        
        bpm_resource = resources["fl://bpm"]
        result_str = await bpm_resource.fn()
        res = parse(result_str)
        
        assert res["bpm"] == 120
        assert res["source"] == "dry_run_preview"

    @pytest.mark.asyncio
    async def test_resource_channels_dry_run(self, dry_bridge):
        # Retrieve get_channels resource
        resources = {str(r.uri): r for r in mcp._resource_manager.list_resources()}
        assert "fl://channels" in resources
        
        channels_resource = resources["fl://channels"]
        result_str = await channels_resource.fn()
        res = parse(result_str)
        
        assert "channels" in res
        assert res["count"] == 5
        assert res["source"] == "dry_run_preview"

    @pytest.mark.asyncio
    async def test_resource_pattern_notes_dry_run(self, dry_bridge):
        # Retrieve get_pattern_notes resource
        resources = {str(r.uri): r for r in mcp._resource_manager.list_resources()}
        assert "fl://pattern/notes" in resources
        
        notes_resource = resources["fl://pattern/notes"]
        result_str = await notes_resource.fn()
        res = parse(result_str)
        
        assert "notes" in res
        assert res["count"] == 3
        assert res["source"] == "dry_run_preview"

    @pytest.mark.asyncio
    async def test_resource_pattern_notes_visual_dry_run(self, dry_bridge):
        # Retrieve get_pattern_notes_visual resource
        resources = {str(r.uri): r for r in mcp._resource_manager.list_resources()}
        assert "fl://pattern/notes/visual" in resources
        
        notes_visual_resource = resources["fl://pattern/notes/visual"]
        result_str = await notes_visual_resource.fn()
        
        assert "🎹 Active Piano Roll MIDI Visualizer" in result_str
        assert "Scale Span" in result_str
        assert "Beat  |" in result_str
        assert "C4" in result_str
        assert "G4" in result_str
        assert "█" in result_str




class TestSprint7Prompts:
    def test_prompt_generate_trap_loop(self):
        prompts = {p.name: p for p in mcp._prompt_manager.list_prompts()}
        assert "generate-trap-loop" in prompts
        
        prompt_obj = prompts["generate-trap-loop"]
        
        # Test with defaults
        res_default = prompt_obj.fn()
        assert "140 BPM" in res_default
        assert "Trap hi-hat triplets" in res_default
        
        # Test with custom tempo
        res_custom = prompt_obj.fn(tempo=150)
        assert "150 BPM" in res_custom

    def test_prompt_insert_chords(self):
        prompts = {p.name: p for p in mcp._prompt_manager.list_prompts()}
        assert "insert-chords" in prompts
        
        prompt_obj = prompts["insert-chords"]
        
        # Test with defaults
        res_default = prompt_obj.fn()
        assert "key of C minor" in res_default
        assert "fl_add_chord_progression" in res_default
        
        # Test with custom key/scale
        res_custom = prompt_obj.fn(key="F#", scale="major")
        assert "key of F# major" in res_custom

    def test_prompt_humanize_pattern(self):
        prompts = {p.name: p for p in mcp._prompt_manager.list_prompts()}
        assert "humanize-pattern" in prompts
        
        prompt_obj = prompts["humanize-pattern"]
        
        # Test with defaults
        res_default = prompt_obj.fn()
        assert "swing factor of 0.1" in res_default
        assert "fl_get_notes" in res_default
        
        # Test with custom swing
        res_custom = prompt_obj.fn(swing=0.25)
        assert "swing factor of 0.25" in res_custom


class TestSprint7TypeStubs:
    def test_type_stubs_exist_and_conform(self):
        stub_dir = "fl_studio_scripts/stubs"
        expected_files = [
            "channels.pyi",
            "patterns.pyi",
            "transport.pyi",
            "mixer.pyi",
            "playlist.pyi",
            "ui.pyi",
            "general.pyi",
            "device.pyi",
        ]
        
        for fname in expected_files:
            fpath = os.path.join(stub_dir, fname)
            assert os.path.exists(fpath), f"Stub file {fname} is missing!"
            
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                
            assert "def " in content, f"Stub file {fname} should contain function declarations."

        # Specific module declarations check
        with open(os.path.join(stub_dir, "general.pyi"), "r", encoding="utf-8") as f:
            general_content = f.read()
        assert "processRECEvent" in general_content
        assert "processMIDICC" in general_content
        assert "undoUp" in general_content
        assert "undoDown" in general_content

        with open(os.path.join(stub_dir, "device.pyi"), "r", encoding="utf-8") as f:
            device_content = f.read()
        assert "setHasMeters" in device_content
        assert "midiOutSysex" in device_content
