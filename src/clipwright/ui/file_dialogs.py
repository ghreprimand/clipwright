"""Qt file dialog helpers.

Clipwright uses non-native dialogs because some Qt/PyQt/Wayland combinations
can segfault while opening native file pickers.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QWidget


def choose_directory(
    parent: QWidget | None,
    title: str,
    start_dir: str | Path | None = None,
) -> str:
    dialog = QFileDialog(parent, title, str(start_dir or Path.home()))
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
    dialog.setFileMode(QFileDialog.FileMode.Directory)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)

    if dialog.exec() != QFileDialog.DialogCode.Accepted:
        return ""

    files = dialog.selectedFiles()
    return files[0] if files else ""


def choose_video_files(
    parent: QWidget | None,
    title: str,
    start_dir: str | Path | None = None,
) -> list[str]:
    dialog = QFileDialog(parent, title, str(start_dir or Path.home()))
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
    dialog.setNameFilter(
        "Video Files (*.mp4 *.mov *.mkv *.avi *.m4v *.mts *.m2ts *.webm);;All Files (*)"
    )
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)

    if dialog.exec() != QFileDialog.DialogCode.Accepted:
        return []

    return dialog.selectedFiles()
