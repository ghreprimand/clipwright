"""Application entry point."""

from __future__ import annotations

import signal
import sys
import traceback

from PyQt6.QtCore import QThreadPool
from PyQt6.QtWidgets import QApplication

from clipwright import __version__
from clipwright.ui.mainwindow import MainWindow
from clipwright.util.config import Config
from clipwright.util.paths import cache_dir


_crash_log = None


def _enable_crash_logging():
    """Write Python tracebacks to a stable user-readable log file."""
    global _crash_log

    log_path = cache_dir() / "clipwright-crash.log"
    _crash_log = log_path.open("a", encoding="utf-8")
    sys.stderr = _crash_log

    try:
        import faulthandler

        faulthandler.enable(file=_crash_log, all_threads=True)
    except Exception:
        pass

    original_hook = sys.excepthook

    def log_exception(exc_type, exc_value, exc_traceback):
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=_crash_log)
        _crash_log.flush()
        original_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = log_exception


def main():
    if "--version" in sys.argv or "-V" in sys.argv:
        print(f"Clipwright {__version__}")
        sys.exit(0)

    _enable_crash_logging()

    # Allow Ctrl+C from terminal to kill the app
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName("Clipwright")
    app.setOrganizationName("clipwright")
    app.setApplicationVersion(__version__)

    config = Config()
    window = MainWindow(config)
    window.show()

    exit_code = app.exec()

    # Wait for any running background jobs to finish (up to 5s)
    QThreadPool.globalInstance().waitForDone(5000)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
