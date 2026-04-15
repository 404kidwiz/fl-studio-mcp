"""Abstract MIDI transport interface.

All platform implementations must satisfy this contract.
The tool layer only ever touches MIDITransport — never platform details.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import mido


class MIDITransport(ABC):
    """Thin wrapper around mido that knows how to find the right ports per OS."""

    @abstractmethod
    def list_output_ports(self) -> list[str]:
        """Return all available MIDI output port names."""

    @abstractmethod
    def list_input_ports(self) -> list[str]:
        """Return all available MIDI input port names."""

    @abstractmethod
    def open_output(self, port_name: str) -> mido.ports.BaseOutput:
        """Open and return a MIDI output port by exact name."""

    @abstractmethod
    def open_input(self, port_name: str) -> mido.ports.BaseInput:
        """Open and return a MIDI input port by exact name."""

    @property
    @abstractmethod
    def default_output_hint(self) -> str:
        """Substring hint for the preferred output port on this platform."""

    def resolve_port(self, partial: str, ports: list[str]) -> str:
        """Case-insensitive partial-match resolver.

        Returns the first port whose name contains `partial`.
        Raises ValueError with a helpful list if nothing matches.
        """
        needle = partial.lower()
        for p in ports:
            if needle in p.lower():
                return p
        available = "\n  ".join(ports) or "(none)"
        raise ValueError(
            f"No port matching {partial!r} found.\n"
            f"Available ports:\n  {available}\n"
            "Enable the IAC Driver in Audio MIDI Setup on macOS, "
            "or install loopMIDI on Windows."
        )
