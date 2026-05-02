"""File panel — tree view of scanned recordings with checkboxes."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, QRunnable, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QAction, QDragEnterEvent, QDragMoveEvent, QDropEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QMenu,
    QProgressBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from clipwright.core.mediafile import CameraType, Recording
from clipwright.core.scanner import scan_directory, scan_paths


_CAMERA_LABELS = {
    CameraType.GOPRO: "GoPro",
    CameraType.DJI_ACTION4: "DJI Action 4",
    CameraType.UNKNOWN: "Unknown",
}


class FilePanel(QWidget):
    recording_selected = pyqtSignal(object)  # Recording
    recordings_loaded = pyqtSignal(int)

    # Signals for context menu actions
    convert_requested = pyqtSignal(list)   # list[Recording]
    merge_requested = pyqtSignal(list)     # list[Recording]
    transcode_requested = pyqtSignal(list) # list[Recording]
    trim_requested = pyqtSignal(object)    # Recording
    rename_requested = pyqtSignal(list)    # list[Recording]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.recordings: list[Recording] = []
        self.setAcceptDrops(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.header_label = QLabel("Files")
        self.header_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(self.header_label)

        self.scan_progress = QProgressBar()
        self.scan_progress.setMaximumHeight(16)
        self.scan_progress.hide()
        layout.addWidget(self.scan_progress)

        self.tree = QTreeWidget()
        self.tree.setAcceptDrops(True)
        self.tree.viewport().setAcceptDrops(True)
        self.tree.viewport().installEventFilter(self)
        self.tree.setHeaderLabels(["Name", "Camera", "Duration", "Audio", "Size"])
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)

        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.tree)

    def load_directory(self, path: Path):
        """Scan a directory in a background thread and populate the tree."""
        self.load_paths([path], append=False, label=f"Scanning {path.name}...")

    def load_paths(self, paths: list[Path], append: bool = False, label: str | None = None):
        """Scan files/folders in a background thread and populate or append to the tree."""
        if not append:
            self.tree.clear()
            self.recordings = []
        self.scan_progress.setRange(0, 0)  # indeterminate
        self.scan_progress.show()
        if label:
            self.header_label.setText(label)
        elif len(paths) == 1:
            self.header_label.setText(f"Scanning {paths[0].name}...")
        else:
            self.header_label.setText(f"Scanning {len(paths)} item(s)...")

        runner = ScanRunner(paths, append=append)
        runner.signals = ScanSignals()
        runner.signals.finished.connect(self._on_scan_finished)
        runner.signals.error.connect(self._on_scan_error)
        QThreadPool.globalInstance().start(runner)

    def _on_scan_finished(self, recordings: list, append: bool):
        if append:
            existing = {r.primary_file.path.resolve() for r in self.recordings}
            self.recordings.extend(
                r for r in recordings
                if r.primary_file.path.resolve() not in existing
            )
        else:
            self.recordings = recordings
        self.scan_progress.hide()
        self._populate_tree()
        count = len(self.recordings)
        gopro = sum(1 for r in self.recordings if r.camera == CameraType.GOPRO)
        dji = sum(1 for r in self.recordings if r.camera == CameraType.DJI_ACTION4)
        parts = [f"{count} recording(s)"]
        if gopro:
            parts.append(f"{gopro} GoPro")
        if dji:
            parts.append(f"{dji} DJI")
        self.header_label.setText(" | ".join(parts))
        self.recordings_loaded.emit(count)

    def _on_scan_error(self, error_msg: str):
        self.scan_progress.hide()
        self.header_label.setText(f"Error: {error_msg}")

    def _populate_tree(self):
        self.tree.clear()
        for rec in self.recordings:
            item = QTreeWidgetItem()
            item.setData(0, Qt.ItemDataRole.UserRole, rec)
            item.setCheckState(0, Qt.CheckState.Checked)
            item.setText(0, rec.display_name)
            item.setText(1, _CAMERA_LABELS.get(rec.camera, "Unknown"))
            item.setText(2, rec.duration_str)

            # Audio status
            if rec.needs_audio_conversion:
                item.setText(3, "AAC (needs conversion)")
                item.setForeground(3, Qt.GlobalColor.red)
            else:
                audio = rec.primary_file.audio_codec or "none"
                item.setText(3, audio)

            item.setText(4, rec.primary_file.size_str)

            # Add chapter children for multi-chapter recordings
            if rec.needs_merge:
                for ch in rec.chapters:
                    child = QTreeWidgetItem()
                    child.setText(0, ch.path.name)
                    child.setText(2, ch.duration_str)
                    child.setText(4, ch.size_str)
                    item.addChild(child)

            self.tree.addTopLevelItem(item)

    def _show_context_menu(self, position):
        """Show right-click context menu on file tree items."""
        item = self.tree.itemAt(position)
        if not item:
            return

        rec = item.data(0, Qt.ItemDataRole.UserRole)
        if not rec:
            # Clicked on a chapter child — get parent recording
            parent = item.parent()
            if parent:
                rec = parent.data(0, Qt.ItemDataRole.UserRole)
            if not rec:
                return

        selected = self.get_selected_recordings()
        if not selected:
            selected = [rec]

        menu = QMenu(self)

        # Convert audio
        convert_action = QAction(f"Convert Audio ({len(selected)} file(s))", self)
        convert_action.triggered.connect(lambda: self.convert_requested.emit(selected))
        menu.addAction(convert_action)

        # Merge (only if multi-chapter)
        mergeable = [r for r in selected if r.needs_merge]
        if mergeable:
            merge_action = QAction(f"Merge Chapters ({len(mergeable)} recording(s))", self)
            merge_action.triggered.connect(lambda: self.merge_requested.emit(mergeable))
            menu.addAction(merge_action)

        menu.addSeparator()

        # Transcode
        transcode_action = QAction(f"Transcode ({len(selected)} file(s))...", self)
        transcode_action.triggered.connect(lambda: self.transcode_requested.emit(selected))
        menu.addAction(transcode_action)

        # Trim (single file only)
        trim_action = QAction(f"Quick Trim — {rec.display_name}...", self)
        trim_action.triggered.connect(lambda: self.trim_requested.emit(rec))
        menu.addAction(trim_action)

        menu.addSeparator()

        # Rename
        rename_action = QAction(f"Batch Rename ({len(selected)} file(s))...", self)
        rename_action.triggered.connect(lambda: self.rename_requested.emit(selected))
        menu.addAction(rename_action)

        menu.addSeparator()

        # Open containing folder
        open_folder_action = QAction("Open Containing Folder", self)
        open_folder_action.triggered.connect(
            lambda: self._open_containing_folder(rec)
        )
        menu.addAction(open_folder_action)

        menu.exec(self.tree.viewport().mapToGlobal(position))

    def _open_containing_folder(self, rec):
        import subprocess
        folder = str(rec.primary_file.path.parent)
        subprocess.Popen(["xdg-open", folder])

    def _on_selection_changed(self):
        items = self.tree.selectedItems()
        if items:
            rec = items[0].data(0, Qt.ItemDataRole.UserRole)
            if rec:
                self.recording_selected.emit(rec)

    def get_selected_recordings(self) -> list[Recording]:
        """Return selected rows, falling back to checked recordings."""
        row_selected = self._row_selected_recordings()
        if row_selected:
            return row_selected

        selected = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                rec = item.data(0, Qt.ItemDataRole.UserRole)
                if rec:
                    selected.append(rec)
        return selected

    def select_all(self):
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(0, Qt.CheckState.Checked)

    def select_none(self):
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(0, Qt.CheckState.Unchecked)

    def remove_selected(self):
        selected_paths = {
            r.primary_file.path.resolve()
            for r in self._row_selected_recordings()
        }
        if not selected_paths:
            return
        self.recordings = [
            r for r in self.recordings
            if r.primary_file.path.resolve() not in selected_paths
        ]
        self._populate_tree()
        self.recordings_loaded.emit(len(self.recordings))

    def clear(self):
        self.recordings = []
        self.tree.clear()
        self.header_label.setText("Drop video files or folders here")
        self.recordings_loaded.emit(0)

    def _row_selected_recordings(self) -> list[Recording]:
        row_selected: list[Recording] = []
        for item in self.tree.selectedItems():
            rec = item.data(0, Qt.ItemDataRole.UserRole)
            if rec and rec not in row_selected:
                row_selected.append(rec)
        return row_selected

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if paths:
            self.load_paths(paths, append=True, label=f"Adding {len(paths)} item(s)...")
            event.acceptProposedAction()

    def eventFilter(self, watched, event):
        if watched is self.tree.viewport():
            if event.type() == QEvent.Type.DragEnter and event.mimeData().hasUrls():
                event.acceptProposedAction()
                return True
            if event.type() == QEvent.Type.DragMove and event.mimeData().hasUrls():
                event.acceptProposedAction()
                return True
            if event.type() == QEvent.Type.Drop and event.mimeData().hasUrls():
                self.dropEvent(event)
                return True
        return super().eventFilter(watched, event)


# --- Background scanner ---


class ScanSignals(QObject):
    finished = pyqtSignal(list, bool)
    error = pyqtSignal(str)


class ScanRunner(QRunnable):
    def __init__(self, paths: list[Path], append: bool = False):
        super().__init__()
        self.paths = paths
        self.append = append
        self.signals: ScanSignals | None = None

    def run(self):
        try:
            if len(self.paths) == 1 and self.paths[0].is_dir():
                recordings = scan_directory(self.paths[0])
            else:
                recordings = scan_paths(self.paths)
            if self.signals:
                self.signals.finished.emit(recordings, self.append)
        except Exception as e:
            if self.signals:
                self.signals.error.emit(str(e))
