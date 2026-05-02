"""Directory scanner: detect camera files, extract metadata, group recordings."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from clipwright.core import ffmpeg
from clipwright.core.mediafile import CameraType, FileRole, MediaFile, Recording

# GoPro naming: G[H|L|X]NNCCCC.EXT
# H = high-res video, L = low-res proxy, X = chaptered (older models)
# NN = chapter number (01 = first), CCCC = clip ID
_GOPRO_RE = re.compile(
    r"^G([HLXT])(\d{2})(\d{4})\.(MP4|LRV|THM|WAV)$", re.IGNORECASE
)

# DJI Action 4 naming: DJI_NNNN.MP4 or DJI_20240101_123456_NNNN.MP4
_DJI_RE = re.compile(
    r"^DJI_(?:(\d{8}_\d{6})_)?(\d{4})\.(MP4|mp4)$"
)

# File extensions we care about
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".mts", ".m2ts", ".webm"}
_SIDECAR_EXTS = {".lrv", ".thm", ".wav"}
_ALL_EXTS = _VIDEO_EXTS | _SIDECAR_EXTS


def scan_directory(
    path: Path,
    on_file_scanned: callable = None,
) -> list[Recording]:
    """Scan a directory and return grouped recordings.

    Args:
        path: Directory to scan.
        on_file_scanned: Optional callback(filename, index, total) for progress.
    """
    all_files = sorted(_iter_supported_files(path))
    return scan_files(all_files, on_file_scanned=on_file_scanned)


def scan_paths(
    paths: list[Path],
    on_file_scanned: callable = None,
) -> list[Recording]:
    """Scan explicit files and/or folders and return grouped recordings."""
    all_files: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        candidates = _iter_supported_files(path) if path.is_dir() else [path]
        for candidate in candidates:
            if not candidate.is_file() or candidate.suffix.lower() not in _ALL_EXTS:
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            all_files.append(candidate)

    return scan_files(sorted(all_files), on_file_scanned=on_file_scanned)


def scan_files(
    files: list[Path],
    on_file_scanned: callable = None,
) -> list[Recording]:
    """Scan an explicit list of media files and return grouped recordings."""
    all_files = [
        f for f in files
        if f.is_file() and f.suffix.lower() in _ALL_EXTS
    ]

    if not all_files:
        return []

    media_files: list[MediaFile] = []
    for i, filepath in enumerate(all_files):
        if on_file_scanned:
            on_file_scanned(filepath.name, i, len(all_files))

        mf = _build_media_file(filepath)
        media_files.append(mf)

    return _group_into_recordings(media_files)


def _iter_supported_files(path: Path):
    return (
        f for f in path.iterdir()
        if f.is_file() and f.suffix.lower() in _ALL_EXTS
    )


def _build_media_file(filepath: Path) -> MediaFile:
    """Create a MediaFile from a path, detecting camera and probing metadata."""
    camera, file_role, chapter_num, clip_id = _detect_from_filename(filepath.name)

    mf = MediaFile(
        path=filepath,
        camera=camera,
        file_role=file_role,
        chapter_number=chapter_num,
        clip_id=clip_id,
        size_bytes=filepath.stat().st_size,
    )

    # Only probe video files for full metadata
    if file_role == FileRole.VIDEO:
        _apply_probe_data(mf)

    return mf


def _detect_from_filename(filename: str) -> tuple[CameraType, FileRole, int, str]:
    """Detect camera type, file role, chapter number, and clip ID from filename."""

    # Try GoPro pattern
    m = _GOPRO_RE.match(filename)
    if m:
        letter, chapter_str, clip_id, ext = m.groups()
        ext_lower = ext.lower()
        if ext_lower == "mp4":
            role = FileRole.VIDEO
        elif ext_lower == "lrv":
            role = FileRole.LRV
        elif ext_lower == "thm":
            role = FileRole.THM
        elif ext_lower == "wav":
            role = FileRole.AUDIO_SIDECAR
        else:
            role = FileRole.VIDEO
        return CameraType.GOPRO, role, int(chapter_str), clip_id

    # Try DJI pattern
    m = _DJI_RE.match(filename)
    if m:
        _datetime_str, clip_num, _ext = m.groups()
        return CameraType.DJI_ACTION4, FileRole.VIDEO, 1, clip_num

    # Unknown camera — treat as video if it's a video extension
    suffix = Path(filename).suffix.lower()
    if suffix in _VIDEO_EXTS:
        role = FileRole.VIDEO
    elif suffix in _SIDECAR_EXTS:
        role = FileRole.AUDIO_SIDECAR if suffix == ".wav" else FileRole.LRV
    else:
        role = FileRole.VIDEO

    # Use stem as clip ID for unknown files
    return CameraType.UNKNOWN, role, 1, Path(filename).stem


def _apply_probe_data(mf: MediaFile) -> None:
    """Run ffprobe and populate metadata fields on a MediaFile."""
    try:
        data = ffmpeg.probe(mf.path)
    except (RuntimeError, FileNotFoundError):
        return

    # Extract from streams
    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type")
        if codec_type == "video" and mf.video_codec is None:
            mf.video_codec = stream.get("codec_name")
            width = int(stream.get("width", 0))
            height = int(stream.get("height", 0))
            mf.resolution = (width, height)
            # Parse framerate from r_frame_rate (e.g., "60000/1001")
            r_fps = stream.get("r_frame_rate", "0/1")
            try:
                num, den = r_fps.split("/")
                mf.framerate = round(int(num) / int(den), 2)
            except (ValueError, ZeroDivisionError):
                pass
        elif codec_type == "audio" and mf.audio_codec is None:
            mf.audio_codec = stream.get("codec_name")

    # Extract format-level info
    fmt = data.get("format", {})
    try:
        mf.duration_sec = float(fmt.get("duration", 0))
    except (ValueError, TypeError):
        pass

    # Try to get recording date from format tags
    tags = fmt.get("tags", {})
    date_str = tags.get("creation_time") or tags.get("date") or ""
    if date_str:
        mf.recording_date = _parse_date(date_str)

    # Camera detection fallback from metadata
    if mf.camera == CameraType.UNKNOWN:
        make = (tags.get("make", "") + " " + tags.get("encoder", "")).lower()
        if "gopro" in make:
            mf.camera = CameraType.GOPRO
        elif "dji" in make:
            mf.camera = CameraType.DJI_ACTION4


def _parse_date(date_str: str) -> datetime | None:
    """Try to parse a date string from video metadata."""
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _group_into_recordings(files: list[MediaFile]) -> list[Recording]:
    """Group MediaFiles into Recording objects.

    GoPro files are grouped by clip_id (chapters merged).
    DJI and unknown files each become their own Recording.
    """
    gopro_groups: dict[str, dict] = {}
    recordings: list[Recording] = []

    for mf in files:
        if mf.camera == CameraType.GOPRO:
            if mf.clip_id not in gopro_groups:
                gopro_groups[mf.clip_id] = {"chapters": [], "sidecars": []}
            if mf.file_role == FileRole.VIDEO:
                gopro_groups[mf.clip_id]["chapters"].append(mf)
            else:
                gopro_groups[mf.clip_id]["sidecars"].append(mf)
        else:
            # Non-GoPro: each video is its own recording
            if mf.file_role == FileRole.VIDEO:
                recordings.append(Recording(
                    clip_id=mf.clip_id,
                    camera=mf.camera,
                    chapters=[mf],
                ))

    # Build GoPro recordings from groups
    for clip_id, group in gopro_groups.items():
        chapters = sorted(group["chapters"], key=lambda f: f.chapter_number)
        if not chapters:
            continue
        recordings.append(Recording(
            clip_id=clip_id,
            camera=CameraType.GOPRO,
            chapters=chapters,
            sidecars=group["sidecars"],
        ))

    # Sort by first file's recording date or name
    recordings.sort(key=lambda r: (
        r.recording_date or datetime.min,
        r.primary_file.path.name,
    ))

    return recordings
