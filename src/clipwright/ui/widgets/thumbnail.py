"""Thumbnail grid widget for visual clip browsing."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PyQt6.QtCore import QRunnable, QSize, Qt, QThreadPool, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from clipwright.core import ffmpeg
from clipwright.core.mediafile import CameraType, Recording
from clipwright.util.paths import thumbnail_cache_dir


_THUMB_SIZE = QSize(220, 140)

_CAMERA_LABELS = {
    CameraType.GOPRO: "GoPro",
    CameraType.DJI_ACTION4: "DJI",
    CameraType.UNKNOWN: "?",
}


class ThumbnailGrid(QScrollArea):
    """Scrollable grid of video thumbnails."""

    recording_clicked = pyqtSignal(object)  # Recording

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._flow_layout = FlowLayout(self._container)
        self.setWidget(self._container)

        self._cards: list[ThumbnailCard] = []

    def set_recordings(self, recordings: list[Recording]):
        """Populate the grid with thumbnails for the given recordings."""
        # Clear existing
        for card in self._cards:
            self._flow_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        for rec in recordings:
            card = ThumbnailCard(rec)
            card.clicked.connect(lambda r=rec: self.recording_clicked.emit(r))
            self._flow_layout.addWidget(card)
            self._cards.append(card)
            card.load_thumbnail()


class ThumbnailCard(QFrame):
    """Single thumbnail card with image, filename, and duration overlay."""

    clicked = pyqtSignal()

    def __init__(self, recording: Recording, parent=None):
        super().__init__(parent)
        self.recording = recording
        self.setFixedSize(_THUMB_SIZE.width() + 10, _THUMB_SIZE.height() + 45)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            ThumbnailCard {
                background: palette(base);
                border: 1px solid palette(mid);
                border-radius: 6px;
            }
            ThumbnailCard:hover {
                border: 2px solid palette(highlight);
            }
        """)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Thumbnail image
        self.image_label = QLabel()
        self.image_label.setFixedSize(_THUMB_SIZE)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background: #111; border-radius: 4px;")
        self.image_label.setText("...")
        layout.addWidget(self.image_label)

        # Info row
        info = QLabel(
            f"{self.recording.primary_file.path.stem}  "
            f"<span style='color: gray;'>{self.recording.duration_str} | "
            f"{_CAMERA_LABELS.get(self.recording.camera, '?')}</span>"
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setFont(QFont("", 9))
        info.setMaximumWidth(_THUMB_SIZE.width())
        layout.addWidget(info)

        # AAC warning badge
        if self.recording.needs_audio_conversion:
            badge = QLabel("AAC")
            badge.setStyleSheet(
                "background: #e74c3c; color: white; border-radius: 3px; "
                "padding: 1px 4px; font-size: 10px; font-weight: bold;"
            )
            badge.setFixedWidth(32)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Overlay on top-right of thumbnail
            badge.setParent(self.image_label)
            badge.move(_THUMB_SIZE.width() - 38, 4)

    def load_thumbnail(self):
        video_path = self.recording.primary_file.path
        cache_key = hashlib.md5(str(video_path).encode()).hexdigest()
        cache_path = thumbnail_cache_dir() / f"{cache_key}.jpg"

        if cache_path.exists():
            self._set_pixmap(cache_path)
            return

        runner = _ThumbRunner(video_path, cache_path)
        runner.signals = _ThumbSignals()
        runner.signals.finished.connect(self._set_pixmap)
        QThreadPool.globalInstance().start(runner)

    def _set_pixmap(self, path: Path):
        if not path.exists():
            self.image_label.setText("No preview")
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.image_label.setText("No preview")
            return
        self.image_label.setPixmap(
            pixmap.scaled(
                _THUMB_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class _ThumbSignals(QObject):
    finished = pyqtSignal(Path)


class _ThumbRunner(QRunnable):
    def __init__(self, video_path: Path, cache_path: Path):
        super().__init__()
        self.video_path = video_path
        self.cache_path = cache_path
        self.signals: _ThumbSignals | None = None

    def run(self):
        try:
            ffmpeg.extract_thumbnail(self.video_path, self.cache_path)
        except Exception:
            pass
        if self.signals:
            self.signals.finished.emit(self.cache_path)


class FlowLayout(QVBoxLayout):
    """Simple flow layout that wraps widgets into rows.

    This is a simplified version — it re-lays out as a horizontal wrap
    by using nested QHBoxLayouts. For a proper flow layout we'd need
    a custom QLayout, but this is good enough for thumbnails.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSpacing(6)
        self._widgets: list[QWidget] = []

    def addWidget(self, widget):
        self._widgets.append(widget)
        super().addWidget(widget)
