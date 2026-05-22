import os
import sys
from pathlib import Path
from typing import List, Dict
from mcp.server.fastmcp import FastMCP

from ..bridge import format_result
from ..automation import get_automation


def get_fl_user_data_path() -> Path:
    """Finds the user's FL Studio User Data folder cross-platform."""
    if sys.platform == "win32":
        try:
            import ctypes

            buf = ctypes.create_unicode_buffer(1024)
            # CSIDL_PERSONAL (Documents folder) is 5
            ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)
            doc_path = Path(buf.value)
        except Exception:
            doc_path = Path.home() / "Documents"
    else:
        doc_path = Path.home() / "Documents"

    fl_path = doc_path / "Image-Line" / "FL Studio"

    # Handle OneDrive documents folder on Windows
    if sys.platform == "win32" and not fl_path.exists():
        onedrive_path = (
            Path.home() / "OneDrive" / "Documents" / "Image-Line" / "FL Studio"
        )
        if onedrive_path.exists():
            fl_path = onedrive_path

    return fl_path


def scan_plugin_database() -> Dict[str, List[Dict[str, str]]]:
    """Scan the user's categorized FL Studio plugin database (Generators & Effects).

    Returns:
        Dict containing categories of plugins.
    """
    user_data_path = get_fl_user_data_path()
    plugin_db_path = user_data_path / "Presets" / "Plugin database"

    result = {"generators": [], "effects": []}

    if not plugin_db_path.exists():
        return result

    for category in ["Generators", "Effects"]:
        cat_path = plugin_db_path / category
        if not cat_path.exists():
            continue

        for root, _, files in os.walk(cat_path):
            for file in files:
                if file.lower().endswith(".fst"):
                    rel_path = Path(root).relative_to(cat_path)
                    subcat = str(rel_path) if rel_path != Path(".") else "Unsorted"
                    name = Path(file).stem
                    result[category.lower()].append(
                        {
                            "name": name,
                            "category": subcat,
                            "path": str(Path(root) / file),
                        }
                    )

    return result


def scan_system_plugins() -> List[Dict[str, str]]:
    """Scan system folders for installed plugins (VST, VST3, AU).

    Returns:
        List of plugins found on the system.
    """
    plugins = []

    if sys.platform == "darwin":  # macOS
        mac_paths = [
            ("/Library/Audio/Plug-Ins/Components", "AU"),
            ("~/Library/Audio/Plug-Ins/Components", "AU"),
            ("/Library/Audio/Plug-Ins/VST", "VST"),
            ("~/Library/Audio/Plug-Ins/VST", "VST"),
            ("/Library/Audio/Plug-Ins/VST3", "VST3"),
            ("~/Library/Audio/Plug-Ins/VST3", "VST3"),
        ]
        for raw_path, fmt in mac_paths:
            path = Path(raw_path).expanduser()
            if not path.exists():
                continue

            for item in path.iterdir():
                if item.name.startswith("."):
                    continue
                if item.suffix.lower() in [".component", ".vst", ".vst3"]:
                    plugins.append(
                        {"name": item.stem, "format": fmt, "path": str(item)}
                    )
                elif item.is_dir():
                    try:
                        for sub_item in item.iterdir():
                            if sub_item.suffix.lower() in [
                                ".component",
                                ".vst",
                                ".vst3",
                            ]:
                                plugins.append(
                                    {
                                        "name": sub_item.stem,
                                        "format": fmt,
                                        "path": str(sub_item),
                                    }
                                )
                    except OSError:
                        pass

    elif sys.platform == "win32":  # Windows
        win_paths = [
            ("C:\\Program Files\\Common Files\\VST3", "VST3"),
            ("C:\\Program Files (x86)\\Common Files\\VST3", "VST3"),
            ("C:\\Program Files\\VSTPlugins", "VST"),
            ("C:\\Program Files\\Steinberg\\VSTPlugins", "VST"),
            ("C:\\Program Files (x86)\\VSTPlugins", "VST"),
        ]
        vst_env = os.environ.get("VST_PATH")
        if vst_env:
            win_paths.append((vst_env, "VST"))

        for raw_path, fmt in win_paths:
            path = Path(raw_path)
            if not path.exists():
                continue

            for root, _, files in os.walk(path):
                depth = len(Path(root).relative_to(path).parts)
                if depth > 2:
                    continue
                for file in files:
                    ext = Path(file).suffix.lower()
                    if ext in [".dll", ".vst3"]:
                        plugins.append(
                            {
                                "name": Path(file).stem,
                                "format": fmt,
                                "path": str(Path(root) / file),
                            }
                        )

    return plugins


def register(mcp: FastMCP) -> None:
    """Register VST scanner and loading tools with FastMCP."""

    @mcp.tool(
        name="fl_list_installed_plugins",
        annotations={
            "title": "List Installed Plugins",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def fl_list_installed_plugins(scan_system: bool = False) -> str:
        """Scan and list FL Studio plugin database (generators/effects) and system plugins.

        Args:
            scan_system: If True, also scans global macOS/Windows plugin folders
                         in addition to FL Studio categorized presets.

        Returns:
            str: JSON containing categorized generators/effects lists.
        """
        db = scan_plugin_database()
        result = {"plugin_database": db, "system_plugins": []}
        if scan_system:
            result["system_plugins"] = scan_system_plugins()

        return format_result(result)

    @mcp.tool(
        name="fl_load_plugin",
        annotations={
            "title": "Load Plugin",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def fl_load_plugin(name: str) -> str:
        """Load a VST/AU plugin into FL Studio using GUI/keystroke automation.

        This focuses FL Studio, opens the Plugin Picker (F8), searches for the
        specified plugin name, and presses Enter to load it into the active slot.

        Args:
            name: The name of the VST/AU plugin to load.

        Returns:
            str: JSON indicating success or failure.
        """
        automation = get_automation()
        success = automation.load_plugin(name)
        return format_result(
            {"success": success, "action": "load_plugin", "plugin_name": name}
        )
