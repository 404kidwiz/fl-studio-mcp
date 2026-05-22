# FL Studio MCP Production Configuration & Distribution Guide

This guide details how to compile, pack, distribute, and configure the **FL Studio MCP Server** for end-users on both **macOS** and **Windows**.

---

## 🚀 1. Production Distribution & Packaging

We use standard, modern Python packaging tools to distribute the MCP server.

### Option A: PyInstaller Single-Binary Build (Recommended for End-Users)
PyInstaller compiles the entire Python environment, dependencies, and our server into a single executable binary, removing any local Python runtime requirement.

#### macOS Compilation
Run this command on a macOS machine:
```bash
uv run pyinstaller --onefile \
  --name "fl-studio-mcp-macos" \
  --clean \
  src/fl_studio_mcp/server.py
```
*Outputs a standalone executable `dist/fl-studio-mcp-macos`.*

#### Windows Compilation
Run this command on a Windows machine:
```cmd
uv run pyinstaller --onefile ^
  --name "fl-studio-mcp-win" ^
  --clean ^
  src\fl_studio_mcp\server.py
```
*Outputs a standalone executable `dist/fl-studio-mcp-win.exe`.*

### Option B: PyPI / Source Distribution
If installing via a package manager:
```bash
# Build standard wheel and sdist
uv build
```
Users can then install it with:
```bash
uv pip install fl-studio-mcp
# or
pip install fl-studio-mcp
```

---

## ⚙️ 2. Claude Desktop Integration

To register the FL Studio MCP server with Claude Desktop, edit the `claude_desktop_config.json` file.

### Configuration File Paths
*   **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
*   **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### `claude_desktop_config.json` Templates

> [!TIP]
> Always verify the path to the executable or the python module environment matches your target installation directory.

#### Template: Compiled Standalone Executables
```json
{
  "mcpServers": {
    "fl_studio_mcp": {
      "command": "/absolute/path/to/dist/fl-studio-mcp-macos",
      "args": [],
      "env": {
        "FL_MCP_PORT": "FL Studio Bus",
        "FL_MCP_DRY_RUN": "0"
      }
    }
  }
}
```

#### Template: Local Development using `uv` (Fastest for builders)
```json
{
  "mcpServers": {
    "fl_studio_mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/fl-studio-mcp",
        "run",
        "fl-studio-mcp"
      ],
      "env": {
        "FL_MCP_PORT": "FL Studio Bus",
        "FL_MCP_DRY_RUN": "0"
      }
    }
  }
}
```

#### Template: Local Development over WebSocket Network Transport
If you are controlling a remote or containerized FL Studio instance over WebSockets:
```json
{
  "mcpServers": {
    "fl_studio_mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/fl-studio-mcp",
        "run",
        "fl-studio-mcp"
      ],
      "env": {
        "FL_MCP_PORT": "ws://127.0.0.1:8765",
        "FL_MCP_DRY_RUN": "0"
      }
    }
  }
}
```

---

## 🎹 3. FL Studio MIDI Controller Script Setup

To establish two-way communication between the MCP server and FL Studio, users must install our MIDI controller script.

### Installation Steps

1.  **Locate FL Studio's Hardware Controller Script Directory**:
    *   **macOS**: `/Users/<user>/Documents/Image-Line/FL Studio/Settings/Hardware/`
    *   **Windows**: `C:\Users\<user>\Documents\Image-Line\FL Studio\Settings\Hardware\`
2.  **Create a New Subfolder**:
    Create a folder named `device_fl_mcp_bridge` in the hardware directory.
3.  **Place the Script File**:
    Copy our bridge controller script `device_fl_mcp_bridge.py` into this folder.
4.  **Configure MIDI in FL Studio**:
    *   Open FL Studio.
    *   Go to **Options** > **MIDI Settings** (or press **F10**).
    *   Under **Input**, select your loopback MIDI port (e.g. **FL Studio Bus** or **loopMIDI Port**).
    *   Set **Controller type** to `FL MCP Bridge`.
    *   Enable the input port by toggling the **Enable** button.
    *   Under **Output**, select the same MIDI port, enable it, and assign it to the **same Port number** (e.g., Port `125` or as configured).

> [!IMPORTANT]
> The controller script handles incoming SysEx queries and sends channel listings, pattern details, and mixer feedback natively. Make sure the port names and assignments match exactly for seamless bidirectional control.

---

## 🛠️ 4. loopback MIDI Port Setup

### macOS (Native IAC Driver)
No external installations required:
1. Open **Audio MIDI Setup** app.
2. Go to **Window** > **Show MIDI Studio**.
3. Double-click **IAC Driver**.
4. Check **Device is online**.
5. Add or rename a port to `FL Studio Bus`.

### Windows (loopMIDI)
1. Download and install **loopMIDI** by Tobias Erichsen (free).
2. Open loopMIDI.
3. Add a new loopback port named `FL Studio Bus` or custom name.
4. Keep the loopMIDI app running in the background.
5. In your `claude_desktop_config.json`, pass the matching port name in `FL_MCP_PORT`.
