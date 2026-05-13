"""File panel — tree view of scanned recordings with checkboxes."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, QRunnable, QRectF, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QAction, QDragEnterEvent, QDragMoveEvent, QDropEvent, QPainter, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
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


class EmptyStateWidget(QFrame):
    """Prominent empty-state placeholder shown when no recordings are loaded.

    Displays a centered, visually engaging message with a camera icon,
    primary instructions, and secondary tips — far more inviting than a
    single-line status bar.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._icon_size = 48
        self._drawn = False
        self._setup_ui()
        self._init_style()

    def _init_style(self):
        """Configure the frame's alignment and shape."""
        # Alignment handled by layout alignment and stretch
        self.setFrameShape(QFrame.Shape.NoFrame)

    # ---- Painting a simple camera icon ----

    def _paint_icon(self, painter: QPainter, rect: QRectF):
        """Draw a minimal camera outline icon in the top area."""
        cx = rect.center().x()
        top_y = rect.top() + (rect.height() * 0.06)
        w, h = self._icon_size, self._icon_size * 0.75

        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
        )

        # Camera body
        painter.setPen(QColor("#b0bec5"))
        painter.setBrush(QColor(255, 255, 255, 0))
        body_w = w
        body_h = h * 0.7
        body_x = cx - body_w / 2
        body_y = top_y + h * 0.15
        r = 4
        painter.drawRoundedRect(
            body_x, body_y, body_w, body_h, r, r
        )

        # Top bump (viewfinder)
        bump_w = w * 0.35
        bump_h = h * 0.3
        painter.drawRoundedRect(
            cx - bump_w / 2, top_y, bump_w, bump_h, 3, 3
        )

        # Lens circle
        lens_r = w * 0.17
        painter.setPen(QColor("#78909c"))
        painter.drawEllipse(
            int(cx - lens_r), int(body_y + body_h * 0.15),
            int(lens_r * 2), int(lens_r * 2),
        )

        # Lens highlight
        hl_r = lens_r * 0.35
        painter.setPen(QColor("#90a4ae"))
        painter.drawEllipse(
            int(cx - hl_r + 2), int(body_y + body_h * 0.15 - 2),
            int(hl_r * 2), int(hl_r * 2),
        )

    def paintEvent(self, event):
        # Custom QPainter painting is incompatible with Qt6 Wayland backing store.
        # The widget's label-based UI (emoji icon, main_label, secondary_label)
        # provides all the visual content we need.
        super().paintEvent(event)

    # ---- UI ----

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon area
        self.icon_label = QLabel("📁")
        self.icon_label.setFixedSize(self._icon_size + 16, self._icon_size + 16)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet(
            "font-size: 36px; background: transparent;"
        )
        layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Main instruction
        self.main_label = QLabel("Drop video files here to get started")
        self.main_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #37474f; background: transparent;"
        )
        self.main_label.setWordWrap(True)
        layout.addWidget(self.main_label)

        # Subtext
        self.sub_label = QLabel(
            "Supports MP4, MOV, MTS, MP3 and other common media formats"
        )
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setStyleSheet(
            "font-size: 12px; color: #78909c; background: transparent;"
        )
        self.sub_label.setWordWrap(True)
        layout.addWidget(self.sub_label)

        # Tip row
        self.tip_label = QLabel(
            "💡 "
            "Drag-and-drop • File → Add Files (Ctrl+O) • File → Add Folder (Ctrl+Shift+O)"
        )
        self.tip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tip_label.setStyleSheet(
            "font-size: 11px; color: #90a4ae; background: transparent;"
        )
        self.tip_label.setWordWrap(True)
        layout.addWidget(self.tip_label)

        # Add stretch below so the content sits centered vertically
        layout.addStretch(1)

    def show(self):
        super().show()
        self._drawn = True
        self.update()


class DropZoneOverlay(QFrame):
    """Highlighted overlay shown during drag-overs when empty.

    When the user drags files over the file panel while it's empty,
    a translucent green highlight appears to confirm the drop zone.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._highlighted = False
        self.setStyleSheet("""
            DropZoneOverlay {
                background: rgba(33, 150, 243, 0.08);
                border: 3px dashed rgba(33, 150, 243, 0.45);
                border-radius: 6px;
            }
        """)
        self.hide()

    def highlight(self):
        if not self._highlighted:
            self._highlighted = True
            self.show()

    def unhighlight(self):
        if self._highlighted:
            self._highlighted = False
            self.hide()


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

        # Container that holds tree + overlay — so overlay can sit on top
        self._tree_container = QWidget()
        self._tree_layout = QVBoxLayout(self._tree_container)
        self._tree_layout.setContentsMargins(0, 0, 0, 0)
        self._tree_layout.setSpacing(0)

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

        self._tree_layout.addWidget(self.tree)

        # Empty state widget (shown when no recordings)
        self.empty_state = EmptyStateWidget()
        self.empty_state.hide()
        self._tree_layout.addWidget(self.empty_state)

        # Drop-zone overlay (shown during drags when empty)
        self._drop_overlay = DropZoneOverlay()
        self._drop_overlay.setParent(self._tree_container)
        self._drop_overlay.hide()

        layout.addWidget(self._tree_container)

        # Show empty state initially
        self.empty_state.show()

        # Install event filter on the viewport for drag highlighting
        self.tree.viewport().installEventFilter(self)

    # ---- Empty-state visibility ----

    def _set_empty(self, empty: bool):
        """Show or hide the empty-state widget and overlay."""
        self.empty_state.setVisible(empty)
        self.scan_progress.hide()
        if empty:
            self.header_label.setText(
                "Drop video files or folders here"
            )
            self.header_label.setStyleSheet(
                "font-weight: bold; font-size: 13px; color: #546e7a; font-style: italic;"
            )
        else:
            self.header_label.setStyleSheet("font-weight: bold; font-size: 13px;")

    def _position_drop_overlay(self):
        """Make the overlay fill the tree viewport area."""
        if not self.empty_state.isVisible():
            self._drop_overlay.hide()
            return
        vp = self.tree.viewport()
        rect = vp.geometry()
        self._drop_overlay.setGeometry(rect)

    # ---- Drag-and-drop ----

    def _on_tree_drag_enter(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            if self.empty_state.isVisible():
                self._drop_overlay.highlight()
                self._position_drop_overlay()

    def _on_tree_drag_move(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _on_tree_drag_leave(self, _event):
        self._drop_overlay.unhighlight()

    def _on_tree_drop(self, event: QDropEvent):
        self._drop_overlay.unhighlight()
        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if paths:
            self.load_paths(paths, append=True, label=f"Adding {len(paths)} item(s)...")
            event.acceptProposedAction()

    # ---- Public API ----

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
        self._set_empty(False)
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

        self._position_drop_overlay()

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
        self._set_empty(True)
        self.recordings_loaded.emit(0)

    def _row_selected_recordings(self) -> list[Recording]:
        row_selected: list[Recording] = []
        for item in self.tree.selectedItems():
            rec = item.data(0, Qt.ItemDataRole.UserRole)
            if rec and rec not in row_selected:
                row_selected.append(rec)
        return row_selected

    # ---- Event filter for drag highlighting ----

    def eventFilter(self, watched, event):
        if watched is self.tree.viewport():
            etype = event.type()
            if etype == QEvent.Type.DragEnter:
                self._on_tree_drag_enter(event)
                return True
            if etype == QEvent.Type.DragMove:
                self._on_tree_drag_move(event)
                return True
            if etype == QEvent.Type.DragLeave:
                self._on_tree_drag_leave(event)
                return True
            if etype == QEvent.Type.Drop:
                self._on_tree_drop(event)
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
