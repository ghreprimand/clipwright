"""Template-based batch file renaming."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from clipwright.core.mediafile import Recording


# Default template tokens
AVAILABLE_TOKENS = {
    "date": "Recording date (YYYY-MM-DD)",
    "time": "Recording time (HH-MM-SS)",
    "datetime": "Recording date and time (YYYY-MM-DD_HH-MM-SS)",
    "camera": "Camera name (gopro / dji_action4)",
    "clip_id": "Original clip ID",
    "resolution": "Resolution (e.g. 3840x2160)",
    "fps": "Framerate (e.g. 60)",
    "duration": "Duration in seconds",
    "index": "Sequential number in batch",
    "original": "Original filename without extension",
}


@dataclass
class RenamePreview:
    """Preview of a rename operation before executing."""

    source: Path
    destination: Path
    recording: Recording


def preview_rename(
    recordings: list[Recording],
    template: str,
    output_dir: Path | None = None,
    start_index: int = 1,
    custom_fields: dict[str, str] | None = None,
) -> list[RenamePreview]:
    """Generate rename previews without actually renaming.

    Args:
        recordings: Recordings to rename.
        template: Template string like "{date}_{camera}_{index:03d}".
        output_dir: If set, renamed files go here. Otherwise, renamed in-place.
        start_index: Starting number for {index} token.
        custom_fields: Extra key-value pairs available in the template.

    Returns:
        List of RenamePreview showing what would happen.
    """
    previews = []
    for i, rec in enumerate(recordings):
        source = rec.primary_file.path
        tokens = _build_tokens(rec, i + start_index, custom_fields)
        try:
            new_stem = template.format_map(SafeDict(tokens))
        except (KeyError, ValueError):
            new_stem = source.stem  # fallback to original on template error

        # Sanitize filename
        new_stem = _sanitize_filename(new_stem)
        ext = source.suffix
        dest_dir = output_dir if output_dir else source.parent
        destination = dest_dir / f"{new_stem}{ext}"

        previews.append(RenamePreview(
            source=source,
            destination=destination,
            recording=rec,
        ))

    return previews


def execute_rename(
    previews: list[RenamePreview],
    copy: bool = False,
) -> list[Path]:
    """Execute rename operations from previews.

    Args:
        previews: List of RenamePreview from preview_rename().
        copy: If True, copy files instead of moving them.

    Returns:
        List of destination paths.
    """
    results = []
    for preview in previews:
        preview.destination.parent.mkdir(parents=True, exist_ok=True)
        if copy:
            shutil.copy2(preview.source, preview.destination)
        else:
            preview.source.rename(preview.destination)
        results.append(preview.destination)
    return results


def _build_tokens(
    rec: Recording,
    index: int,
    custom_fields: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build the token dictionary for template formatting."""
    mf = rec.primary_file
    tokens = {
        "camera": rec.camera.value,
        "clip_id": rec.clip_id,
        "resolution": mf.resolution_str,
        "fps": str(int(mf.framerate)) if mf.framerate else "0",
        "duration": str(int(mf.duration_sec)),
        "index": index,
        "original": mf.path.stem,
    }

    if mf.recording_date:
        tokens["date"] = mf.recording_date.strftime("%Y-%m-%d")
        tokens["time"] = mf.recording_date.strftime("%H-%M-%S")
        tokens["datetime"] = mf.recording_date.strftime("%Y-%m-%d_%H-%M-%S")
    else:
        tokens["date"] = "unknown-date"
        tokens["time"] = "unknown-time"
        tokens["datetime"] = "unknown-datetime"

    if custom_fields:
        tokens.update(custom_fields)

    return tokens


def _sanitize_filename(name: str) -> str:
    """Remove characters that are problematic in filenames."""
    # Replace path separators and other problematic chars
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    # Collapse multiple underscores/spaces
    name = re.sub(r"[_\s]+", "_", name)
    return name.strip("_. ")


class SafeDict(dict):
    """Dict that returns the key placeholder for missing keys instead of raising."""

    def __missing__(self, key):
        return f"{{{key}}}"
