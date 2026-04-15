"""macOS MIDI transport — uses the built-in IAC Driver virtual bus.

Setup (one-time):
  1. Open "Audio MIDI Setup" (Spotlight → Audio MIDI Setup)
  2. Window → Show MIDI Studio
  3. Double-click "IAC Driver" → check "Device is online"
  4. Rename the bus to "FL Studio Bus" if desired (update FL_MCP_PORT accordingly)

FL Studio config:
  MIDI Settings → Input → select the same IAC bus → enable "Enable" checkbox
  MIDI Settings → General → assign the bus to the FL MCP Bridge controller script
"""

import mido
import mido.backends.rtmidi  # noqa: F401 — ensure rtmidi backend is loaded

from .base import MIDITransport


class MacOSMIDITransport(MIDITransport):
    """macOS transport backed by IAC Driver / rtmidi."""

    _IAC_HINT = "IAC Driver"

    def list_output_ports(self) -> list[str]:
        return mido.get_output_names()

    def list_input_ports(self) -> list[str]:
        return mido.get_input_names()

    def open_output(self, port_name: str) -> mido.ports.BaseOutput:
        return mido.open_output(port_name)

    def open_input(self, port_name: str, callback=None) -> mido.ports.BaseInput:
        if callback is not None:
            return mido.open_input(port_name, callback=callback)
        return mido.open_input(port_name)

    @property
    def default_output_hint(self) -> str:
        return self._IAC_HINT
