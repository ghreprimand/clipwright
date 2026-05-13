"""Wrapper around ffmpeg and ffprobe subprocesses."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from collections import deque
from pathlib import Path
from typing import Callable


def _find_binary(name: str) -> str:
    """Find an ffmpeg/ffprobe binary on PATH."""
    path = shutil.which(name)
    if path is None:
        raise FileNotFoundError(
            f"'{name}' not found on PATH. Install it with: sudo apt install ffmpeg"
        )
    return path


def probe(path: Path) -> dict:
    """Run ffprobe on a file and return parsed JSON metadata."""
    ffprobe = _find_binary("ffprobe")
    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {result.stderr}")
    return json.loads(result.stdout)


def convert_audio(
    input_path: Path,
    output_path: Path,
    audio_codec: str = "pcm_s16le",
    duration_sec: float = 0.0,
    on_progress: Callable[[float], None] | None = None,
) -> Path:
    """Convert a video file's audio to an editing-friendly codec.

    Video stream is copied without re-encoding. Audio is converted to PCM.
    Output container is .mov.
    """
    ffmpeg = _find_binary("ffmpeg")
    cmd = [
        ffmpeg,
        "-y",  # overwrite output
        "-nostdin",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(input_path),
        "-c:v", "copy",
        "-c:a", audio_codec,
        "-progress", "pipe:1",
        str(output_path),
    ]
    run_with_progress(cmd, duration_sec, on_progress, "ffmpeg conversion failed")
    return output_path


def concat(
    file_list: list[Path],
    output_path: Path,
    duration_sec: float = 0.0,
    on_progress: Callable[[float], None] | None = None,
) -> Path:
    """Losslessly concatenate multiple video files (e.g., GoPro chapters).

    Uses the ffmpeg concat demuxer — no re-encoding.
    """
    ffmpeg = _find_binary("ffmpeg")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for path in file_list:
            # ffmpeg concat format requires escaped single quotes
            escaped = str(path).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
        concat_file = f.name

    try:
        cmd = [
            ffmpeg,
            "-y",
            "-nostdin",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            "-progress", "pipe:1",
            str(output_path),
        ]
        run_with_progress(cmd, duration_sec, on_progress, "ffmpeg concat failed")
    finally:
        Path(concat_file).unlink(missing_ok=True)

    return output_path


def extract_thumbnail(
    path: Path,
    output_path: Path,
    timestamp: str = "00:00:01",
) -> Path:
    """Extract a single frame from a video as a JPEG thumbnail."""
    ffmpeg = _find_binary("ffmpeg")
    cmd = [
        ffmpeg,
        "-y",
        "-nostdin",
        "-hide_banner",
        "-loglevel", "error",
        "-ss", timestamp,
        "-i", str(path),
        "-vframes", "1",
        "-q:v", "5",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"Thumbnail extraction failed: {result.stderr}")
    return output_path


# ffmpeg progress output parsing

_TIME_RE = re.compile(r"out_time_us=(\d+)")


def run_with_progress(
    cmd: list[str],
    duration_sec: float,
    on_progress: Callable[[float], None] | None,
    error_prefix: str,
) -> None:
    """Run ffmpeg, drain combined output, and parse progress without blocking."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    duration_us = duration_sec * 1_000_000
    output_tail: deque[str] = deque(maxlen=80)

    if proc.stdout is not None:
        for line in proc.stdout:
            output_tail.append(line)
            match = _TIME_RE.search(line)
            if match and on_progress and duration_us > 0:
                time_us = int(match.group(1))
                pct = min(100.0, (time_us / duration_us) * 100.0)
                on_progress(pct)

    return_code = proc.wait()
    if return_code != 0:
        output = "".join(output_tail).strip()
        detail = f": {output}" if output else ""
        raise RuntimeError(f"{error_prefix}{detail}")


def _parse_progress(
    lines,
    duration_sec: float,
    on_progress: Callable[[float], None],
) -> None:
    """Parse ffmpeg -progress lines and call on_progress with 0.0-100.0."""
    duration_us = duration_sec * 1_000_000
    if duration_us <= 0:
        return
    for line in lines:
        match = _TIME_RE.search(line)
        if match:
            time_us = int(match.group(1))
            pct = min(100.0, (time_us / duration_us) * 100.0)
            on_progress(pct)
