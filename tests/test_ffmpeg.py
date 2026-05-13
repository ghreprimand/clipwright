import sys

import pytest

from clipwright.core.ffmpeg import run_with_progress


def test_run_with_progress_parses_out_time():
    progress = []
    cmd = [
        sys.executable,
        "-c",
        "print('out_time_us=500000'); print('progress=continue')",
    ]

    run_with_progress(cmd, 1.0, progress.append, "failed")

    assert progress == [50.0]


def test_run_with_progress_includes_combined_output_on_failure():
    cmd = [
        sys.executable,
        "-c",
        "import sys; print('bad input', file=sys.stderr); sys.exit(7)",
    ]

    with pytest.raises(RuntimeError, match="failed: bad input"):
        run_with_progress(cmd, 1.0, None, "failed")
