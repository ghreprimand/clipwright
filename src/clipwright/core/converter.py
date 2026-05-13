"""Audio conversion pipeline for Linux editing compatibility."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable

from clipwright.core import ffmpeg
from clipwright.core.mediafile import Recording
from clipwright.core.outputs import resolve_output_path


def convert_recording(
    recording: Recording,
    output_dir: Path,
    output_suffix: str = "_pcm",
    conflict_policy: str = "rename",
    on_progress: Callable[[float, str], None] | None = None,
) -> Path:
    """Convert a recording to an editing-friendly audio format.

    If the recording has multiple chapters, they are merged first.
    Audio is converted from AAC to PCM.

    Args:
        recording: The recording to convert.
        output_dir: Directory to write the output file.
        on_progress: Optional callback(percent, status_message).

    Returns:
        Path to the output .mov file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build output filename
    primary = recording.primary_file
    stem = primary.path.stem
    if recording.needs_merge:
        # Use clip ID for merged files
        stem = f"{primary.path.stem}_merged"
    output_path = resolve_output_path(
        output_dir / f"{stem}{output_suffix}.mov",
        conflict_policy=conflict_policy,
    )

    total_duration = recording.total_duration

    if recording.needs_merge and recording.needs_audio_conversion:
        # Merge chapters first, then convert audio
        _report(on_progress, 0, f"Merging {len(recording.chapters)} chapters...")
        with tempfile.TemporaryDirectory() as tmp:
            merged_path = Path(tmp) / "merged.mov"
            chapter_paths = [ch.path for ch in recording.chapters]
            ffmpeg.concat(
                chapter_paths,
                merged_path,
                duration_sec=total_duration,
                on_progress=lambda pct: _report(
                    on_progress, pct * 0.4, "Merging chapters..."
                ),
            )
            _report(on_progress, 40, "Converting audio...")
            ffmpeg.convert_audio(
                merged_path,
                output_path,
                duration_sec=total_duration,
                on_progress=lambda pct: _report(
                    on_progress, 40 + pct * 0.6, "Converting audio..."
                ),
            )

    elif recording.needs_merge:
        # Merge only (audio already compatible)
        _report(on_progress, 0, "Merging chapters...")
        chapter_paths = [ch.path for ch in recording.chapters]
        ffmpeg.concat(
            chapter_paths,
            output_path,
            duration_sec=total_duration,
            on_progress=lambda pct: _report(on_progress, pct, "Merging chapters..."),
        )

    elif recording.needs_audio_conversion:
        # Single file, just convert audio
        _report(on_progress, 0, "Converting audio...")
        ffmpeg.convert_audio(
            primary.path,
            output_path,
            duration_sec=total_duration,
            on_progress=lambda pct: _report(on_progress, pct, "Converting audio..."),
        )

    else:
        # Nothing to do — file is already compatible
        _report(on_progress, 100, "Already compatible")
        return primary.path

    _report(on_progress, 100, "Done")
    return output_path


def _report(
    callback: Callable[[float, str], None] | None,
    percent: float,
    message: str,
) -> None:
    if callback:
        callback(min(100.0, max(0.0, percent)), message)
