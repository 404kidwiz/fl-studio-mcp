"""Tool: VST Presets librarian and coordination clicks."""

from mcp.server.fastmcp import FastMCP
from ..bridge import format_result
from ..automation import get_automation
from ..presets import PresetLibrarian
from ..models import CatalogPresetInput, SearchPresetsInput, LoadPresetInput
from ..errors import FLMCPError, ErrorCode

_librarian = None

def get_librarian() -> PresetLibrarian:
    global _librarian
    if _librarian is None:
        _librarian = PresetLibrarian()
    return _librarian

def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="fl_catalog_vst_preset",
        annotations={
            "title": "Catalog VST Preset",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def fl_catalog_vst_preset(params: CatalogPresetInput) -> str:
        """Catalog click coordinates for a VST preset.

        Saves or updates click coordinates and metadata (tags, category, notes)
        for a specific preset of a third-party VST plugin.
        """
        lib = get_librarian()
        try:
            entry = lib.catalog_preset(
                vst_name=params.vst_name,
                preset_name=params.preset_name,
                x=params.x,
                y=params.y,
                category=params.category,
                tags=params.tags,
                notes=params.notes
            )
            return format_result({
                "success": True,
                "preset": entry
            })
        except Exception as e:
            return format_result(
                FLMCPError(ErrorCode.UNKNOWN, f"Failed to catalog preset: {e}").to_dict()
            )

    @mcp.tool(
        name="fl_search_vst_presets",
        annotations={
            "title": "Search VST Presets",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def fl_search_vst_presets(params: SearchPresetsInput) -> str:
        """Search cataloged VST presets.

        Search the library by a keyword query, VST name, tag, or category.
        """
        lib = get_librarian()
        try:
            results = lib.search_presets(
                query=params.query,
                vst_name=params.vst_name,
                tag=params.tag,
                category=params.category
            )
            return format_result({
                "success": True,
                "presets": results
            })
        except Exception as e:
            return format_result(
                FLMCPError(ErrorCode.UNKNOWN, f"Failed to search presets: {e}").to_dict()
            )

    @mcp.tool(
        name="fl_load_vst_preset",
        annotations={
            "title": "Load VST Preset",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def fl_load_vst_preset(params: LoadPresetInput) -> str:
        """Load a VST preset using cataloged mouse click coordinates.

        Finds the coordinates for the preset, focuses FL Studio,
        and simulates a mouse click at those coordinates.
        """
        lib = get_librarian()
        preset = lib.get_preset(params.vst_name, params.preset_name)
        if not preset:
            return format_result(
                FLMCPError(
                    ErrorCode.INVALID_PARAMS,
                    f"Preset '{params.preset_name}' for VST '{params.vst_name}' not found."
                ).to_dict()
            )
        
        automation = get_automation()
        success = automation.click_at(preset["x"], preset["y"])
        return format_result({
            "success": success,
            "vst_name": params.vst_name,
            "preset_name": params.preset_name,
            "coordinates": {"x": preset["x"], "y": preset["y"]}
        })
