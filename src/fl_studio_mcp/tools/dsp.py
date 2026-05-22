"""
Digital Signal Processing (DSP) integration for FL Studio MCP.
Provides sample analysis (BPM, key, transients) and auto-slicing logic using Librosa.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def fl_analyze_sample(path: str, dry_run: bool = False) -> str:
    """
    Analyzes a .wav or .mp3 file for BPM, key, and transient peaks.
    """
    if dry_run:
        return json.dumps({
            "status": "success",
            "message": "DRY RUN: Sample analysis skipped",
            "data": {
                "bpm": 120.0,
                "duration": 5.4,
                "transient_count": 8
            }
        })

    try:
        import librosa
        import numpy as np
    except ImportError:
        return json.dumps({"status": "error", "message": "librosa/numpy not installed. Please install them to use DSP features."})

    if not os.path.exists(path):
        return json.dumps({"status": "error", "message": f"File not found: {path}"})

    try:
        y, sr = librosa.load(path)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        duration = librosa.get_duration(y=y, sr=sr)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        peaks = librosa.util.peak_pick(onset_env, pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.5, wait=10)
        
        return json.dumps({
            "status": "success",
            "data": {
                "bpm": float(tempo[0] if isinstance(tempo, (list, np.ndarray)) else tempo),
                "duration": float(duration),
                "transient_count": int(len(peaks))
            }
        })
    except Exception as e:
        logger.error(f"DSP Analysis error: {e}")
        return json.dumps({"status": "error", "message": str(e)})


def fl_auto_slice(path: str, output_dir: str, threshold: float = 0.5, dry_run: bool = False) -> str:
    """
    Automatically slices a file based on transients and saves the sub-wavs.
    """
    if dry_run:
        return json.dumps({
            "status": "success",
            "message": f"DRY RUN: Sliced sample into 4 pieces at {output_dir}"
        })

    try:
        import librosa
        import soundfile as sf
    except ImportError:
        return json.dumps({"status": "error", "message": "librosa/soundfile not installed."})

    if not os.path.exists(path):
        return json.dumps({"status": "error", "message": f"File not found: {path}"})

    os.makedirs(output_dir, exist_ok=True)
    try:
        y, sr = librosa.load(path)
        onsets = librosa.onset.onset_detect(y=y, sr=sr, units='samples', delta=threshold)
        
        if len(onsets) == 0:
            return json.dumps({"status": "error", "message": "No transients detected."})

        # Append end of file to onsets
        onsets = list(onsets) + [len(y)]
        
        slices = []
        for i in range(len(onsets) - 1):
            start = onsets[i]
            end = onsets[i+1]
            slice_audio = y[start:end]
            
            out_path = os.path.join(output_dir, f"slice_{i}.wav")
            sf.write(out_path, slice_audio, sr)
            slices.append(out_path)

        return json.dumps({
            "status": "success",
            "message": f"Sample sliced into {len(slices)} pieces.",
            "data": {
                "slices": slices
            }
        })
    except Exception as e:
        logger.error(f"Auto-slice error: {e}")
        return json.dumps({"status": "error", "message": str(e)})

def register(mcp) -> None:
    """Register DSP tools."""
    mcp.tool()(fl_analyze_sample)
    mcp.tool()(fl_auto_slice)
