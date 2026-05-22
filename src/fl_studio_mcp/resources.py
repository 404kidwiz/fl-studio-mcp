"""MCP Resources implementation for FL Studio MCP server."""

import json
from mcp.server.fastmcp import FastMCP
from .bridge import FLStudioBridge
from .protocol import (
    RESP_STATUS,
    RESP_CHANNELS,
    RESP_NOTES,
    decode_resp_status,
    decode_resp_channels,
    decode_resp_notes,
    encode_query_status,
    encode_query_channels,
    encode_get_notes,
)

def register(mcp: FastMCP) -> None:
    """Register all live FL Studio resources on the FastMCP instance."""

    @mcp.resource("fl://bpm")
    async def get_bpm() -> str:
        """Retrieve the current project BPM tempo from FL Studio.

        Returns:
            str: JSON representation of the current playback tempo.
        """
        bridge = FLStudioBridge.get()
        if bridge.dry_run:
            return json.dumps({
                "bpm": 120,
                "source": "dry_run_preview"
            }, indent=2)

        try:
            response = await bridge.query(encode_query_status(), RESP_STATUS, timeout_ms=2000)
            if response is None:
                return json.dumps({
                    "error": "TIMEOUT",
                    "hint": "FL Studio did not respond to status query"
                }, indent=2)
            
            status = decode_resp_status(response["payload"])
            return json.dumps({
                "bpm": status["bpm"],
                "source": "fl_studio"
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "error": "ERROR",
                "message": str(e)
            }, indent=2)

    @mcp.resource("fl://channels")
    async def get_channels() -> str:
        """Retrieve the current channel list from FL Studio's channel rack.

        Returns:
            str: JSON listing channel slot names and total count.
        """
        bridge = FLStudioBridge.get()
        if bridge.dry_run:
            mock = ["Kick", "Snare", "Hi-Hat", "Bass", "Synth Lead"]
            return json.dumps({
                "channels": mock,
                "count": len(mock),
                "source": "dry_run_preview"
            }, indent=2)

        try:
            response = await bridge.query(encode_query_channels(), RESP_CHANNELS, timeout_ms=2000)
            if response is None:
                return json.dumps({
                    "error": "TIMEOUT",
                    "hint": "FL Studio did not respond to channel query"
                }, indent=2)
            
            channels = decode_resp_channels(response["payload"])
            return json.dumps({
                "channels": channels,
                "count": len(channels),
                "source": "fl_studio"
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "error": "ERROR",
                "message": str(e)
            }, indent=2)

    @mcp.resource("fl://pattern/notes")
    async def get_pattern_notes() -> str:
        """Retrieve the live notes cache of the active pattern in FL Studio.

        Returns:
            str: JSON representation of the active pattern's piano roll notes.
        """
        bridge = FLStudioBridge.get()
        if bridge.dry_run:
            mock = [
                {"pitch": 60, "velocity": 100, "channel": 0, "start_tick": 0, "duration_ticks": 96},
                {"pitch": 64, "velocity": 100, "channel": 0, "start_tick": 96, "duration_ticks": 96},
                {"pitch": 67, "velocity": 100, "channel": 0, "start_tick": 192, "duration_ticks": 192},
            ]
            return json.dumps({
                "notes": mock,
                "count": len(mock),
                "source": "dry_run_preview"
            }, indent=2)

        try:
            response = await bridge.query(encode_get_notes(), RESP_NOTES, timeout_ms=2000)
            if response is None:
                return json.dumps({
                    "error": "TIMEOUT",
                    "hint": "FL Studio did not respond to notes query"
                }, indent=2)
            
            notes = decode_resp_notes(response["payload"])
            return json.dumps({
                "notes": notes,
                "count": len(notes),
                "source": "fl_studio"
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "error": "ERROR",
                "message": str(e)
            }, indent=2)

    @mcp.resource("fl://pattern/notes/visual")
    async def get_pattern_notes_visual() -> str:
        """Retrieve a beautifully rendered visual ASCII piano roll of active pattern notes.

        Returns:
            str: Markdown visual representation of active MIDI notes across beats/steps.
        """
        bridge = FLStudioBridge.get()
        notes = []

        if bridge.dry_run:
            notes = [
                {"pitch": 67, "velocity": 100, "channel": 0, "start_tick": 192, "duration_ticks": 192},
                {"pitch": 64, "velocity": 100, "channel": 0, "start_tick": 96, "duration_ticks": 96},
                {"pitch": 60, "velocity": 100, "channel": 0, "start_tick": 0, "duration_ticks": 96},
            ]
        else:
            try:
                response = await bridge.query(encode_get_notes(), RESP_NOTES, timeout_ms=2000)
                if response is not None:
                    notes = decode_resp_notes(response["payload"])
            except Exception as e:
                return f"### ❌ Error Fetching Live Notes\n\n```\n{e}\n```"

        def pitch_to_name(pitch: int) -> str:
            names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
            octave = (pitch // 12) - 1
            return f"{names[pitch % 12]}{octave}"

        if not notes:
            return "### 🎹 Piano Roll Visualizer\n\n*No notes present in the active pattern.*"

        valid_notes = [n for n in notes if n.get("duration_ticks", 0) > 0]
        if not valid_notes:
            return "### 🎹 Piano Roll Visualizer\n\n*All pattern notes have zero duration.*"

        pitches = [n["pitch"] for n in valid_notes]
        min_p = max(0, min(pitches) - 1)
        max_p = min(127, max(pitches) + 1)
        max_tick = max(n["start_tick"] + n["duration_ticks"] for n in valid_notes)

        # 16th note subdivisions = 24 ticks
        grid_ticks = 24
        total_cols = max(1, (max_tick + grid_ticks - 1) // grid_ticks)
        if total_cols > 64:
            total_cols = 64

        grid = {p: ["░"] * total_cols for p in range(min_p, max_p + 1)}

        for n in valid_notes:
            p = n["pitch"]
            if p not in grid:
                continue
            start_col = n["start_tick"] // grid_ticks
            dur_cols = max(1, n["duration_ticks"] // grid_ticks)
            for c in range(start_col, start_col + dur_cols):
                if 0 <= c < total_cols:
                    grid[p][c] = "█"

        lines = [
            "### 🎹 Active Piano Roll MIDI Visualizer",
            f"*Scale Span: {pitch_to_name(min(pitches))} - {pitch_to_name(max(pitches))} | Length: {max_tick} ticks*",
            "",
            "```text",
        ]

        # Draw time header
        beat_line = "Beat  | "
        step_line = "Step  | "
        for c in range(total_cols):
            b_num = (c // 4) + 1
            s_num = (c % 4) + 1
            if s_num == 1:
                beat_line += f"{b_num:<8}"
            step_line += f"{s_num} "

        # Crop matching lengths
        beat_line = beat_line[:len(step_line)].rstrip()
        lines.append(beat_line)
        lines.append(step_line)
        lines.append("-" * len(step_line))

        # Rows
        for p in range(max_p, min_p - 1, -1):
            row_indicator = "█" if p in pitches else " "
            row_header = f"{pitch_to_name(p):<5} | "
            row_content = " ".join(grid[p])
            lines.append(f"{row_header}{row_content}")

        lines.append("```")
        lines.append("")
        lines.append("> **Legend**: `█` = Played Note duration | `░` = Empty grid timeline subdivision (sixteenth notes)")

        return "\n".join(lines)

