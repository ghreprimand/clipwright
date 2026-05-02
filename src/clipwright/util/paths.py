"""XDG path helpers and temp directory management."""

from __future__ import annotations

import os
from pathlib import Path


def cache_dir() -> Path:
    """Return the app's cache directory (~/.cache/clipwright/)."""
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    d = base / "clipwright"
    d.mkdir(parents=True, exist_ok=True)
    return d


def thumbnail_cache_dir() -> Path:
    """Return the thumbnail cache directory."""
    d = cache_dir() / "thumbnails"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_dir() -> Path:
    """Return the app's config directory (~/.config/clipwright/)."""
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / "clipwright"
    d.mkdir(parents=True, exist_ok=True)
    return d
