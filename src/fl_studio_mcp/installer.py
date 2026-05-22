"""Installer script for the FL Studio MCP Bridge."""

import os
import sys
import shutil
from pathlib import Path

def get_fl_user_data_dir() -> Path:
    """Resolve the FL Studio User Data folder across platforms."""
    if sys.platform == "win32":
        docs = Path(os.environ.get("USERPROFILE", "~")).expanduser() / "Documents"
        return docs / "Image-Line" / "FL Studio"
    elif sys.platform == "darwin":
        docs = Path.home() / "Documents"
        return docs / "Image-Line" / "FL Studio"
    else:
        raise NotImplementedError(f"Unsupported OS: {sys.platform}")

def install() -> None:
    """Finds the bridge script and copies it to the FL Studio MIDI Scripts directory."""
    # Look for the bridge script locally first (dev environment)
    dev_path = Path("fl_studio_scripts/fl_mcp_bridge/device_fl_mcp_bridge.py").absolute()
    
    # Also look relative to this file in case it's packaged
    pkg_path = Path(__file__).parent.parent.parent / "fl_studio_scripts" / "fl_mcp_bridge" / "device_fl_mcp_bridge.py"
    
    src_script = dev_path if dev_path.exists() else pkg_path
    
    if not src_script.exists():
        print(f"Error: Could not find device_fl_mcp_bridge.py.", file=sys.stderr)
        print(f"Checked paths:\n- {dev_path}\n- {pkg_path}", file=sys.stderr)
        sys.exit(1)

    try:
        base_dir = get_fl_user_data_dir()
        dest_dir = base_dir / "Settings" / "Hardware" / "fl_mcp_bridge"
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        dest_file = dest_dir / "device_fl_mcp_bridge.py"
        shutil.copy2(src_script, dest_file)
        print(f"✅ Successfully installed FL Studio MCP Bridge to:\n  {dest_file}")
        print("\nNext Steps:")
        print("  1. Open FL Studio.")
        print("  2. Go to Options -> MIDI Settings.")
        print("  3. Find 'FL MCP Bridge' in the output and input lists.")
        print("  4. Set the Port to a unique number (e.g., 10).")
        print("  5. Click 'Enable'.")
    except Exception as e:
        print(f"Installation failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    install()
