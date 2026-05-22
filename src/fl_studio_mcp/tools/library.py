import os
from pathlib import Path
from typing import List, Dict, Any
from mcp.server.fastmcp import FastMCP

from ..bridge import format_result
from ..automation import get_automation
from fl_studio_mcp.tools.vst_scanner import get_fl_user_data_path


def scan_user_library(library_type: str = "all") -> Dict[str, List[Dict[str, Any]]]:
    """Scan FL Studio user folder directories for assets (scores, presets, templates, audio).

    Args:
        library_type: The type of assets to list. Options: "scores", "channels", "mixer",
                      "templates", "audio", "all".

    Returns:
        Dict mapping asset categories to lists of file descriptions.
    """
    user_data_path = get_fl_user_data_path()

    categories = {
        "scores": user_data_path / "Presets" / "Scores",
        "channels": user_data_path / "Presets" / "Channel presets",
        "mixer": user_data_path / "Presets" / "Mixer presets",
        "templates": user_data_path / "Projects" / "Templates",
        "audio": user_data_path / "Audio",
    }

    result = {}

    for cat_name, cat_path in categories.items():
        if library_type != "all" and library_type != cat_name:
            continue

        result[cat_name] = []
        if not cat_path.exists():
            continue

        for root, _, files in os.walk(cat_path):
            for file in files:
                if file.startswith("."):
                    continue
                full_path = Path(root) / file
                rel_path = full_path.relative_to(cat_path)
                try:
                    stat = full_path.stat()
                    size_bytes = stat.st_size
                except Exception:
                    size_bytes = 0

                result[cat_name].append(
                    {
                        "name": Path(file).stem,
                        "file_name": file,
                        "category": str(rel_path.parent)
                        if rel_path.parent != Path(".")
                        else "Root",
                        "size_bytes": size_bytes,
                        "path": str(full_path),
                    }
                )

    return result


def register(mcp: FastMCP) -> None:
    """Register FL Studio user library tools with FastMCP."""

    @mcp.tool(
        name="fl_list_library",
        annotations={
            "title": "List User Library Files",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def fl_list_library(library_type: str = "all") -> str:
        """Scan and list user library files inside FL Studio folders.

        Args:
            library_type: The type of assets to list. Options: "scores", "channels",
                          "mixer", "templates", "audio", "all".

        Returns:
            str: JSON mapping library folders to file lists.
        """
        valid_types = ["scores", "channels", "mixer", "templates", "audio", "all"]
        if library_type not in valid_types:
            library_type = "all"

        files = scan_user_library(library_type)
        return format_result(files)

    @mcp.tool(
        name="fl_load_file",
        annotations={
            "title": "Load Library File",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def fl_load_file(file_path: str) -> str:
        """Open a preset (.fst), project (.flp), score (.fsc), or audio sample file in FL Studio.

        Args:
            file_path: Absolute path to the file to open.

        Returns:
            str: JSON indicating success or failure.
        """
        automation = get_automation()
        success = automation.open_file(file_path)
        return format_result(
            {"success": success, "action": "load_file", "file_path": file_path}
        )
