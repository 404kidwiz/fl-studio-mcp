import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import json
from mcp.server.fastmcp import FastMCP

from fl_studio_mcp.presets import PresetLibrarian
from fl_studio_mcp.models import CatalogPresetInput, SearchPresetsInput, LoadPresetInput
from fl_studio_mcp.tools.presets import register as register_presets


@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test_presets.json"


def test_preset_librarian_basic_crud(temp_db_path):
    """Test PresetLibrarian's core catalog, search, and delete features."""
    lib = PresetLibrarian(database_path=temp_db_path)

    # 1. Catalog a preset
    entry = lib.catalog_preset(
        vst_name="Serum",
        preset_name="Ambient Pad",
        x=100,
        y=200,
        category="Pads",
        tags=["warm", "cinematic"],
        notes="A warm ambient pad sound.",
    )
    assert entry["vst_name"] == "Serum"
    assert entry["preset_name"] == "Ambient Pad"
    assert entry["x"] == 100
    assert entry["y"] == 200
    assert "warm" in entry["tags"]

    # 2. Get the preset
    fetched = lib.get_preset("Serum", "Ambient Pad")
    assert fetched is not None
    assert fetched["x"] == 100
    assert fetched["y"] == 200

    # Case insensitivity lookup
    fetched_case = lib.get_preset("serum", "ambient pad")
    assert fetched_case is not None

    # 3. Duplicate overwrite
    lib.catalog_preset(
        vst_name="Serum",
        preset_name="Ambient Pad",
        x=150,
        y=250,
        category="Pads",
        tags=["warm", "cinematic", "chill"],
    )
    fetched_updated = lib.get_preset("Serum", "Ambient Pad")
    assert fetched_updated["x"] == 150
    assert fetched_updated["y"] == 250
    assert "chill" in fetched_updated["tags"]
    # Check that database list has only 1 item (no duplicate)
    assert len(lib.data["presets"]) == 1

    # 4. Add another preset
    lib.catalog_preset(
        vst_name="Vital",
        preset_name="Sub Bass",
        x=300,
        y=400,
        category="Basses",
        tags=["heavy", "sub"],
        notes="A deep sub bass sound.",
    )

    # 5. Search presets
    # Search by VST name substring
    vst_results = lib.search_presets(vst_name="ser")
    assert len(vst_results) == 1
    assert vst_results[0]["preset_name"] == "Ambient Pad"

    # Search by tag
    tag_results = lib.search_presets(tag="heavy")
    assert len(tag_results) == 1
    assert tag_results[0]["preset_name"] == "Sub Bass"

    # Search by category
    cat_results = lib.search_presets(category="pads")
    assert len(cat_results) == 1

    # Search by general query
    query_results = lib.search_presets(query="deep")
    assert len(query_results) == 1
    assert query_results[0]["preset_name"] == "Sub Bass"

    # 6. Delete preset
    assert lib.delete_preset("Serum", "Ambient Pad") is True
    assert lib.get_preset("Serum", "Ambient Pad") is None
    assert len(lib.data["presets"]) == 1


def test_preset_librarian_fallback_path():
    """Test that PresetLibrarian falls back correctly to local path when exception occurs."""
    with patch(
        "fl_studio_mcp.presets.get_fl_user_data_path",
        side_effect=RuntimeError("No FL Studio found"),
    ):
        lib = PresetLibrarian()
        assert lib.db_path == Path(".fl_studio_mcp") / "mcp_presets.json"


@pytest.mark.asyncio
async def test_preset_tools(temp_db_path):
    """Test the FastMCP tool wrappers for Preset Librarian."""
    mcp = FastMCP("test_mcp")
    register_presets(mcp)

    tools = getattr(mcp, "_tools", None) or getattr(mcp._tool_manager, "_tools", {})
    assert "fl_catalog_vst_preset" in tools
    assert "fl_search_vst_presets" in tools
    assert "fl_load_vst_preset" in tools

    # Override get_librarian to use our test DB librarian
    test_lib = PresetLibrarian(database_path=temp_db_path)
    with patch("fl_studio_mcp.tools.presets.get_librarian", return_value=test_lib):
        # 1. Test fl_catalog_vst_preset
        catalog_tool = tools["fl_catalog_vst_preset"]
        catalog_input = CatalogPresetInput(
            vst_name="Sylenth1",
            preset_name="Pluck Sound",
            x=500,
            y=600,
            category="Plucks",
            tags=["dry", "pluck"],
            notes="A dry pluck sound.",
        )
        res_cat = await catalog_tool.fn(catalog_input)
        res_cat_data = json.loads(res_cat)
        assert res_cat_data["success"] is True
        assert res_cat_data["preset"]["preset_name"] == "Pluck Sound"

        # 2. Test fl_search_vst_presets
        search_tool = tools["fl_search_vst_presets"]
        search_input = SearchPresetsInput(query="pluck")
        res_search = await search_tool.fn(search_input)
        res_search_data = json.loads(res_search)
        assert res_search_data["success"] is True
        assert len(res_search_data["presets"]) == 1
        assert res_search_data["presets"][0]["vst_name"] == "Sylenth1"

        # 3. Test fl_load_vst_preset
        load_tool = tools["fl_load_vst_preset"]
        load_input = LoadPresetInput(vst_name="Sylenth1", preset_name="Pluck Sound")

        # Mock the automation click_at call
        mock_auto = MagicMock()
        mock_auto.click_at.return_value = True
        with patch(
            "fl_studio_mcp.tools.presets.get_automation", return_value=mock_auto
        ):
            res_load = await load_tool.fn(load_input)
            res_load_data = json.loads(res_load)
            assert res_load_data["success"] is True
            assert res_load_data["coordinates"] == {"x": 500, "y": 600}
            mock_auto.click_at.assert_called_once_with(500, 600)

        # Test loading non-existent preset
        load_missing_input = LoadPresetInput(
            vst_name="Sylenth1", preset_name="Missing Sound"
        )
        res_load_missing = await load_tool.fn(load_missing_input)
        res_load_missing_data = json.loads(res_load_missing)
        assert "error" in res_load_missing_data
