"""FL Studio MCP server entry point.

Run via:
    uv run fl-studio-mcp          # installed package
    python -m fl_studio_mcp.server  # development

The server communicates over stdio (Claude Desktop / MCP clients) and bridges
commands to FL Studio via MIDI using the IAC Driver on macOS.
"""

import os
import logging

# Configure logging based on FL_MCP_LOG_LEVEL
log_level_name = os.getenv("FL_MCP_LOG_LEVEL", "WARNING").upper()
log_level = getattr(logging, log_level_name, logging.WARNING)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from mcp.server.fastmcp import FastMCP

from .tools import (
    channels,
    composition,
    connection,
    library,
    midi_ports,
    mixing,
    notes,
    pattern_control,
    pattern_list,
    patterns,
    project,
    status,
    tempo,
    transport_control,
    vst_scanner,
    gui_automation,
    presets,
    algorithmic,
    plugins,
    ui,
    project_generator,
    dsp,
    vision,
    stems,
    midi_gen,
    collaboration,
    mix_engineer,
    arranger,
    sound_design,
    mastering,
    creative_fx,
    audio_ai,
    workflow_advanced,
    vst_bridge,
    vocal_alignment,
    video_generation,
    project_vc,
    spatial_audio,
    performance,
    remix,
    generative_vocals,
    hardware,
    optimization,
    release,
    genre_fusion,
    session_musician,
    soundscapes,
    vocal_cloning,
    film_scoring,
    psychoacoustics,
    foley_designer,
    live_looping,
    humanization,
    project_health,
    arrangement_builder,
    vocal_chops,
    audio_extraction,
    gain_staging,
    euclidean_drums,
    routing_wizard,
    transition_fx,
    hardware_midi,
    latency,
    custom_ui,
    podcast_editing,
    spectral_morphing,
    remix_contest,
    mpe_generation,
    orchestral_scoring,
    lyric_video,
    master_bus,
    lofi_fx,
    arrangement_mutator,
    preset_curator,
    neural_quantizer,
    harmonic_synth,
    vocal_rider,
    transient_splitter,
    chord_voicer,
    stereo_widener,
    audio_harmonizer,
    glitch_generator,
    sidechain_carver,
    track_sheet,
    song_project_management,
)

from . import resources, prompts

mcp = FastMCP(
    "fl_studio_mcp",
    instructions=(
        "Control FL Studio via MIDI and native OS automation. "
        "Workflow: fl_list_midi_ports → fl_connect → fl_get_status to verify → "
        "then use transport/tempo/notes/project/channel/pattern/mixing tools. "
        "Set dry_run=true in fl_connect to preview without sending MIDI. "
        "Bidirectional tools (fl_get_status, fl_list_channels, fl_list_patterns) "
        "require the FL MCP Bridge controller script loaded in FL Studio's MIDI Settings. "
        "Exposes filesystem/system plugins scanning via fl_list_installed_plugins/fl_list_library "
        "and VST/file loading via fl_load_plugin/fl_load_file using GUI automation. "
        "Use fl_panic any time notes get stuck. "
        'Note pitch accepts integers (60) or note names ("C4", "F#3", "Bb4"). '
        "fl_insert_notes plays notes in realtime — to record into a pattern, "
        "enable Record mode in FL Studio's transport first, then insert notes. "
        "fl_save_project saves to the current filename (Ctrl+S equivalent). "
        "Use fl_disconnect to close ports cleanly when done."
    ),
)

# Register all tools
midi_ports.register(mcp)
connection.register(mcp)
transport_control.register(mcp)
tempo.register(mcp)
notes.register(mcp)
project.register(mcp)
status.register(mcp)
channels.register(mcp)
patterns.register(mcp)
pattern_list.register(mcp)
mixing.register(mcp)
vst_scanner.register(mcp)
library.register(mcp)
pattern_control.register(mcp)
composition.register(mcp)
gui_automation.register(mcp)
presets.register(mcp)
algorithmic.register(mcp)
plugins.register(mcp)
ui.register(mcp)
project_generator.register(mcp)
dsp.register(mcp)
vision.register(mcp)
stems.register(mcp)
midi_gen.register(mcp)
collaboration.register(mcp)
mix_engineer.register(mcp)
arranger.register(mcp)
sound_design.register(mcp)
mastering.register(mcp)
creative_fx.register(mcp)
audio_ai.register(mcp)
workflow_advanced.register(mcp)
vst_bridge.register(mcp)
vocal_alignment.register(mcp)
video_generation.register(mcp)
project_vc.register(mcp)
spatial_audio.register(mcp)
performance.register(mcp)
remix.register(mcp)
generative_vocals.register(mcp)
hardware.register(mcp)
optimization.register(mcp)
release.register(mcp)
genre_fusion.register(mcp)
session_musician.register(mcp)
soundscapes.register(mcp)
vocal_cloning.register(mcp)
film_scoring.register(mcp)
psychoacoustics.register(mcp)
foley_designer.register(mcp)
live_looping.register(mcp)
humanization.register(mcp)
project_health.register(mcp)
arrangement_builder.register(mcp)
vocal_chops.register(mcp)
audio_extraction.register(mcp)
gain_staging.register(mcp)
euclidean_drums.register(mcp)
routing_wizard.register(mcp)
transition_fx.register(mcp)
hardware_midi.register(mcp)
latency.register(mcp)
custom_ui.register(mcp)
podcast_editing.register(mcp)
spectral_morphing.register(mcp)
remix_contest.register(mcp)
mpe_generation.register(mcp)
orchestral_scoring.register(mcp)
lyric_video.register(mcp)
master_bus.register(mcp)
lofi_fx.register(mcp)
arrangement_mutator.register(mcp)
preset_curator.register(mcp)
neural_quantizer.register(mcp)
harmonic_synth.register(mcp)
vocal_rider.register(mcp)
transient_splitter.register(mcp)
chord_voicer.register(mcp)
stereo_widener.register(mcp)
audio_harmonizer.register(mcp)
glitch_generator.register(mcp)
sidechain_carver.register(mcp)
track_sheet.register(mcp)
song_project_management.register(mcp)

# Register resources and prompts
resources.register(mcp)
prompts.register(mcp)


def main() -> None:
    """Entry point for the fl-studio-mcp CLI command."""
    dry_run = os.getenv("FL_MCP_DRY_RUN", "0") == "1"
    if dry_run:
        import sys

        print(
            "FL Studio MCP starting in DRY-RUN mode (no MIDI will be sent)",
            file=sys.stderr,
        )
    mcp.run()


if __name__ == "__main__":
    main()
