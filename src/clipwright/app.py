"""Application entry point."""

from __future__ import annotations

import signal
import sys

from PyQt6.QtCore import QThreadPool
from PyQt6.QtWidgets import QApplication

from clipwright import __version__
from clipwright.ui.mainwindow import MainWindow
from clipwright.util.config import Config


def main():
    if "--version" in sys.argv or "-V" in sys.argv:
        print(f"Clipwright {__version__}")
        sys.exit(0)

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
