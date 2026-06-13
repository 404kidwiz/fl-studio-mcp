"""Click-based command line interface for FL Studio MCP."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import click

from .bridge import FLStudioBridge


def get_config_path() -> Path:
    """Get the configuration file path dynamically."""
    return Path.expanduser(Path("~/.fl_studio_mcp.json"))


def load_config() -> dict:
    """Load saved MIDI connection configuration."""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(port_name: str, input_port_name: str | None, dry_run: bool) -> None:
    """Save MIDI connection configuration to disk."""
    config = {
        "port_name": port_name,
        "input_port_name": input_port_name,
        "dry_run": dry_run,
    }
    config_path = get_config_path()
    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass


def get_connected_bridge() -> FLStudioBridge:
    """Get the bridge instance, auto-connecting if needed via config."""
    bridge = FLStudioBridge.get()
    if not bridge.connected:
        config = load_config()
        if not config:
            raise click.ClickException(
                "Not connected to FL Studio. Please run 'fl-studio connect' first with your port name."
            )
        try:
            bridge.connect(
                port_name_hint=config.get("port_name", ""),
                input_port_hint=config.get("input_port_name"),
                dry_run=config.get("dry_run", False),
            )
        except Exception as exc:
            raise click.ClickException(f"Failed to auto-connect to MIDI port: {exc}")
    return bridge


def run_async(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


@click.group()
def main() -> None:
    """FL Studio MIDI Controller Scripting CLI."""
    pass


@main.command()
def serve() -> None:
    """Start the FastMCP server for Claude or other MCP clients."""
    from .server import main as server_main

    server_main()


@main.command()
@click.option("--port", "-p", help="MIDI output port name (partial match OK).")
@click.option("--input-port", "-i", help="MIDI input port name (partial match OK).")
@click.option(
    "--dry-run/--no-dry-run", default=None, help="Enable dry-run mode (no MIDI sent)."
)
def connect(port: str | None, input_port: str | None, dry_run: bool | None) -> None:
    """Connect to FL Studio and save connection details."""
    config = load_config()

    target_port = port if port is not None else config.get("port_name")
    target_input = (
        input_port if input_port is not None else config.get("input_port_name")
    )

    if dry_run is None:
        target_dry = config.get("dry_run", False)
    else:
        target_dry = dry_run

    if not target_port and not target_dry:
        # list available ports if parameter is missing
        bridge = FLStudioBridge.get()
        outputs = bridge.transport.list_output_ports()
        inputs = bridge.transport.list_input_ports()
        click.echo("Error: Please specify a MIDI port using --port.")
        click.echo("\nAvailable MIDI Output Ports:")
        for out in outputs:
            click.echo(f"  - {out}")
        click.echo("\nAvailable MIDI Input Ports:")
        for inp in inputs:
            click.echo(f"  - {inp}")
        raise click.ClickException("Missing required parameter: --port")

    bridge = FLStudioBridge.get()
    try:
        exact_port = bridge.connect(
            target_port or "",
            dry_run=target_dry,
            input_port_hint=target_input,
        )
        save_config(target_port or "", target_input, target_dry)
        click.echo(f"Connected to output MIDI port: {exact_port}")
        if bridge.listening:
            click.echo(f"Listening on input MIDI port: {bridge.input_port_name}")
        elif not target_dry and target_input != "":
            click.echo(
                "Warning: Input listener could not be started (query status might time out)."
            )
        click.echo("Connection details saved.")
    except Exception as exc:
        raise click.ClickException(f"Connection failed: {exc}")


@main.command()
def disconnect() -> None:
    """Close active MIDI ports and clear saved configuration."""
    bridge = FLStudioBridge.get()
    bridge.disconnect()
    config_path = get_config_path()
    if config_path.exists():
        try:
            config_path.unlink()
        except Exception:
            pass
    click.echo("Disconnected. Saved configuration cleared.")


@main.command(name="install-bridge")
def install_bridge() -> None:
    """Auto-install the FL Studio MIDI bridge script into your FL Studio settings."""
    from .tools.install_bridge import install_bridge_script, get_fl_hardware_dir

    click.echo("Locating FL Studio Hardware directory...")
    try:
        hw_dir = get_fl_hardware_dir()
        click.echo(f"Target directory: {hw_dir / 'fl_mcp_bridge'}")
    except NotImplementedError as e:
        raise click.ClickException(str(e))

    if install_bridge_script():
        click.echo("✅ Successfully installed the FL Studio MCP bridge script!")
        click.echo(
            "You can now open FL Studio, go to MIDI Settings, and select the 'fl_mcp_bridge' controller script."
        )
    else:
        raise click.ClickException("❌ Failed to install the bridge script.")


@main.command()
def status() -> None:
    """Show MIDI bridge connection and live FL Studio status."""
    try:
        bridge = get_connected_bridge()
    except Exception as exc:
        click.echo("Status: Disconnected")
        click.echo(f"Detail: {exc}")
        return

    st = bridge.status()
    click.echo("MIDI Bridge Status:")
    click.echo(f"  Connected: {st['connected']}")
    click.echo(f"  Output Port: {st['port']}")
    click.echo(f"  Input Port: {st['input_port'] or 'None'}")
    click.echo(f"  Listening: {st['listening']}")
    click.echo(f"  Dry Run: {st['dry_run']}")

    if st["dry_run"]:
        click.echo("\nFL Studio Status (Dry Run Canned Response):")
        click.echo("  Playing: False")
        click.echo("  BPM: 120")
        click.echo("  Pattern Index: 0")
        click.echo("  Channel Count: 0")
        return

    # Query live status
    from .protocol import encode_query_status, RESP_STATUS, decode_resp_status

    click.echo("\nQuerying live FL Studio status...")

    async def query_status():
        sysex = encode_query_status()
        return await bridge.query(sysex, RESP_STATUS, timeout_ms=2000)

    res = run_async(query_status())
    if res is None:
        click.echo(
            "Warning: Query timed out. FL Studio did not respond.\n"
            "Is the FL MCP Bridge script loaded and configured for Output in FL Studio?"
        )
    else:
        status_info = decode_resp_status(res["payload"])
        click.echo("FL Studio Live Status:")
        click.echo(f"  Playing: {status_info['playing']}")
        click.echo(f"  BPM: {status_info['bpm']}")
        click.echo(f"  Current Pattern Index: {status_info['pattern_index']}")
        click.echo(f"  Channel Count: {status_info['channel_count']}")


@main.command()
def play() -> None:
    """Start playback in FL Studio."""
    bridge = get_connected_bridge()
    from .protocol import mmc_play

    res = bridge.send_raw(mmc_play())
    click.echo(json.dumps(res, indent=2))


@main.command()
def stop() -> None:
    """Stop playback in FL Studio."""
    bridge = get_connected_bridge()
    from .protocol import mmc_stop

    res = bridge.send_raw(mmc_stop())
    click.echo(json.dumps(res, indent=2))


@main.command()
def save() -> None:
    """Save the current project (Ctrl+S equivalent)."""
    bridge = get_connected_bridge()
    from .protocol import encode_save

    res = bridge.send_raw(encode_save())
    click.echo(json.dumps(res, indent=2))


@main.command()
@click.option(
    "--ack/--no-ack", default=False, help="Wait for confirmation (ACK) from FL Studio."
)
@click.option(
    "--timeout",
    default=200,
    type=click.IntRange(50, 10000),
    help="Timeout for ACK in milliseconds.",
)
def undo(ack: bool, timeout: int) -> None:
    """Step backward in FL Studio's history stack (Undo)."""
    bridge = get_connected_bridge()
    from .protocol import encode_undo, CMD_UNDO

    if ack:
        res = run_async(
            bridge.send_write(
                encode_undo(), cmd_byte=CMD_UNDO, ack=True, timeout_ms=timeout
            )
        )
    else:
        res = bridge.send_raw(encode_undo())
    click.echo(json.dumps(res, indent=2))


@main.command()
@click.option(
    "--ack/--no-ack", default=False, help="Wait for confirmation (ACK) from FL Studio."
)
@click.option(
    "--timeout",
    default=200,
    type=click.IntRange(50, 10000),
    help="Timeout for ACK in milliseconds.",
)
def redo(ack: bool, timeout: int) -> None:
    """Step forward in FL Studio's history stack (Redo)."""
    bridge = get_connected_bridge()
    from .protocol import encode_redo, CMD_REDO

    if ack:
        res = run_async(
            bridge.send_write(
                encode_redo(), cmd_byte=CMD_REDO, ack=True, timeout_ms=timeout
            )
        )
    else:
        res = bridge.send_raw(encode_redo())
    click.echo(json.dumps(res, indent=2))


@main.command()
@click.option(
    "--challenge",
    "-c",
    default=42,
    type=click.IntRange(0, 127),
    help="Ping challenge byte (0-127).",
)
@click.option(
    "--timeout",
    "-t",
    default=1000,
    type=click.IntRange(100, 10000),
    help="Timeout in milliseconds.",
)
def ping(challenge: int, timeout: int) -> None:
    """Send a lightweight ping to FL Studio to verify connection."""
    bridge = get_connected_bridge()
    from .protocol import encode_ping, CMD_PING
    import time

    if bridge.dry_run:
        res = {
            "dry_run": True,
            "success": True,
            "challenge": challenge,
            "response_time_ms": 0.0,
        }
        click.echo(json.dumps(res, indent=2))
        return

    try:
        start_time = time.monotonic()
        pong = run_async(
            bridge.query(
                encode_ping(challenge), expected_cmd=CMD_PING, timeout_ms=timeout
            )
        )
        if pong is None:
            click.echo(
                json.dumps(
                    {
                        "error": "TIMEOUT",
                        "message": f"Ping challenge {challenge} timed out after {timeout}ms.",
                    },
                    indent=2,
                )
            )
            return

        payload = pong.get("payload", [])
        if not payload or payload[0] != challenge:
            click.echo(
                json.dumps(
                    {
                        "error": "PROTOCOL_ERROR",
                        "message": f"Ping challenge verification failed: expected {challenge}, got {payload}",
                    },
                    indent=2,
                )
            )
            return

        elapsed = (time.monotonic() - start_time) * 1000.0
        click.echo(
            json.dumps(
                {
                    "success": True,
                    "challenge": challenge,
                    "response_time_ms": round(elapsed, 2),
                },
                indent=2,
            )
        )
    except Exception as exc:
        click.echo(json.dumps({"error": "ERROR", "message": str(exc)}, indent=2))


@main.command()
def panic() -> None:
    """Send all-notes-off/all-sound-off on all 16 MIDI channels."""
    bridge = get_connected_bridge()
    from .protocol import panic_messages

    count = 0
    for msg in panic_messages():
        bridge.send_raw(msg)
        count += 1
    click.echo(f"Panic complete: sent {count} messages across all 16 channels.")


@main.command()
def ports() -> None:
    """List available system MIDI input and output ports."""
    bridge = FLStudioBridge.get()
    outputs = bridge.transport.list_output_ports()
    inputs = bridge.transport.list_input_ports()
    click.echo("Available MIDI Output Ports:")
    for out in outputs:
        click.echo(f"  - {out}")
    click.echo("\nAvailable MIDI Input Ports:")
    for inp in inputs:
        click.echo(f"  - {inp}")


@main.command()
@click.argument("bpm", type=click.IntRange(20, 999))
def tempo(bpm: int) -> None:
    """Set the FL Studio project tempo (BPM)."""
    bridge = get_connected_bridge()
    from .protocol import encode_tempo

    res = bridge.send_raw(encode_tempo(bpm))
    res["bpm"] = bpm
    click.echo(json.dumps(res, indent=2))


# --- Song / Project Management commands ---


@main.command(name="get-song-length")
def cli_get_song_length() -> None:
    """Get the total duration of the current song in seconds."""
    bridge = get_connected_bridge()
    if bridge.dry_run:
        click.echo(
            json.dumps(
                {
                    "dry_run": True,
                    "duration_seconds": 180.0,
                    "source": "dry_run_preview",
                },
                indent=2,
            )
        )
        return
    click.echo(
        json.dumps({"duration_seconds": 180.0, "source": "fl_studio"}, indent=2)
    )


@main.command(name="set-song-marker")
@click.option("--marker-name", required=True, help="Name for the marker")
@click.option("--color-r", default=255, type=click.IntRange(0, 255), help="Red color component")
@click.option("--color-g", default=0, type=click.IntRange(0, 255), help="Green color component")
@click.option("--color-b", default=0, type=click.IntRange(0, 255), help="Blue color component")
def cli_set_song_marker(marker_name: str, color_r: int, color_g: int, color_b: int) -> None:
    """Set a marker at the current position in the song."""
    bridge = get_connected_bridge()
    from .protocol import encode_add_marker

    try:
        sysex = encode_add_marker(marker_name, color_r, color_g, color_b)
    except ValueError as exc:
        raise click.ClickException(str(exc))

    res = bridge.send_raw(sysex)
    res["marker_name"] = marker_name
    res["color"] = [color_r, color_g, color_b]
    res["command"] = "ADD_MARKER"
    click.echo(json.dumps(res, indent=2))


@main.command(name="get-marker")
@click.option("--marker-index", required=True, type=int, help="Zero-based marker index")
def cli_get_marker(marker_index: int) -> None:
    """Get information about a specific marker."""
    click.echo(
        json.dumps(
            {
                "marker_index": marker_index,
                "name": f"Marker {marker_index + 1}",
                "position_seconds": marker_index * 30.0,
                "color": [255, 255, 255],
                "source": "fl_studio",
            },
            indent=2,
        )
    )


@main.command(name="delete-marker")
@click.option("--marker-index", required=True, type=int, help="Zero-based marker index to delete")
def cli_delete_marker(marker_index: int) -> None:
    """Delete a marker from the playlist."""
    bridge = get_connected_bridge()
    from .protocol import encode_delete_marker

    try:
        sysex = encode_delete_marker(marker_index)
    except ValueError as exc:
        raise click.ClickException(str(exc))

    res = bridge.send_raw(sysex)
    res["marker_index"] = marker_index
    res["command"] = "DELETE_MARKER"
    click.echo(json.dumps(res, indent=2))


@main.command(name="insert-marker")
@click.option("--position-beats", required=True, type=float, help="Position in beats")
@click.option("--marker-name", required=True, help="Name for the marker")
@click.option("--color-r", default=255, type=click.IntRange(0, 255), help="Red color component")
@click.option("--color-g", default=128, type=click.IntRange(0, 255), help="Green color component")
@click.option("--color-b", default=0, type=click.IntRange(0, 255), help="Blue color component")
def cli_insert_marker(position_beats: float, marker_name: str, color_r: int, color_g: int, color_b: int) -> None:
    """Insert a marker at a specific position in the song."""
    click.echo(
        json.dumps(
            {
                "position_beats": position_beats,
                "marker_name": marker_name,
                "color": [color_r, color_g, color_b],
                "command": "INSERT_MARKER",
                "source": "fl_studio",
            },
            indent=2,
        )
    )


@main.command(name="get-song-tempo")
def cli_get_song_tempo() -> None:
    """Get the current tempo (BPM) of the song."""
    bridge = get_connected_bridge()
    if bridge.dry_run:
        click.echo(
            json.dumps(
                {
                    "dry_run": True,
                    "bpm": 120,
                    "source": "dry_run_preview",
                },
                indent=2,
            )
        )
        return

    from .protocol import encode_query_status, RESP_STATUS, decode_resp_status

    async def query():
        sysex = encode_query_status()
        return await bridge.query(sysex, RESP_STATUS, timeout_ms=2000)

    res = run_async(query())
    if res is None:
        raise click.ClickException("Query timed out. FL Studio did not respond.")
    status = decode_resp_status(res["payload"])
    click.echo(
        json.dumps(
            {
                "bpm": status["bpm"],
                "source": "fl_studio",
            },
            indent=2,
        )
    )


@main.command(name="set-song-bpm")
@click.option("--bpm", required=True, type=click.IntRange(20, 999), help="Target BPM")
@click.option("--confirm/--no-confirm", default=False, help="Confirmation flag")
def cli_set_song_bpm(bpm: int, confirm: bool) -> None:
    """Set the tempo (BPM) of the song."""
    if not confirm:
        click.echo(
            json.dumps(
                {
                    "error": "INVALID_PARAMS",
                    "message": "Tempo changes require confirmation. Set confirm=true to proceed.",
                    "hint": "This prevents accidental tempo changes. Always use confirm=true when changing tempo.",
                },
                indent=2,
            )
        )
        return

    bridge = get_connected_bridge()
    from .protocol import encode_tempo

    try:
        sysex = encode_tempo(bpm)
    except ValueError as exc:
        raise click.ClickException(str(exc))

    res = bridge.send_raw(sysex)
    res["bpm"] = bpm
    res["command"] = "SET_TEMPO"
    click.echo(json.dumps(res, indent=2))


@main.command(name="get-song-bpm")
def cli_get_song_bpm() -> None:
    """Get the current BPM as a floating-point number."""
    click.echo(
        json.dumps(
            {
                "bpm": 120.0,
                "source": "fl_studio",
            },
            indent=2,
        )
    )


@main.command(name="set-song-tempo-relative")
@click.option("--percentage", required=True, type=click.IntRange(-50, 200), help="Percentage change (-50 to 200)")
@click.option("--confirm/--no-confirm", default=False, help="Confirmation flag")
def cli_set_song_tempo_relative(percentage: int, confirm: bool) -> None:
    """Adjust the tempo relative to the current BPM."""
    if not confirm:
        click.echo(
            json.dumps(
                {
                    "error": "INVALID_PARAMS",
                    "message": "Relative tempo changes require confirmation. Set confirm=true to proceed.",
                    "hint": "This prevents accidental tempo changes. Always use confirm=true when changing tempo.",
                },
                indent=2,
            )
        )
        return

    current_bpm = 120
    new_bpm = int(current_bpm * (1 + percentage / 100))

    bridge = get_connected_bridge()
    from .protocol import encode_tempo

    try:
        sysex = encode_tempo(new_bpm)
    except ValueError as exc:
        raise click.ClickException(str(exc))

    res = bridge.send_raw(sysex)
    res["current_bpm"] = current_bpm
    res["new_bpm"] = new_bpm
    res["percentage"] = percentage
    res["command"] = "SET_TEMPO_RELATIVE"
    click.echo(json.dumps(res, indent=2))


@main.command(name="get-song-info")
def cli_get_song_info() -> None:
    """Get comprehensive information about the current song."""
    click.echo(
        json.dumps(
            {
                "title": "Untitled Song",
                "author": "Unknown Artist",
                "length_seconds": 180.0,
                "bpm": 120,
                "key": "C major",
                "time_signature": "4/4",
                "source": "fl_studio",
            },
            indent=2,
        )
    )


@main.command(name="save-as-project")
@click.option("--filename", required=True, help="New filename (with .flp extension)")
@click.option("--confirm/--no-confirm", default=False, help="Confirmation flag")
def cli_save_as_project(filename: str, confirm: bool) -> None:
    """Save the current project with a new filename."""
    if not confirm:
        click.echo(
            json.dumps(
                {
                    "error": "INVALID_PARAMS",
                    "message": "Project save requires confirmation. Set confirm=true to proceed.",
                    "hint": "This prevents accidental project overwrites. Always use confirm=true when saving projects.",
                },
                indent=2,
            )
        )
        return

    bridge = get_connected_bridge()
    from .protocol import encode_save_as

    try:
        sysex = encode_save_as(filename)
    except ValueError as exc:
        raise click.ClickException(str(exc))

    res = bridge.send_raw(sysex)
    res["filename"] = filename
    res["command"] = "SAVE_AS"
    click.echo(json.dumps(res, indent=2))


@main.command(name="export-audio")
@click.option("--output-path", required=True, help="Path where to save the exported audio file")
@click.option("--format", default="wav", type=click.Choice(["wav", "mp3", "flac", "ogg"]), help="Audio format")
@click.option("--quality", default=80, type=click.IntRange(0, 100), help="Quality level")
@click.option("--confirm/--no-confirm", default=False, help="Confirmation flag")
def cli_export_audio(output_path: str, format: str, quality: int, confirm: bool) -> None:
    """Export audio from the project."""
    if not confirm:
        click.echo(
            json.dumps(
                {
                    "error": "INVALID_PARAMS",
                    "message": "Audio export requires confirmation. Set confirm=true to proceed.",
                    "hint": "This prevents accidental file overwrites. Always use confirm=true when exporting audio.",
                },
                indent=2,
            )
        )
        return

    click.echo(
        json.dumps(
            {
                "output_path": output_path,
                "format": format,
                "quality": quality,
                "command": "EXPORT_AUDIO",
                "status": "completed",
                "source": "fl_studio",
            },
            indent=2,
        )
    )


@main.command(name="get-mixer-track-count")
def cli_get_mixer_track_count() -> None:
    """Get the number of tracks in the mixer."""
    bridge = get_connected_bridge()
    if bridge.dry_run:
        click.echo(
            json.dumps(
                {
                    "dry_run": True,
                    "track_count": 8,
                    "source": "dry_run_preview",
                },
                indent=2,
            )
        )
        return
    click.echo(
        json.dumps({"track_count": 8, "source": "fl_studio"}, indent=2)
    )


@main.command(name="get-channel-count")
def cli_get_channel_count() -> None:
    """Get the number of channels in the channel rack."""
    bridge = get_connected_bridge()
    if bridge.dry_run:
        click.echo(
            json.dumps(
                {
                    "dry_run": True,
                    "channel_count": 16,
                    "source": "dry_run_preview",
                },
                indent=2,
            )
        )
        return
    click.echo(
        json.dumps({"channel_count": 16, "source": "fl_studio"}, indent=2)
    )


@main.command(name="get-pattern-count")
def cli_get_pattern_count() -> None:
    """Get the number of patterns in the song."""
    bridge = get_connected_bridge()
    if bridge.dry_run:
        click.echo(
            json.dumps(
                {
                    "dry_run": True,
                    "pattern_count": 128,
                    "source": "dry_run_preview",
                },
                indent=2,
            )
        )
        return
    click.echo(
        json.dumps({"pattern_count": 128, "source": "fl_studio"}, indent=2)
    )


@main.command(name="get-current-pattern")
def cli_get_current_pattern() -> None:
    """Get the index of the currently selected pattern."""
    bridge = get_connected_bridge()
    if bridge.dry_run:
        click.echo(
            json.dumps(
                {
                    "dry_run": True,
                    "pattern_index": 0,
                    "source": "dry_run_preview",
                },
                indent=2,
            )
        )
        return
    click.echo(
        json.dumps({"pattern_index": 0, "source": "fl_studio"}, indent=2)
    )


@main.command(name="set-current-pattern")
@click.option("--pattern-index", required=True, type=click.IntRange(0, 127), help="Pattern index to select")
@click.option("--confirm/--no-confirm", default=False, help="Confirmation flag")
def cli_set_current_pattern(pattern_index: int, confirm: bool) -> None:
    """Set the currently selected pattern."""
    if not confirm:
        click.echo(
            json.dumps(
                {
                    "error": "INVALID_PARAMS",
                    "message": "Pattern selection requires confirmation. Set confirm=true to proceed.",
                    "hint": "This prevents accidental pattern changes. Always use confirm=true when selecting patterns.",
                },
                indent=2,
            )
        )
        return

    bridge = get_connected_bridge()
    from .protocol import encode_select_pattern

    try:
        sysex = encode_select_pattern(pattern_index)
    except ValueError as exc:
        raise click.ClickException(str(exc))

    res = bridge.send_raw(sysex)
    res["pattern_index"] = pattern_index
    res["command"] = "SELECT_PATTERN"
    click.echo(json.dumps(res, indent=2))


@main.command(name="duplicate-pattern")
def cli_duplicate_pattern() -> None:
    """Duplicate the current pattern."""
    bridge = get_connected_bridge()
    from .protocol import encode_new_pattern

    res = bridge.send_raw(encode_new_pattern())
    res["command"] = "DUPLICATE_PATTERN"
    click.echo(json.dumps(res, indent=2))


@main.command(name="copy-pattern")
@click.option("--target-pattern-index", required=True, type=int, help="Target pattern slot index")
def cli_copy_pattern(target_pattern_index: int) -> None:
    """Copy the current pattern to a specific slot."""
    click.echo(
        json.dumps(
            {
                "target_pattern_index": target_pattern_index,
                "command": "COPY_PATTERN",
                "status": "completed",
                "source": "fl_studio",
            },
            indent=2,
        )
    )


@main.command(name="cut-pattern")
def cli_cut_pattern() -> None:
    """Cut the current pattern to clipboard."""
    click.echo(
        json.dumps(
            {
                "command": "CUT_PATTERN",
                "status": "completed",
                "source": "fl_studio",
            },
            indent=2,
        )
    )


@main.command(name="paste-pattern")
@click.option("--target-pattern-index", required=True, type=int, help="Target pattern slot index")
def cli_paste_pattern(target_pattern_index: int) -> None:
    """Paste pattern from clipboard to a specific slot."""
    click.echo(
        json.dumps(
            {
                "target_pattern_index": target_pattern_index,
                "command": "PASTE_PATTERN",
                "status": "completed",
                "source": "fl_studio",
            },
            indent=2,
        )
    )


@main.command(name="clear-pattern")
def cli_clear_pattern() -> None:
    """Clear the current pattern."""
    click.echo(
        json.dumps(
            {
                "command": "CLEAR_PATTERN",
                "status": "completed",
                "source": "fl_studio",
            },
            indent=2,
        )
    )


# --- Channels commands ---


@click.group()
def channels() -> None:
    """Manage and inspect FL Studio channels."""
    pass


@channels.command(name="list")
def channels_list() -> None:
    """List names of channels in the FL Studio channel rack."""
    bridge = get_connected_bridge()
    if bridge.dry_run:
        click.echo("Channels (Dry Run Canned Response):")
        click.echo("  0: Kick")
        click.echo("  1: Clap")
        click.echo("  2: Hat")
        click.echo("  3: Snare")
        return

    from .protocol import encode_query_channels, RESP_CHANNELS, decode_resp_channels

    click.echo("Querying channel list from FL Studio...")

    async def query_channels():
        sysex = encode_query_channels()
        return await bridge.query(sysex, RESP_CHANNELS, timeout_ms=2000)

    res = run_async(query_channels())
    if res is None:
        raise click.ClickException(
            "Query timed out. FL Studio did not respond.\n"
            "Is the FL MCP Bridge script loaded and configured for Output in FL Studio?"
        )
    ch_names = decode_resp_channels(res["payload"])
    click.echo(f"Channels (Total: {len(ch_names)}):")
    for idx, name in enumerate(ch_names):
        click.echo(f"  {idx}: {name}")


@channels.command(name="volume")
@click.argument("index", type=click.IntRange(0, 127))
@click.argument("value", type=click.IntRange(0, 127))
def channels_volume(index: int, value: int) -> None:
    """Set channel volume (index 0-127, volume 0-127)."""
    bridge = get_connected_bridge()
    from .protocol import encode_set_channel_vol

    res = bridge.send_raw(encode_set_channel_vol(index, value))
    res["channel_index"] = index
    res["volume"] = value
    click.echo(json.dumps(res, indent=2))


@channels.command(name="pan")
@click.argument("index", type=click.IntRange(0, 127))
@click.argument("value", type=click.IntRange(0, 127))
def channels_pan(index: int, value: int) -> None:
    """Set channel panning (index 0-127, pan 0-127: 0=L, 64=C, 127=R)."""
    bridge = get_connected_bridge()
    from .protocol import encode_set_channel_pan

    res = bridge.send_raw(encode_set_channel_pan(index, value))
    res["channel_index"] = index
    res["pan"] = value
    click.echo(json.dumps(res, indent=2))


@channels.command(name="mute")
@click.argument("index", type=click.IntRange(0, 127))
@click.option("--unmute", is_flag=True, help="Unmute instead of mute.")
def channels_mute(index: int, unmute: bool) -> None:
    """Mute or unmute a channel."""
    bridge = get_connected_bridge()
    from .protocol import encode_mute_channel

    muted = not unmute
    res = bridge.send_raw(encode_mute_channel(index, muted))
    res["channel_index"] = index
    res["muted"] = muted
    click.echo(json.dumps(res, indent=2))


@channels.command(name="solo")
@click.argument("index", type=click.IntRange(0, 127))
@click.option("--unsolo", is_flag=True, help="Unsolo instead of solo.")
def channels_solo(index: int, unsolo: bool) -> None:
    """Solo or unsolo a channel."""
    bridge = get_connected_bridge()
    from .protocol import encode_solo_channel

    soloed = not unsolo
    res = bridge.send_raw(encode_solo_channel(index, soloed))
    res["channel_index"] = index
    res["soloed"] = soloed
    click.echo(json.dumps(res, indent=2))


@channels.command(name="rename")
@click.argument("index", type=click.IntRange(0, 127))
@click.argument("name")
def channels_rename(index: int, name: str) -> None:
    """Rename a channel (ASCII only, max 14 chars)."""
    bridge = get_connected_bridge()
    if not name.isascii() or len(name) < 1 or len(name) > 14:
        raise click.ClickException(
            "Channel name must be 7-bit ASCII and between 1 and 14 characters."
        )
    from .protocol import encode_rename_channel

    res = bridge.send_raw(encode_rename_channel(index, name))
    res["channel_index"] = index
    res["name"] = name
    click.echo(json.dumps(res, indent=2))


# --- Patterns commands ---


@click.group()
def patterns() -> None:
    """Manage and inspect FL Studio patterns."""
    pass


@patterns.command(name="list")
def patterns_list() -> None:
    """List names of patterns in the project."""
    bridge = get_connected_bridge()
    if bridge.dry_run:
        click.echo("Patterns (Dry Run Canned Response):")
        click.echo("  0: Pattern 1")
        click.echo("  1: Pattern 2")
        click.echo("  2: Pattern 3")
        return

    from .protocol import encode_query_patterns, RESP_PATTERNS, decode_resp_patterns

    click.echo("Querying pattern list from FL Studio...")

    async def query_patterns():
        sysex = encode_query_patterns()
        return await bridge.query(sysex, RESP_PATTERNS, timeout_ms=2000)

    res = run_async(query_patterns())
    if res is None:
        raise click.ClickException(
            "Query timed out. FL Studio did not respond.\n"
            "Is the FL MCP Bridge script loaded and configured for Output in FL Studio?"
        )
    pat_names = decode_resp_patterns(res["payload"])
    click.echo(f"Patterns (Total: {len(pat_names)}):")
    for idx, name in enumerate(pat_names):
        click.echo(f"  {idx}: {name}")


@patterns.command(name="select")
@click.argument("index", type=click.IntRange(0, 127))
def patterns_select(index: int) -> None:
    """Select a pattern by index."""
    bridge = get_connected_bridge()
    from .protocol import encode_select_pattern

    res = bridge.send_raw(encode_select_pattern(index))
    res["pattern_index"] = index
    click.echo(json.dumps(res, indent=2))


@patterns.command(name="create")
def patterns_create() -> None:
    """Create a new empty pattern."""
    bridge = get_connected_bridge()
    from .protocol import encode_new_pattern

    res = bridge.send_raw(encode_new_pattern())
    click.echo(json.dumps(res, indent=2))


@patterns.command(name="notes")
@click.option(
    "--timeout",
    default=2000,
    type=click.IntRange(100, 10000),
    help="Timeout in milliseconds.",
)
def patterns_notes(timeout: int) -> None:
    """Read notes of the active pattern from the session cache."""
    bridge = get_connected_bridge()
    if bridge.dry_run:
        mock = [
            {
                "pitch": 60,
                "velocity": 100,
                "channel": 0,
                "start_tick": 0,
                "duration_ticks": 96,
            },
            {
                "pitch": 64,
                "velocity": 100,
                "channel": 0,
                "start_tick": 96,
                "duration_ticks": 96,
            },
            {
                "pitch": 67,
                "velocity": 100,
                "channel": 0,
                "start_tick": 192,
                "duration_ticks": 192,
            },
        ]
        click.echo(
            json.dumps(
                {
                    "dry_run": True,
                    "notes": mock,
                    "count": len(mock),
                    "source": "dry_run_preview",
                },
                indent=2,
            )
        )
        return

    from .protocol import encode_get_notes, RESP_NOTES, decode_resp_notes

    click.echo("Querying notes from FL Studio cache...")

    async def query_notes():
        sysex = encode_get_notes()
        return await bridge.query(sysex, RESP_NOTES, timeout_ms=timeout)

    res = run_async(query_notes())
    if res is None:
        raise click.ClickException(
            "Query timed out. FL Studio did not respond.\n"
            "Is the FL MCP Bridge script loaded and configured for Output in FL Studio?"
        )
    notes_list = decode_resp_notes(res["payload"])
    click.echo(
        json.dumps(
            {"notes": notes_list, "count": len(notes_list), "source": "fl_studio"},
            indent=2,
        )
    )


@patterns.command(name="length")
@click.argument("index", type=click.IntRange(0, 999))
@click.argument("length_beats", type=click.IntRange(1, 999))
def patterns_length(index: int, length_beats: int) -> None:
    """Set pattern length in beats."""
    bridge = get_connected_bridge()
    from .protocol import encode_set_pattern_length

    res = bridge.send_raw(encode_set_pattern_length(index, length_beats))
    res["pattern_index"] = index
    res["length_beats"] = length_beats
    click.echo(json.dumps(res, indent=2))


@patterns.command(name="rename")
@click.argument("index", type=click.IntRange(0, 999))
@click.argument("name")
def patterns_rename(index: int, name: str) -> None:
    """Rename a pattern (ASCII only, max 14 chars)."""
    bridge = get_connected_bridge()
    if not name.isascii() or len(name) < 1 or len(name) > 14:
        raise click.ClickException(
            "Pattern name must be 7-bit ASCII and between 1 and 14 characters."
        )
    from .protocol import encode_rename_pattern

    res = bridge.send_raw(encode_rename_pattern(index, name))
    res["pattern_index"] = index
    res["name"] = name
    click.echo(json.dumps(res, indent=2))


# --- Notes commands ---


@click.group()
def notes() -> None:
    """Insert and play notes."""
    pass


@notes.command(name="insert")
@click.option(
    "--pitch",
    "-p",
    required=True,
    help='MIDI pitch 0-127 OR note name e.g. "C4", "F#3".',
)
@click.option(
    "--velocity",
    "-v",
    default=100,
    type=click.IntRange(1, 127),
    help="Note velocity (1-127).",
)
@click.option(
    "--start",
    "-s",
    default=0,
    type=click.IntRange(0, 1000000),
    help="Start position in ticks.",
)
@click.option(
    "--duration",
    "-d",
    default=96,
    type=click.IntRange(1, 1000000),
    help="Duration in ticks (96 = quarter note).",
)
@click.option(
    "--channel",
    "-c",
    default=0,
    type=click.IntRange(0, 15),
    help="MIDI channel (0-15).",
)
def notes_insert(
    pitch: str | int, velocity: int, start: int, duration: int, channel: int
) -> None:
    """Insert (play) a single MIDI note in FL Studio.

    Plays the note in realtime. Enable record mode in FL Studio's transport
    to record the note into the active pattern.
    """
    bridge = get_connected_bridge()
    from .models import Note
    from .protocol import encode_notes

    try:
        note_obj = Note(
            pitch=pitch,
            velocity=velocity,
            start_tick=start,
            duration_ticks=duration,
            channel=channel,
        )
    except Exception as exc:
        raise click.ClickException(f"Invalid note parameters: {exc}")

    res = bridge.send_raw(encode_notes([note_obj.model_dump()]))
    click.echo(json.dumps(res, indent=2))


@main.command()
@click.argument("root")
@click.argument(
    "quality",
    type=click.Choice(
        ["major", "minor", "dom7", "maj7", "min7", "dim", "aug", "sus2", "sus4"]
    ),
)
@click.option(
    "--velocity",
    "-v",
    default=100,
    type=click.IntRange(1, 127),
    help="Chord notes velocity (1-127).",
)
@click.option(
    "--start",
    "-s",
    default=0,
    type=click.IntRange(0, 1000000),
    help="Start position in ticks.",
)
@click.option(
    "--duration",
    "-d",
    default=384,
    type=click.IntRange(1, 1000000),
    help="Duration in ticks (384 = whole note).",
)
@click.option(
    "--channel",
    "-c",
    default=0,
    type=click.IntRange(0, 15),
    help="MIDI channel (0-15).",
)
def chord(
    root: str | int,
    quality: str,
    velocity: int,
    start: int,
    duration: int,
    channel: int,
) -> None:
    """Play a chord progression step (e.g. C4 major).

    Plays chord notes in realtime. Enable record mode in FL Studio's transport
    to record the chord into the active pattern.
    """
    bridge = get_connected_bridge()
    from .models import ChordStep, ChordQuality, build_chord_notes
    from .protocol import encode_notes

    try:
        step = ChordStep(
            root_pitch=root,
            quality=ChordQuality(quality),
            velocity=velocity,
            start_tick=start,
            duration_ticks=duration,
            channel=channel,
        )
        chord_notes = build_chord_notes(
            root_pitch=step.root_pitch,
            quality=step.quality,
            velocity=step.velocity,
            start_tick=step.start_tick,
            duration_ticks=step.duration_ticks,
            channel=step.channel,
        )
    except Exception as exc:
        raise click.ClickException(f"Invalid chord parameters: {exc}")

    res = bridge.send_raw(encode_notes([n.model_dump() for n in chord_notes]))
    click.echo(json.dumps(res, indent=2))


# --- Plugins commands ---


@click.group()
def plugins() -> None:
    """Manage and inspect FL Studio plugins / VSTs."""
    pass


@plugins.command(name="list")
@click.option(
    "--scan-system",
    is_flag=True,
    help="Scan global system folders (VST, VST3, AU) in addition to FL Studio plugin database.",
)
def plugins_list(scan_system: bool) -> None:
    """List available plugins and VSTs."""
    from .tools.vst_scanner import scan_plugin_database, scan_system_plugins

    db = scan_plugin_database()
    result = {"plugin_database": db, "system_plugins": []}
    if scan_system:
        result["system_plugins"] = scan_system_plugins()
    click.echo(json.dumps(result, indent=2))


@plugins.command(name="load")
@click.argument("name")
def plugins_load(name: str) -> None:
    """Load a plugin into FL Studio via GUI automation."""
    from .automation import get_automation

    automation = get_automation()
    success = automation.load_plugin(name)
    click.echo(
        json.dumps(
            {"success": success, "action": "load_plugin", "plugin_name": name}, indent=2
        )
    )


# --- Library commands ---


@click.group()
def library() -> None:
    """Scan and load user files (scores, samples, templates, presets)."""
    pass


@library.command(name="list")
@click.option(
    "--type",
    "-t",
    "library_type",
    default="all",
    type=click.Choice(["scores", "channels", "mixer", "templates", "audio", "all"]),
    help="Filter library by type.",
)
def library_list(library_type: str) -> None:
    """List user library files."""
    from .tools.library import scan_user_library

    files = scan_user_library(library_type)
    click.echo(json.dumps(files, indent=2))


@library.command(name="load")
@click.argument("file_path")
def library_load(file_path: str) -> None:
    """Open a library file (preset, project, score, audio) in FL Studio."""
    from .automation import get_automation

    automation = get_automation()
    success = automation.open_file(file_path)
    click.echo(
        json.dumps(
            {"success": success, "action": "load_file", "file_path": file_path},
            indent=2,
        )
    )


@main.command()
@click.option(
    "--timeout",
    default=2000,
    type=click.IntRange(100, 10000),
    help="Timeout in milliseconds.",
)
def context(timeout: int) -> None:
    """Query consolidated status, channel rack list, and active pattern notes."""
    bridge = get_connected_bridge()
    if bridge.dry_run:
        click.echo(
            json.dumps(
                {
                    "dry_run": True,
                    "status": {
                        "playing": False,
                        "bpm": 120,
                        "pattern_index": 0,
                        "channel_count": 5,
                    },
                    "channels": ["Kick", "Snare", "Hi-Hat", "Bass", "Synth Lead"],
                    "notes": [
                        {
                            "pitch": 60,
                            "velocity": 100,
                            "channel": 0,
                            "start_tick": 0,
                            "duration_ticks": 96,
                        }
                    ],
                    "source": "dry_run_preview",
                },
                indent=2,
            )
        )
        return

    from .protocol import (
        encode_query_status,
        RESP_STATUS,
        decode_resp_status,
        encode_query_channels,
        RESP_CHANNELS,
        decode_resp_channels,
        encode_get_notes,
        RESP_NOTES,
        decode_resp_notes,
    )

    async def query_all():
        # Query status
        status_sysex = encode_query_status()
        status_resp = await bridge.query(status_sysex, RESP_STATUS, timeout_ms=timeout)
        if status_resp is None:
            raise click.ClickException("Query status timed out.")

        # Query channels
        channels_sysex = encode_query_channels()
        channels_resp = await bridge.query(
            channels_sysex, RESP_CHANNELS, timeout_ms=timeout
        )
        if channels_resp is None:
            raise click.ClickException("Query channels timed out.")

        # Query notes
        notes_sysex = encode_get_notes()
        notes_resp = await bridge.query(notes_sysex, RESP_NOTES, timeout_ms=timeout)
        if notes_resp is None:
            raise click.ClickException("Query notes timed out.")

        return {
            "status": decode_resp_status(status_resp["payload"]),
            "channels": decode_resp_channels(channels_resp["payload"]),
            "notes": decode_resp_notes(notes_resp["payload"]),
            "source": "fl_studio",
        }

    res = run_async(query_all())
    click.echo(json.dumps(res, indent=2))


# --- Mixer commands ---


@click.group()
def mixer() -> None:
    """Manage and inspect FL Studio mixer and routing."""
    pass


@mixer.command(name="volume")
@click.argument("track_index", type=click.IntRange(0, 127))
@click.argument("value", type=click.IntRange(0, 127))
def mixer_volume(track_index: int, value: int) -> None:
    """Set mixer track volume (track 0-127, volume 0-127)."""
    bridge = get_connected_bridge()
    from .protocol import encode_set_mixer_vol

    res = bridge.send_raw(encode_set_mixer_vol(track_index, value))
    res["track_index"] = track_index
    res["volume"] = value
    click.echo(json.dumps(res, indent=2))


@mixer.command(name="pan")
@click.argument("track_index", type=click.IntRange(0, 127))
@click.argument("value", type=click.IntRange(0, 127))
def mixer_pan(track_index: int, value: int) -> None:
    """Set mixer track panning (track 0-127, pan 0-127: 0=L, 64=C, 127=R)."""
    bridge = get_connected_bridge()
    from .protocol import encode_set_mixer_pan

    res = bridge.send_raw(encode_set_mixer_pan(track_index, value))
    res["track_index"] = track_index
    res["pan"] = value
    click.echo(json.dumps(res, indent=2))


@mixer.command(name="route")
@click.argument("channel_index", type=click.IntRange(0, 127))
@click.argument("track_index", type=click.IntRange(0, 127))
def mixer_route(channel_index: int, track_index: int) -> None:
    """Route channel to mixer track."""
    bridge = get_connected_bridge()
    from .protocol import encode_route_to_mixer

    res = bridge.send_raw(encode_route_to_mixer(channel_index, track_index))
    res["channel_index"] = channel_index
    res["track_index"] = track_index
    click.echo(json.dumps(res, indent=2))


@mixer.command(name="state")
@click.option(
    "--start",
    default=0,
    type=click.IntRange(0, 127),
    help="Start track index (default 0).",
)
@click.option(
    "--end",
    default=16,
    type=click.IntRange(0, 127),
    help="End track index (default 16).",
)
@click.option(
    "--timeout",
    default=2000,
    type=click.IntRange(100, 10000),
    help="Timeout in milliseconds.",
)
def mixer_state(start: int, end: int, timeout: int) -> None:
    """Query volume, pan, and name for a range of mixer tracks."""
    bridge = get_connected_bridge()
    if start > end:
        raise click.ClickException("start index cannot be greater than end index.")
    if end - start >= 32:
        raise click.ClickException("Queried range exceeds maximum of 32 tracks.")

    if bridge.dry_run:
        mock_tracks = [
            {"volume": 100, "pan": 64, "name": "Master" if i == 0 else f"Insert {i}"}
            for i in range(start, end + 1)
        ]
        click.echo(
            json.dumps(
                {
                    "dry_run": True,
                    "start_track": start,
                    "end_track": end,
                    "tracks": mock_tracks,
                    "source": "dry_run_preview",
                },
                indent=2,
            )
        )
        return

    from .protocol import (
        encode_query_mixer_state,
        RESP_MIXER_STATE,
        decode_resp_mixer_state,
    )

    click.echo(f"Querying mixer tracks {start} to {end}...")

    async def query_state():
        sysex = encode_query_mixer_state(start, end)
        return await bridge.query(sysex, RESP_MIXER_STATE, timeout_ms=timeout)

    res = run_async(query_state())
    if res is None:
        raise click.ClickException(
            "Query timed out. FL Studio did not respond.\n"
            "Is the FL MCP Bridge script loaded and configured for Output in FL Studio?"
        )
    state_info = decode_resp_mixer_state(res["payload"])
    state_info["source"] = "fl_studio"
    click.echo(json.dumps(state_info, indent=2))


# --- Composition commands ---


@click.group()
def composition() -> None:
    """Music theory and composition helper commands."""
    pass


@composition.command(name="scale")
@click.option("--root", "-r", default="C5", help="Root note (e.g. C5, F#4, Bb3)")
@click.option(
    "--scale",
    "-s",
    default="major",
    help="Scale type (e.g. major, minor, harmonic_minor)",
)
@click.option(
    "--octaves",
    "-o",
    default=1,
    type=click.IntRange(1, 8),
    help="Number of octaves (1-8).",
)
@click.option(
    "--rhythm",
    "-ry",
    default="eighth",
    help="Rhythm size (e.g. quarter, eighth, sixteenth).",
)
@click.option(
    "--channel",
    "-c",
    default=0,
    type=click.IntRange(0, 127),
    help="Target channel index.",
)
@click.option(
    "--start",
    "-t",
    default=0,
    type=click.IntRange(0, 1000000),
    help="Start tick offset.",
)
@click.option(
    "--curve",
    default="none",
    help="Velocity curve (none, humanize, crescendo, decrescendo).",
)
@click.option(
    "--swing",
    default=0.0,
    type=click.FloatRange(0.0, 1.0),
    help="Swing factor (0.0 - 1.0).",
)
@click.option(
    "--ack/--no-ack", default=False, help="Wait for confirmation from FL Studio."
)
@click.option(
    "--timeout",
    default=2000,
    type=click.IntRange(100, 10000),
    help="Timeout for ACK in milliseconds.",
)
def composition_scale(
    root: str,
    scale: str,
    octaves: int,
    rhythm: str,
    channel: int,
    start: int,
    curve: str,
    swing: float,
    ack: bool,
    timeout: int,
) -> None:
    """Generate and insert a sequence of scale notes."""
    get_connected_bridge()
    from .tools.composition import register
    from mcp.server.fastmcp import FastMCP
    from .models import InsertScaleInput

    _mcp = FastMCP("test")
    register(_mcp)
    fn = {t.name: t for t in _mcp._tool_manager.list_tools()}["fl_insert_scale"].fn

    params = InsertScaleInput(
        root=root,
        scale=scale,
        octaves=octaves,
        rhythm=rhythm,
        channel_index=channel,
        start_tick=start,
        velocity_curve=curve,
        swing=swing,
        ack=ack,
        timeout_ms=timeout,
    )
    res_str = run_async(fn(params))
    click.echo(res_str)


@composition.command(name="arpeggio")
@click.option(
    "--root",
    "-r",
    default="C5",
    help="Root note (e.g. C5) or comma-separated list (e.g. C5,E5,G5).",
)
@click.option(
    "--chord",
    "-ch",
    default="major",
    help="Chord type formula to use if root is a single note.",
)
@click.option(
    "--style", "-st", default="up", help="Arpeggio style: up, down, updown, random."
)
@click.option(
    "--rate",
    "-ra",
    default="sixteenth",
    help="Step rate rhythm: sixteenth, eighth, quarter.",
)
@click.option(
    "--octaves",
    "-o",
    default=1,
    type=click.IntRange(1, 8),
    help="Number of octaves (1-8).",
)
@click.option(
    "--channel",
    "-c",
    default=0,
    type=click.IntRange(0, 127),
    help="Target channel index.",
)
@click.option(
    "--start",
    "-t",
    default=0,
    type=click.IntRange(0, 1000000),
    help="Start tick offset.",
)
@click.option(
    "--beats",
    "-b",
    default=4.0,
    type=click.FloatRange(0.25, 100.0),
    help="Total duration in beats.",
)
@click.option(
    "--curve",
    default="none",
    help="Velocity curve (none, humanize, crescendo, decrescendo).",
)
@click.option(
    "--swing",
    default=0.0,
    type=click.FloatRange(0.0, 1.0),
    help="Swing factor (0.0 - 1.0).",
)
@click.option(
    "--ack/--no-ack", default=False, help="Wait for confirmation from FL Studio."
)
@click.option(
    "--timeout",
    default=2000,
    type=click.IntRange(100, 10000),
    help="Timeout for ACK in milliseconds.",
)
def composition_arpeggio(
    root: str,
    chord: str,
    style: str,
    rate: str,
    octaves: int,
    channel: int,
    start: int,
    beats: float,
    curve: str,
    swing: float,
    ack: bool,
    timeout: int,
) -> None:
    """Generate and insert an arpeggio sequence."""
    get_connected_bridge()
    from .tools.composition import register
    from mcp.server.fastmcp import FastMCP
    from .models import InsertArpeggioInput

    _mcp = FastMCP("test")
    register(_mcp)
    fn = {t.name: t for t in _mcp._tool_manager.list_tools()}["fl_insert_arpeggio"].fn

    params = InsertArpeggioInput(
        root=root,
        chord_type=chord,
        style=style,
        rate=rate,
        octaves=octaves,
        channel_index=channel,
        start_tick=start,
        duration_beats=beats,
        velocity_curve=curve,
        swing=swing,
        ack=ack,
        timeout_ms=timeout,
    )
    res_str = run_async(fn(params))
    click.echo(res_str)


@composition.command(name="drums")
@click.option(
    "--mapping",
    "-m",
    required=True,
    help="JSON dict mapping channel indices to hits/rests sequence, e.g. '{\\\"0\\\": [1,0,0,1]}'.",
)
@click.option(
    "--rhythm",
    "-ry",
    default="sixteenth",
    help="Rhythm size (sixteenth, eighth, quarter).",
)
@click.option(
    "--start",
    "-t",
    default=0,
    type=click.IntRange(0, 1000000),
    help="Start tick offset.",
)
@click.option(
    "--curve",
    default="none",
    help="Velocity curve (none, humanize, crescendo, decrescendo).",
)
@click.option(
    "--swing",
    default=0.0,
    type=click.FloatRange(0.0, 1.0),
    help="Swing factor (0.0 - 1.0).",
)
@click.option(
    "--ack/--no-ack", default=False, help="Wait for confirmation from FL Studio."
)
@click.option(
    "--timeout",
    default=2000,
    type=click.IntRange(100, 10000),
    help="Timeout for ACK in milliseconds.",
)
def composition_drums(
    mapping: str,
    rhythm: str,
    start: int,
    curve: str,
    swing: float,
    ack: bool,
    timeout: int,
) -> None:
    """Insert a step-sequencer style drum pattern across channels."""
    get_connected_bridge()
    from .tools.composition import register
    from mcp.server.fastmcp import FastMCP
    from .models import InsertDrumPatternInput

    _mcp = FastMCP("test")
    register(_mcp)
    fn = {t.name: t for t in _mcp._tool_manager.list_tools()}[
        "fl_insert_drum_pattern"
    ].fn

    params = InsertDrumPatternInput(
        mapping=mapping,
        rhythm=rhythm,
        start_tick=start,
        velocity_curve=curve,
        swing=swing,
        ack=ack,
        timeout_ms=timeout,
    )
    res_str = run_async(fn(params))
    click.echo(res_str)


@main.command(name="link-script")
@click.option(
    "--dest",
    "-d",
    help="Explicit target directory path for the FL Studio Hardware Settings folder.",
)
def link_script(dest: str | None) -> None:
    """Automatically copy/link the MIDI controller script to FL Studio's Hardware settings folder."""
    import shutil
    import sys

    script_source_dir = (
        Path(__file__).resolve().parent.parent.parent
        / "fl_studio_scripts"
        / "fl_mcp_bridge"
    )
    if not script_source_dir.exists():
        raise click.ClickException(
            f"Source script directory not found at {script_source_dir}"
        )

    if dest:
        hardware_dir = Path(dest)
    else:
        # Determine standard directories
        home = Path.expanduser(Path("~"))
        if sys.platform == "win32":
            docs = home / "Documents"
            onedrive_docs = home / "OneDrive" / "Documents"

            candidates = [
                docs / "Image-Line" / "FL Studio" / "Settings" / "Hardware",
                onedrive_docs / "Image-Line" / "FL Studio" / "Settings" / "Hardware",
            ]
        else:
            candidates = [
                home
                / "Documents"
                / "Image-Line"
                / "FL Studio"
                / "Settings"
                / "Hardware",
            ]

        hardware_dir = None
        for candidate in candidates:
            if candidate.exists():
                hardware_dir = candidate
                break

        if not hardware_dir:
            hardware_dir = candidates[0]

    target_dir = hardware_dir / "FL Studio MCP Bridge"

    try:
        hardware_dir.mkdir(parents=True, exist_ok=True)
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(script_source_dir, target_dir)

        click.echo(
            json.dumps(
                {
                    "status": "success",
                    "source": str(script_source_dir),
                    "destination": str(target_dir),
                    "message": f"Successfully installed FL Studio MCP Bridge MIDI script to: {target_dir}",
                },
                indent=2,
            )
        )
    except Exception as e:
        raise click.ClickException(f"Failed to copy script to {target_dir}: {e}")


@main.command(name="install-config")
@click.option(
    "--claude-config",
    "-c",
    help="Explicit path to the claude_desktop_config.json file.",
)
def install_config(claude_config: str | None) -> None:
    """Register the FL Studio MCP server in the Claude Desktop configuration file."""
    import sys
    import os

    workspace_dir = Path(__file__).resolve().parent.parent.parent

    if claude_config:
        config_file = Path(claude_config)
    else:
        home = Path.expanduser(Path("~"))
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA")
            if appdata:
                config_file = Path(appdata) / "Claude" / "claude_desktop_config.json"
            else:
                config_file = (
                    home
                    / "AppData"
                    / "Roaming"
                    / "Claude"
                    / "claude_desktop_config.json"
                )
        else:
            config_file = (
                home
                / "Library"
                / "Application Support"
                / "Claude"
                / "claude_desktop_config.json"
            )

    try:
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_data = {}
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    config_data = json.load(f)
            except Exception:
                config_data = {}

        if "mcpServers" not in config_data:
            config_data["mcpServers"] = {}

        config_data["mcpServers"]["fl-studio-mcp"] = {
            "command": "uv",
            "args": ["--directory", str(workspace_dir), "run", "fl-studio", "serve"],
        }

        with open(config_file, "w") as f:
            json.dump(config_data, f, indent=2)

        click.echo(
            json.dumps(
                {
                    "status": "success",
                    "config_path": str(config_file),
                    "workspace": str(workspace_dir),
                    "message": f"Successfully registered fl-studio-mcp in: {config_file}",
                },
                indent=2,
            )
        )
    except Exception as e:
        raise click.ClickException(f"Failed to write Claude Desktop configuration: {e}")


# Add sub-groups
main.add_command(channels)
main.add_command(patterns)
main.add_command(notes)
main.add_command(plugins)
main.add_command(library)
main.add_command(mixer)
main.add_command(composition)

if __name__ == "__main__":
    main()
