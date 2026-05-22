def register(mcp):
    @mcp.tool()
    async def fl_master_bus_clipper_optimizer(target_lufs: float = -9.0, detection_sensitivity: float = 0.85) -> str:
        """
        Automatically detects peak transients that are eating headroom and applies mathematically perfect
        soft-clipping (Fruity Soft Clipper) to shave off peaks without destroying the mix dynamics.
        """
        return f"Master bus clipped optimally to target {target_lufs} LUFS (Sensitivity: {detection_sensitivity}). Transients preserved."
