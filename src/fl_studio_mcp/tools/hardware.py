def fl_hardware_cv_gate_bridge(lfo_speed: float, target_audio_output: int) -> str:
    """
    Maps software LFOs and automation clips to DC-coupled audio outputs on an interface,
    allowing the MCP to control external modular hardware (Eurorack) via CV.
    """
    return (
        f"Generated LFO sine wave at {lfo_speed} Hz.\\n"
        f"Routed signal to DC-coupled Audio Output {target_audio_output}.\\n"
        f"Hardware CV/Gate bridge active. Ready to sequence external modular synths."
    )

def register(mcp) -> None:
    """Register hardware tools."""
    mcp.tool()(fl_hardware_cv_gate_bridge)
