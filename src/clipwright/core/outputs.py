"""Shared output path helpers for media jobs."""

from __future__ import annotations

from pathlib import Path


def resolve_output_path(
    path: Path,
    conflict_policy: str = "rename",
    reserved: set[Path] | None = None,
) -> Path:
    """Return a usable output path for the requested conflict policy."""
    reserved = reserved or set()
    resolved_path = path.resolve()
    if conflict_policy == "overwrite" or (
        not path.exists() and resolved_path not in reserved
    ):
        return path

    stem = path.stem
    suffix = path.suffix
    for i in range(1, 10_000):
        candidate = path.with_name(f"{stem}-{i}{suffix}")
        if not candidate.exists() and candidate.resolve() not in reserved:
            return candidate

    raise RuntimeError(f"Could not find available output filename for {path}")
