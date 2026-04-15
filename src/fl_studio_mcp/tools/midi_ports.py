"""Tool: list_midi_ports — discover MIDI I/O ports on the host machine."""

import json

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge
from ..transports import get_transport


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="fl_list_midi_ports",
        annotations={
            "title": "List MIDI Ports",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_list_midi_ports() -> str:
        """List all available MIDI input and output ports on this machine.

        No connection to FL Studio is required. Use this first to discover the
        correct port name to pass to connect_fl_studio.

        On macOS, look for "IAC Driver Bus 1" (or similar) in the outputs list.
        If it's missing, enable it in Audio MIDI Setup → IAC Driver → Device is online.

        Returns:
            str: JSON with keys:
                - outputs (list[str]): available output port names
                - inputs (list[str]): available input port names
                - recommended_output (str | null): best guess for FL Studio port
                - platform_hint (str): setup instructions for this OS
        """
        transport = get_transport()
        outputs = transport.list_output_ports()
        inputs = transport.list_input_ports()

        # Try to surface the most likely FL Studio port
        hint = transport.default_output_hint
        recommended = next(
            (p for p in outputs if hint.lower() in p.lower()),
            outputs[0] if outputs else None,
        )

        import sys
        if sys.platform == "darwin":
            platform_hint = (
                "macOS: enable IAC Driver in Audio MIDI Setup. "
                "Then assign that bus in FL Studio → MIDI Settings."
            )
        else:
            platform_hint = (
                "Windows: install loopMIDI, create a virtual port, "
                "and assign it in FL Studio → MIDI Settings."
            )

        return json.dumps(
            {
                "outputs": outputs,
                "inputs": inputs,
                "recommended_output": recommended,
                "platform_hint": platform_hint,
            },
            indent=2,
        )
