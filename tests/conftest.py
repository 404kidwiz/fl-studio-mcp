"""Shared fixtures for FL Studio MCP tests."""

import pytest

from fl_studio_mcp.bridge import FLStudioBridge


@pytest.fixture(autouse=True)
def reset_bridge():
    """Reset the bridge singleton between tests to avoid state bleed."""
    # Tear down any existing instance
    if FLStudioBridge._instance is not None:
        FLStudioBridge._instance.disconnect()
        FLStudioBridge._instance = None
    yield
    # Clean up after test
    if FLStudioBridge._instance is not None:
        FLStudioBridge._instance.disconnect()
        FLStudioBridge._instance = None


@pytest.fixture
def dry_bridge() -> FLStudioBridge:
    """A pre-connected bridge in dry-run mode — no MIDI hardware required."""
    bridge = FLStudioBridge.get()
    bridge.connect("(test)", dry_run=True)
    return bridge
