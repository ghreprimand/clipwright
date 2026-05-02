"""Transcode preset profiles — save and load named transcode configurations."""

from __future__ import annotations

import json
from pathlib import Path

from clipwright.core.transcoder import (
    AudioCodec,
    Container,
    TranscodeSettings,
    VideoCodec,
)
from clipwright.util.paths import config_dir


_PRESETS_FILE = "transcode_presets.json"

# Built-in presets that are always available
BUILTIN_PRESETS: dict[str, TranscodeSettings] = {
    "Linux Editing (MOV + PCM Audio)": TranscodeSettings(
        video_codec=VideoCodec.COPY,
        audio_codec=AudioCodec.PCM,
        container=Container.MOV,
    ),
    "Sharing Copy (1080p H.264)": TranscodeSettings(
        video_codec=VideoCodec.H264,
        audio_codec=AudioCodec.AAC,
        container=Container.MP4,
        resolution=(1920, 1080),
        crf=23,
        speed_preset="medium",
        audio_bitrate="192k",
    ),
    "Sharing Copy (720p H.264)": TranscodeSettings(
        video_codec=VideoCodec.H264,
        audio_codec=AudioCodec.AAC,
        container=Container.MP4,
        resolution=(1280, 720),
        crf=23,
        speed_preset="medium",
        audio_bitrate="128k",
    ),
    "Small File (1080p H.265)": TranscodeSettings(
        video_codec=VideoCodec.H265,
        audio_codec=AudioCodec.AAC,
        container=Container.MP4,
        resolution=(1920, 1080),
        crf=26,
        speed_preset="medium",
        audio_bitrate="128k",
    ),
    "Archive (H.265 High Quality)": TranscodeSettings(
        video_codec=VideoCodec.H265,
        audio_codec=AudioCodec.AAC,
        container=Container.MKV,
        resolution=None,
        crf=18,
        speed_preset="slow",
        audio_bitrate="256k",
    ),
    "ProRes Proxy": TranscodeSettings(
        video_codec=VideoCodec.PRORES,
        audio_codec=AudioCodec.PCM,
        container=Container.MOV,
        resolution=None,
        prores_profile=0,
    ),
    "ProRes HQ": TranscodeSettings(
        video_codec=VideoCodec.PRORES,
        audio_codec=AudioCodec.PCM,
        container=Container.MOV,
        resolution=None,
        prores_profile=3,
    ),
    "DNxHR HQ": TranscodeSettings(
        video_codec=VideoCodec.DNXHD,
        audio_codec=AudioCodec.PCM,
        container=Container.MOV,
        resolution=None,
    ),
}


def _presets_path() -> Path:
    return config_dir() / _PRESETS_FILE


def _settings_to_dict(s: TranscodeSettings) -> dict:
    return {
        "video_codec": s.video_codec,
        "audio_codec": s.audio_codec,
        "container": s.container,
        "resolution": list(s.resolution) if s.resolution else None,
        "crf": s.crf,
        "target_bitrate": s.target_bitrate,
        "speed_preset": s.speed_preset,
        "prores_profile": s.prores_profile,
        "audio_bitrate": s.audio_bitrate,
    }


def _dict_to_settings(d: dict) -> TranscodeSettings:
    res = d.get("resolution")
    return TranscodeSettings(
        video_codec=d.get("video_codec", VideoCodec.H264),
        audio_codec=d.get("audio_codec", AudioCodec.AAC),
        container=d.get("container", Container.MP4),
        resolution=tuple(res) if res else None,
        crf=d.get("crf", 23),
        target_bitrate=d.get("target_bitrate"),
        speed_preset=d.get("speed_preset", "medium"),
        prores_profile=d.get("prores_profile", 2),
        audio_bitrate=d.get("audio_bitrate", "192k"),
    )


def load_user_presets() -> dict[str, TranscodeSettings]:
    """Load user-saved presets from disk."""
    path = _presets_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return {name: _dict_to_settings(d) for name, d in data.items()}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def save_user_preset(name: str, settings: TranscodeSettings) -> None:
    """Save a preset to disk."""
    presets = load_user_presets()
    presets[name] = settings
    path = _presets_path()
    data = {n: _settings_to_dict(s) for n, s in presets.items()}
    path.write_text(json.dumps(data, indent=2))


def delete_user_preset(name: str) -> None:
    """Delete a user preset."""
    presets = load_user_presets()
    presets.pop(name, None)
    path = _presets_path()
    data = {n: _settings_to_dict(s) for n, s in presets.items()}
    path.write_text(json.dumps(data, indent=2))


def get_all_presets() -> dict[str, TranscodeSettings]:
    """Return all presets: built-in + user-saved."""
    all_presets = dict(BUILTIN_PRESETS)
    all_presets.update(load_user_presets())
    return all_presets
