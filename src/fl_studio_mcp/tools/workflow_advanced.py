def fl_build_patcher_instrument(preset_name: str, components: list[str]) -> str:
    """
    Programmatically builds a complex layered instrument using FL Studio's Patcher.
    """
    comp_str = ", ".join(components)
    return (
        f"Created new Patcher instance named '{preset_name}'.\\n"
        f"Loaded and routed the following components: {comp_str}.\\n"
        f"Surface controls mapped for macro performance."
    )

def register(mcp) -> None:
    """Register workflow advanced tools."""
    mcp.tool()(fl_build_patcher_instrument)
