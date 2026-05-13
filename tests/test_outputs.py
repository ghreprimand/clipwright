from pathlib import Path

from clipwright.core.outputs import resolve_output_path


def test_resolve_output_path_uses_requested_path_when_available(tmp_path: Path):
    target = tmp_path / "clip.mov"

    assert resolve_output_path(target) == target


def test_resolve_output_path_renames_existing_file(tmp_path: Path):
    target = tmp_path / "clip.mov"
    target.write_text("existing")

    assert resolve_output_path(target) == tmp_path / "clip-1.mov"


def test_resolve_output_path_honors_reserved_paths(tmp_path: Path):
    target = tmp_path / "clip.mov"
    reserved = {target.resolve(), (tmp_path / "clip-1.mov").resolve()}

    assert resolve_output_path(target, reserved=reserved) == tmp_path / "clip-2.mov"


def test_resolve_output_path_allows_overwrite(tmp_path: Path):
    target = tmp_path / "clip.mov"
    target.write_text("existing")

    assert resolve_output_path(target, conflict_policy="overwrite") == target
