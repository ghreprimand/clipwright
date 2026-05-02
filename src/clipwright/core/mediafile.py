"""Data models for media files and recordings."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


class CameraType(enum.Enum):
    GOPRO = "gopro"
    DJI_ACTION4 = "dji_action4"
    UNKNOWN = "unknown"


class FileRole(enum.Enum):
    VIDEO = "video"
    LRV = "lrv"  # GoPro low-res proxy
    THM = "thm"  # GoPro thumbnail
    AUDIO_SIDECAR = "audio_sidecar"  # GoPro .WAV


@dataclass
class MediaFile:
    """A single file on disk with its detected metadata."""

    path: Path
    camera: CameraType = CameraType.UNKNOWN
    file_role: FileRole = FileRole.VIDEO
    video_codec: str | None = None
    audio_codec: str | None = None
    resolution: tuple[int, int] = (0, 0)
    framerate: float = 0.0
    duration_sec: float = 0.0
    recording_date: datetime | None = None
    size_bytes: int = 0
    chapter_number: int = 0
    clip_id: str = ""

    @property
    def needs_audio_conversion(self) -> bool:
        """True if this file has AAC audio that some Linux editing workflows can't decode."""
        return self.audio_codec is not None and self.audio_codec.lower() in ("aac", "aac_latm")

    @property
    def display_name(self) -> str:
        return self.path.name

    @property
    def resolution_str(self) -> str:
        if self.resolution == (0, 0):
            return "unknown"
        return f"{self.resolution[0]}x{self.resolution[1]}"

    @property
    def duration_str(self) -> str:
        if self.duration_sec <= 0:
            return "00:00"
        mins, secs = divmod(int(self.duration_sec), 60)
        hours, mins = divmod(mins, 60)
        if hours:
            return f"{hours}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    @property
    def size_str(self) -> str:
        size = self.size_bytes
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


@dataclass
class Recording:
    """One logical recording, possibly spanning multiple GoPro chapter files."""

    clip_id: str
    camera: CameraType
    chapters: list[MediaFile] = field(default_factory=list)
    sidecars: list[MediaFile] = field(default_factory=list)

    @property
    def needs_merge(self) -> bool:
        return len(self.chapters) > 1

    @property
    def needs_audio_conversion(self) -> bool:
        return any(ch.needs_audio_conversion for ch in self.chapters)

    @property
    def total_duration(self) -> float:
        return sum(ch.duration_sec for ch in self.chapters)

    @property
    def total_size(self) -> int:
        return sum(ch.size_bytes for ch in self.chapters)

    @property
    def primary_file(self) -> MediaFile:
        """The first chapter file, used for metadata display."""
        return self.chapters[0]

    @property
    def display_name(self) -> str:
        if self.needs_merge:
            return f"{self.chapters[0].path.stem} ({len(self.chapters)} chapters)"
        return self.chapters[0].path.name

    @property
    def resolution(self) -> tuple[int, int]:
        return self.primary_file.resolution

    @property
    def framerate(self) -> float:
        return self.primary_file.framerate

    @property
    def recording_date(self) -> datetime | None:
        return self.primary_file.recording_date

    @property
    def duration_str(self) -> str:
        dur = self.total_duration
        if dur <= 0:
            return "00:00"
        mins, secs = divmod(int(dur), 60)
        hours, mins = divmod(mins, 60)
        if hours:
            return f"{hours}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"
