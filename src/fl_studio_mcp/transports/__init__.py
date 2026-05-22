"""Platform-aware MIDI transport factory.

Usage:
    from fl_studio_mcp.transports import get_transport
    transport = get_transport()
"""

import sys

from .base import MIDITransport


def get_transport(port_name: str | None = None) -> MIDITransport:
    """Return the appropriate MIDI transport for the current platform."""
    if port_name and (port_name.startswith("ws://") or port_name.startswith("wss://")):
        from .websocket import WebSocketMIDITransport
        return WebSocketMIDITransport()

    if sys.platform == "darwin":
        from .macos import MacOSMIDITransport
        return MacOSMIDITransport()
    elif sys.platform == "win32":
        from .windows import WindowsMIDITransport
        return WindowsMIDITransport()
    else:
        # Linux / other: fall back to generic rtmidi; may need additional config
        from .macos import MacOSMIDITransport  # generic rtmidi behaviour
        return MacOSMIDITransport()



__all__ = ["MIDITransport", "get_transport"]
