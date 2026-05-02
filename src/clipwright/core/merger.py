"""GoPro chapter merging — lossless concatenation of chaptered recordings."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from clipwright.core import ffmpeg
from clipwright.core.mediafile import Recording


def merge_chapters(
    recording: Recording,
    output_dir: Path,
    on_progress: Callable[[float], None] | None = None,
) -> Path:
    """Merge a multi-chapter recording into a single file.

    Uses ffmpeg concat demuxer for lossless concatenation (no re-encoding).

    Args:
        recording: A Recording with multiple chapters.
        output_dir: Directory to write the merged file.
        on_progress: Optional callback(percent).

    Returns:
        Path to the merged output file.
    """
    if not recording.needs_merge:
        return recording.primary_file.path

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = recording.primary_file.path.stem
    ext = recording.primary_file.path.suffix
    output_path = output_dir / f"{stem}_merged{ext}"

    chapter_paths = [ch.path for ch in recording.chapters]

    ffmpeg.concat(
        chapter_paths,
        output_path,
        duration_sec=recording.total_duration,
        on_progress=on_progress,
    )

    return output_path
