import os
import sys
import shutil
import urllib.request
from pathlib import Path

def get_fl_hardware_dir() -> Path:
    """Get the path to the FL Studio Hardware settings directory based on OS."""
    if sys.platform == "win32":
        # %USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Hardware
        user_profile = os.environ.get("USERPROFILE", "")
        base_dir = Path(user_profile) / "Documents"
    elif sys.platform == "darwin":
        # ~/Documents/Image-Line/FL Studio/Settings/Hardware
        base_dir = Path.home() / "Documents"
    else:
        raise NotImplementedError(f"Unsupported platform for bridge installation: {sys.platform}")

    hardware_dir = base_dir / "Image-Line" / "FL Studio" / "Settings" / "Hardware"
    return hardware_dir

def install_bridge_script() -> bool:
    """
    Locates or downloads the device_fl_mcp_bridge.py script and copies it
    into the user's FL Studio Hardware directory.
    
    Returns True on success, False on failure.
    """
    hardware_dir = get_fl_hardware_dir()
    bridge_dir = hardware_dir / "fl_mcp_bridge"
    dest_file = bridge_dir / "device_fl_mcp_bridge.py"

    # Create destination directory if it doesn't exist
    bridge_dir.mkdir(parents=True, exist_ok=True)

    # 1. Try to find the file locally (if running from source tree)
    # The file is at <repo_root>/fl_studio_scripts/fl_mcp_bridge/device_fl_mcp_bridge.py
    # This module is at <repo_root>/src/fl_studio_mcp/tools/install_bridge.py
    local_path = Path(__file__).parent.parent.parent.parent / "fl_studio_scripts" / "fl_mcp_bridge" / "device_fl_mcp_bridge.py"

    if local_path.exists():
        shutil.copy2(local_path, dest_file)
        return True

    # 2. If not found locally (e.g. installed via pip without shared-data), download from GitHub
    # We'll use the main branch as the source of truth for the bridge script.
    github_url = "https://raw.githubusercontent.com/404kidwiz/fl-studio-mcp/main/fl_studio_scripts/fl_mcp_bridge/device_fl_mcp_bridge.py"
    try:
        urllib.request.urlretrieve(github_url, str(dest_file))
        return True
    except Exception as e:
        print(f"Failed to download bridge script from GitHub: {e}", file=sys.stderr)
        return False
