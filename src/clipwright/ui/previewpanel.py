"""Preview panel — metadata display and thumbnail for selected recording."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PyQt6.QtCore import QRunnable, Qt, QThreadPool, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from clipwright.core import ffmpeg
from clipwright.core.mediafile import CameraType, Recording
from clipwright.util.paths import thumbnail_cache_dir


_CAMERA_LABELS = {
    CameraType.GOPRO: "GoPro",
    CameraType.DJI_ACTION4: "DJI Action 4",
    CameraType.UNKNOWN: "Unknown Camera",
}


class PreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Thumbnail area
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setMinimumHeight(200)
        self.thumbnail_label.setStyleSheet(
            "background-color: #1a1a2e; border-radius: 6px;"
        )
        self.thumbnail_label.setText("Select a recording to preview")
        layout.addWidget(self.thumbnail_label)

        # Metadata scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.meta_layout = QVBoxLayout(scroll_content)
        self.meta_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # File info group
        file_group = QGroupBox("File Info")
        self.file_form = QFormLayout()
        file_group.setLayout(self.file_form)
        self.meta_layout.addWidget(file_group)

        self.lbl_filename = QLabel("—")
        self.lbl_camera = QLabel("—")
        self.lbl_clip_id = QLabel("—")
        self.lbl_date = QLabel("—")
        self.lbl_chapters = QLabel("—")
        self.file_form.addRow("Filename:", self.lbl_filename)
        self.file_form.addRow("Camera:", self.lbl_camera)
        self.file_form.addRow("Clip ID:", self.lbl_clip_id)
        self.file_form.addRow("Recorded:", self.lbl_date)
        self.file_form.addRow("Chapters:", self.lbl_chapters)

        # Technical info group
        tech_group = QGroupBox("Technical Details")
        self.tech_form = QFormLayout()
        tech_group.setLayout(self.tech_form)
        self.meta_layout.addWidget(tech_group)

        self.lbl_resolution = QLabel("—")
        self.lbl_fps = QLabel("—")
        self.lbl_duration = QLabel("—")
        self.lbl_video_codec = QLabel("—")
        self.lbl_audio_codec = QLabel("—")
        self.lbl_size = QLabel("—")
        self.tech_form.addRow("Resolution:", self.lbl_resolution)
        self.tech_form.addRow("Framerate:", self.lbl_fps)
        self.tech_form.addRow("Duration:", self.lbl_duration)
        self.tech_form.addRow("Video Codec:", self.lbl_video_codec)
        self.tech_form.addRow("Audio Codec:", self.lbl_audio_codec)
        self.tech_form.addRow("Total Size:", self.lbl_size)

        # Status group
        status_group = QGroupBox("Editing Compatibility")
        self.status_form = QFormLayout()
        status_group.setLayout(self.status_form)
        self.meta_layout.addWidget(status_group)

        self.lbl_audio_status = QLabel("—")
        self.lbl_merge_status = QLabel("—")
        self.status_form.addRow("Audio:", self.lbl_audio_status)
        self.status_form.addRow("Chapters:", self.lbl_merge_status)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def show_recording(self, recording: Recording):
        """Update the panel to show info about the given recording."""
        mf = recording.primary_file

        # File info
        self.lbl_filename.setText(mf.path.name)
        self.lbl_camera.setText(_CAMERA_LABELS.get(recording.camera, "Unknown"))
        self.lbl_clip_id.setText(recording.clip_id)
        if mf.recording_date:
            self.lbl_date.setText(mf.recording_date.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            self.lbl_date.setText("Unknown")
        self.lbl_chapters.setText(str(len(recording.chapters)))

        # Technical
        self.lbl_resolution.setText(mf.resolution_str)
        self.lbl_fps.setText(f"{mf.framerate} fps" if mf.framerate else "Unknown")
        self.lbl_duration.setText(recording.duration_str)
        self.lbl_video_codec.setText(mf.video_codec or "Unknown")
        self.lbl_audio_codec.setText(mf.audio_codec or "None")

        total_size = recording.total_size
        for unit in ("B", "KB", "MB", "GB"):
            if total_size < 1024:
                self.lbl_size.setText(f"{total_size:.1f} {unit}")
                break
            total_size /= 1024
        else:
            self.lbl_size.setText(f"{total_size:.1f} TB")

        # Compatibility status
        if recording.needs_audio_conversion:
            self.lbl_audio_status.setText("AAC — convert audio for Linux editing compatibility")
            self.lbl_audio_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
        else:
            self.lbl_audio_status.setText("Compatible")
            self.lbl_audio_status.setStyleSheet("color: #2ecc71; font-weight: bold;")

        if recording.needs_merge:
            self.lbl_merge_status.setText(
                f"{len(recording.chapters)} chapters — merge recommended"
            )
            self.lbl_merge_status.setStyleSheet("color: #f39c12; font-weight: bold;")
        else:
            self.lbl_merge_status.setText("Single file")
            self.lbl_merge_status.setStyleSheet("color: #2ecc71;")

        # Load thumbnail in background
        self._load_thumbnail(mf.path)

    def _load_thumbnail(self, video_path: Path):
        """Extract and display a thumbnail for the video."""
        # Check cache first
        cache_key = hashlib.md5(str(video_path).encode()).hexdigest()
        cache_path = thumbnail_cache_dir() / f"{cache_key}.jpg"

        if cache_path.exists():
            self._set_thumbnail(cache_path)
            return

        runner = ThumbnailRunner(video_path, cache_path)
        runner.signals = ThumbnailSignals()
        runner.signals.finished.connect(self._set_thumbnail)
        QThreadPool.globalInstance().start(runner)

    def _set_thumbnail(self, path: Path):
        """Display a thumbnail image."""
        if not path.exists():
            self.thumbnail_label.setText("No preview available")
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.thumbnail_label.setText("No preview available")
            return
        scaled = pixmap.scaled(
            self.thumbnail_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.thumbnail_label.setPixmap(scaled)


class ThumbnailSignals(QObject):
    finished = pyqtSignal(Path)


class ThumbnailRunner(QRunnable):
    def __init__(self, video_path: Path, cache_path: Path):
        super().__init__()
        self.video_path = video_path
        self.cache_path = cache_path
        self.signals: ThumbnailSignals | None = None

    def run(self):
        try:
            ffmpeg.extract_thumbnail(self.video_path, self.cache_path)
            if self.signals:
                self.signals.finished.emit(self.cache_path)
        except Exception:
            if self.signals:
                self.signals.finished.emit(self.cache_path)
