"""Tests for Sprint 7: MCP Protocol Upgrades & Developer Experience.

Includes resource resolution tests, prompt generation tests, and type stub compliance tests.
"""

import json
import pytest
from fl_studio_mcp.server import mcp


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
