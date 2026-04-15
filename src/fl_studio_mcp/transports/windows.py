"""Windows MIDI transport stub — uses loopMIDI virtual ports.

Setup (one-time):
  1. Download loopMIDI from https://www.tobias-erichsen.de/software/loopmidi.html
  2. Create a port named "FL Studio Bus" (or any name — set FL_MCP_PORT to match)
  3. In FL Studio MIDI Settings, assign that port to the FL MCP Bridge script

This module is intentionally minimal for v1. Tool interfaces are identical to
macOS — only port discovery logic differs. Swap in when targeting Windows.
"""

import mido
import mido.backends.rtmidi  # noqa: F401

from .base import MIDITransport


class WindowsMIDITransport(MIDITransport):
    """Windows transport backed by loopMIDI / rtmidi."""

    _LOOP_MIDI_HINT = "FL Studio Bus"

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
        return self._LOOP_MIDI_HINT
