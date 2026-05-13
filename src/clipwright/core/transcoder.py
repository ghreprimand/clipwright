"""Video transcoding — resolution, codec, and quality conversion (like Handbrake)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from clipwright.core import ffmpeg


class VideoCodec:
    H264 = "libx264"
    H265 = "libx265"
    PRORES = "prores_ks"
    DNXHD = "dnxhd"
    COPY = "copy"


class AudioCodec:
    PCM = "pcm_s16le"
    AAC = "aac"
    COPY = "copy"
    NONE = "none"


class Container:
    MOV = ".mov"
    MP4 = ".mp4"
    MKV = ".mkv"


# Common resolution presets
RESOLUTION_PRESETS = {
    "Original": None,
    "4K (3840x2160)": (3840, 2160),
    "2.7K (2704x1520)": (2704, 1520),
    "1080p (1920x1080)": (1920, 1080),
    "720p (1280x720)": (1280, 720),
    "480p (854x480)": (854, 480),
}

# Quality presets for CRF-based encoding (lower = better quality, bigger file)
QUALITY_PRESETS = {
    "Lossless": 0,
    "Very High (visually lossless)": 16,
    "High": 20,
    "Medium": 23,
    "Low (smaller file)": 28,
    "Very Low (much smaller)": 32,
}

# Encoding speed presets for x264/x265
SPEED_PRESETS = [
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
]

# ProRes profile presets
PRORES_PROFILES = {
    "Proxy": 0,
    "LT": 1,
    "Standard": 2,
    "HQ": 3,
    "4444": 4,
}


@dataclass
class TranscodeSettings:
    """Configuration for a transcode job."""

    video_codec: str = VideoCodec.H264
    audio_codec: str = AudioCodec.AAC
    container: str = Container.MP4

    # Resolution: None = keep original
    resolution: tuple[int, int] | None = None

    # Quality: CRF value for x264/x265, ignored for ProRes/DNxHD
    crf: int = 23

    # Bitrate mode: if set, uses target bitrate instead of CRF
    target_bitrate: str | None = None  # e.g. "20M", "5000k"

    # Encoding speed preset for x264/x265
    speed_preset: str = "medium"

    # ProRes profile (only used when video_codec is prores)
    prores_profile: int = 2  # Standard

    # Audio bitrate for AAC
    audio_bitrate: str = "192k"

    def build_ffmpeg_args(self) -> list[str]:
        """Build the ffmpeg arguments for this transcode configuration."""
        args = []

        # Video codec
        if self.video_codec == VideoCodec.COPY:
            args.extend(["-c:v", "copy"])
        elif self.video_codec == VideoCodec.H264:
            args.extend(["-c:v", "libx264"])
            args.extend(["-preset", self.speed_preset])
            if self.target_bitrate:
                args.extend(["-b:v", self.target_bitrate])
            else:
                args.extend(["-crf", str(self.crf)])
            args.extend(["-pix_fmt", "yuv420p"])
        elif self.video_codec == VideoCodec.H265:
            args.extend(["-c:v", "libx265"])
            args.extend(["-preset", self.speed_preset])
            if self.target_bitrate:
                args.extend(["-b:v", self.target_bitrate])
            else:
                args.extend(["-crf", str(self.crf)])
            args.extend(["-pix_fmt", "yuv420p"])
            args.extend(["-tag:v", "hvc1"])  # Apple compatibility
        elif self.video_codec == VideoCodec.PRORES:
            args.extend(["-c:v", "prores_ks"])
            args.extend(["-profile:v", str(self.prores_profile)])
            args.extend(["-pix_fmt", "yuv422p10le"])
        elif self.video_codec == VideoCodec.DNXHD:
            args.extend(["-c:v", "dnxhd"])
            args.extend(["-profile:v", "dnxhr_hq"])
            args.extend(["-pix_fmt", "yuv422p"])

        # Resolution scaling
        if self.resolution:
            w, h = self.resolution
            # Use -2 to ensure even dimensions
            args.extend(["-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"])

        # Audio codec
        if self.audio_codec == AudioCodec.COPY:
            args.extend(["-c:a", "copy"])
        elif self.audio_codec == AudioCodec.NONE:
            args.append("-an")
        elif self.audio_codec == AudioCodec.PCM:
            args.extend(["-c:a", "pcm_s16le"])
        elif self.audio_codec == AudioCodec.AAC:
            args.extend(["-c:a", "aac", "-b:a", self.audio_bitrate])

        return args


def transcode(
    input_path: Path,
    output_path: Path,
    settings: TranscodeSettings,
    duration_sec: float = 0.0,
    trim_start: float | None = None,
    trim_end: float | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> Path:
    """Transcode a video file with the given settings.

    Args:
        input_path: Source video file.
        output_path: Destination file path.
        settings: Transcode configuration.
        duration_sec: Total duration for progress calculation.
        trim_start: Optional start time in seconds.
        trim_end: Optional end time in seconds.
        on_progress: Optional callback(percent).

    Returns:
        Path to the output file.
    """
    ffmpeg_bin = ffmpeg._find_binary("ffmpeg")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-nostdin",
        "-hide_banner",
        "-loglevel", "error",
    ]

    # Input seeking (before -i for fast seek)
    if trim_start is not None and trim_start > 0:
        cmd.extend(["-ss", str(trim_start)])

    cmd.extend(["-i", str(input_path)])

    # Output duration limit
    if trim_end is not None:
        actual_duration = trim_end - (trim_start or 0)
        cmd.extend(["-t", str(actual_duration)])
        duration_sec = actual_duration

    # Add codec/quality/resolution args
    cmd.extend(settings.build_ffmpeg_args())

    # Progress output
    cmd.extend(["-progress", "pipe:1"])
    cmd.append(str(output_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg.run_with_progress(cmd, duration_sec, on_progress, "Transcode failed")

    return output_path


def estimate_output_size(
    duration_sec: float,
    settings: TranscodeSettings,
    source_resolution: tuple[int, int] = (1920, 1080),
) -> str:
    """Rough estimate of output file size based on settings.

    Returns a human-readable size string.
    """
    if settings.video_codec == VideoCodec.COPY:
        return "Same as source"

    # Rough bitrate estimates in kbps
    res = settings.resolution or source_resolution
    pixels = res[0] * res[1]
    pixel_ratio = pixels / (1920 * 1080)

    if settings.target_bitrate:
        # Parse the target bitrate
        br = settings.target_bitrate.lower()
        if br.endswith("m"):
            kbps = float(br[:-1]) * 1000
        elif br.endswith("k"):
            kbps = float(br[:-1])
        else:
            kbps = float(br) / 1000
    elif settings.video_codec in (VideoCodec.H264, VideoCodec.H265):
        # CRF-based estimate (very rough)
        base_kbps = 8000 if settings.video_codec == VideoCodec.H264 else 5000
        crf_factor = 2 ** ((23 - settings.crf) / 6)
        kbps = base_kbps * pixel_ratio * crf_factor
    elif settings.video_codec == VideoCodec.PRORES:
        # ProRes is roughly constant bitrate per pixel
        prores_rates = {0: 15, 1: 25, 2: 36, 3: 55, 4: 80}  # Mbps at 1080p
        kbps = prores_rates.get(settings.prores_profile, 36) * 1000 * pixel_ratio
    else:
        kbps = 20000 * pixel_ratio

    # Add audio
    if settings.audio_codec == AudioCodec.PCM:
        kbps += 1536  # 16bit 48khz stereo
    elif settings.audio_codec == AudioCodec.AAC:
        kbps += 192
    elif settings.audio_codec != AudioCodec.NONE:
        kbps += 320

    size_mb = (kbps * duration_sec) / 8 / 1024
    if size_mb > 1024:
        return f"~{size_mb / 1024:.1f} GB"
    return f"~{size_mb:.0f} MB"
