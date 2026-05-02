"""Application configuration using QSettings."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSettings


_DEFAULTS = {
    "output_dir": "",
    "output_mode": "same_folder",  # same_folder, subfolder, custom
    "output_subfolder": "converted",
    "output_suffix": "_pcm",
    "conflict_policy": "rename",  # rename, overwrite
    "parallel_jobs": 2,
    "open_output_folder": "false",
    "thumbnail_cache_mb": 200,
    "last_open_dir": "",
    "rename_template": "{date}_{camera}_{clip_id}",
}


class Config:
    """Persistent application settings backed by QSettings."""

    def __init__(self):
        self._settings = QSettings("clipwright", "clipwright")

    def get(self, key: str) -> str:
        return str(self._settings.value(key, _DEFAULTS.get(key, "")))

    def get_int(self, key: str) -> int:
        try:
            return int(self._settings.value(key, _DEFAULTS.get(key, 0)))
        except (ValueError, TypeError):
            return int(_DEFAULTS.get(key, 0))

    def get_path(self, key: str) -> Path | None:
        val = self.get(key)
        return Path(val) if val else None

    def set(self, key: str, value) -> None:
        self._settings.setValue(key, value)

    def sync(self) -> None:
        self._settings.sync()
