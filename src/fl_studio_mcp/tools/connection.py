"""Tool: connect_fl_studio — open the MIDI port and set session state."""

from mcp.server.fastmcp import FastMCP

from ..bridge import FLStudioBridge, format_result
from ..errors import FLMCPError
from ..models import ConnectInput


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="fl_connect",
        annotations={
            "title": "Connect to FL Studio",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def fl_connect(params: ConnectInput) -> str:
        """Open the MIDI output port used to send commands to FL Studio.

        Must be called before play_transport, stop_transport, set_tempo,
        insert_notes, add_chord_progression, or save_project_as.

        Dry-run mode (dry_run=true) enables full tool exploration without
        sending any MIDI — useful for testing prompts and validating inputs.

        Args:
            params (ConnectInput):
                - port_name (str): MIDI output port name. Partial match OK.
                  Use fl_list_midi_ports to discover names.
                - dry_run (bool): If true, no MIDI is sent. Defaults to false.

        Returns:
            str: JSON with keys:
                - connected (bool)
                - port (str): exact port name opened (or "(dry-run)")
                - dry_run (bool)
                - platform_transport (str): transport class used

        Examples:
            - Connect for real:    {"port_name": "IAC Driver Bus 1"}
            - Explore without MIDI: {"port_name": "IAC Driver Bus 1", "dry_run": true}
        """
        bridge = FLStudioBridge.get()
        try:
            bridge.connect(params.port_name, dry_run=params.dry_run)
        except FLMCPError as exc:
            return format_result(exc.to_dict())
        except ValueError as exc:
            # resolve_port raises ValueError with a helpful message
            from ..errors import ErrorCode
            return format_result(
                FLMCPError(ErrorCode.MIDI_PORT_NOT_FOUND, str(exc)).to_dict()
            )

        return format_result(bridge.status())
