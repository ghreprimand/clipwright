"""Job panel — conversion/merge queue with progress tracking."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from clipwright.core.converter import convert_recording
from clipwright.core.merger import merge_chapters
from clipwright.core.mediafile import Recording
from clipwright.core.outputs import resolve_output_path
from clipwright.core.transcoder import TranscodeSettings, transcode
from clipwright.util.config import Config


class JobPanel(QWidget):
    def __init__(self, config: Config | None = None, parent=None):
        super().__init__(parent)
        self.config = config
        self._setup_ui()
        self._active_jobs = 0

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Header
        header = QHBoxLayout()
        self.header_label = QLabel("Jobs")
        self.header_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(self.header_label)
        header.addStretch()

        self.clear_btn = QPushButton("Clear Completed")
        self.clear_btn.clicked.connect(self._clear_completed)
        header.addWidget(self.clear_btn)
        layout.addLayout(header)

        # Scrollable job list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.job_container = QWidget()
        self.job_layout = QVBoxLayout(self.job_container)
        self.job_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.job_layout.setSpacing(4)
        scroll.setWidget(self.job_container)
        layout.addWidget(scroll)

    def submit_conversions(
        self,
        recordings: list[Recording],
        output_dir: Path,
        output_suffix: str = "_pcm",
        conflict_policy: str = "rename",
    ):
        """Submit recordings for conversion."""
        for rec in recordings:
            card = JobCard(rec.display_name, "conversion")
            self.job_layout.addWidget(card)

            runner = ConversionRunner(rec, output_dir, output_suffix, conflict_policy)
            runner.signals = JobSignals()
            runner.signals.progress.connect(card.update_progress)
            runner.signals.finished.connect(card.mark_done)
            runner.signals.error.connect(card.mark_error)
            runner.signals.finished.connect(self._on_job_finished)
            runner.signals.finished.connect(self._maybe_open_output_folder)
            runner.signals.error.connect(self._on_job_finished)

            self._active_jobs += 1
            self._update_header()
            QThreadPool.globalInstance().start(runner)

    def submit_merges(self, recordings: list[Recording], output_dir: Path):
        """Submit recordings for chapter merging."""
        reserved: set[Path] = set()
        conflict_policy = self._conflict_policy()
        for rec in recordings:
            card = JobCard(rec.display_name, "merge")
            self.job_layout.addWidget(card)

            mf = rec.primary_file
            output_path = resolve_output_path(
                output_dir / f"{mf.path.stem}_merged{mf.path.suffix}",
                conflict_policy=conflict_policy,
                reserved=reserved,
            )
            reserved.add(output_path.resolve())

            runner = MergeRunner(rec, output_dir, output_path, conflict_policy)
            runner.signals = JobSignals()
            runner.signals.progress.connect(card.update_progress)
            runner.signals.finished.connect(card.mark_done)
            runner.signals.error.connect(card.mark_error)
            runner.signals.finished.connect(self._on_job_finished)
            runner.signals.finished.connect(self._maybe_open_output_folder)
            runner.signals.error.connect(self._on_job_finished)

            self._active_jobs += 1
            self._update_header()
            QThreadPool.globalInstance().start(runner)

    def submit_transcodes(
        self,
        recordings: list[Recording],
        output_dir: Path,
        settings: TranscodeSettings,
    ):
        """Submit recordings for transcoding."""
        reserved: set[Path] = set()
        conflict_policy = self._conflict_policy()
        for rec in recordings:
            card = JobCard(rec.display_name, "transcode")
            self.job_layout.addWidget(card)

            mf = rec.primary_file
            output_path = resolve_output_path(
                output_dir / f"{mf.path.stem}_transcoded{settings.container}",
                conflict_policy=conflict_policy,
                reserved=reserved,
            )
            reserved.add(output_path.resolve())

            runner = TranscodeRunner(rec, output_path, settings)
            runner.signals = JobSignals()
            runner.signals.progress.connect(card.update_progress)
            runner.signals.finished.connect(card.mark_done)
            runner.signals.error.connect(card.mark_error)
            runner.signals.finished.connect(self._on_job_finished)
            runner.signals.finished.connect(self._maybe_open_output_folder)
            runner.signals.error.connect(self._on_job_finished)

            self._active_jobs += 1
            self._update_header()
            QThreadPool.globalInstance().start(runner)

    def submit_trim(
        self,
        recording: Recording,
        output_dir: Path,
        trim_start: float | None,
        trim_end: float | None,
    ):
        """Submit a recording for trimming."""
        card = JobCard(recording.display_name, "trim")
        self.job_layout.addWidget(card)

        mf = recording.primary_file
        output_path = resolve_output_path(
            output_dir / f"{mf.path.stem}_trimmed.mov",
            conflict_policy=self._conflict_policy(),
        )

        runner = TrimRunner(recording, output_path, trim_start, trim_end)
        runner.signals = JobSignals()
        runner.signals.progress.connect(card.update_progress)
        runner.signals.finished.connect(card.mark_done)
        runner.signals.error.connect(card.mark_error)
        runner.signals.finished.connect(self._on_job_finished)
        runner.signals.finished.connect(self._maybe_open_output_folder)
        runner.signals.error.connect(self._on_job_finished)

        self._active_jobs += 1
        self._update_header()
        QThreadPool.globalInstance().start(runner)

    def _on_job_finished(self, *args):
        self._active_jobs = max(0, self._active_jobs - 1)
        self._update_header()

    def _maybe_open_output_folder(self, output_path: str):
        if self.config and self.config.get("open_output_folder") == "true":
            subprocess.Popen(["xdg-open", str(Path(output_path).parent)])

    def _conflict_policy(self) -> str:
        if not self.config:
            return "rename"
        return self.config.get("conflict_policy") or "rename"

    def _update_header(self):
        if self._active_jobs > 0:
            self.header_label.setText(f"Jobs ({self._active_jobs} active)")
        else:
            self.header_label.setText("Jobs")

    def _clear_completed(self):
        """Remove completed/errored job cards."""
        for i in reversed(range(self.job_layout.count())):
            widget = self.job_layout.itemAt(i).widget()
            if isinstance(widget, JobCard) and widget.is_finished:
                self.job_layout.removeWidget(widget)
                widget.deleteLater()


class JobCard(QWidget):
    """Single job progress card."""

    def __init__(self, name: str, job_type: str, parent=None):
        super().__init__(parent)
        self.is_finished = False
        self._output_path: str | None = None
        self._setup_ui(name, job_type)

    def _setup_ui(self, name: str, job_type: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        self.setStyleSheet(
            "JobCard { background: palette(base); border-radius: 4px; }"
        )

        # Top row: name and status
        top = QHBoxLayout()
        self.name_label = QLabel(f"<b>{name}</b>")
        top.addWidget(self.name_label)
        top.addStretch()
        self.status_label = QLabel(job_type.title())
        self.status_label.setStyleSheet("color: palette(mid);")
        top.addWidget(self.status_label)
        layout.addLayout(top)

        # Progress bar + open folder button row
        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximumHeight(18)
        progress_row.addWidget(self.progress_bar)

        self.open_folder_btn = QPushButton("Open Folder")
        self.open_folder_btn.setMaximumHeight(22)
        self.open_folder_btn.setFixedWidth(90)
        self.open_folder_btn.hide()
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        progress_row.addWidget(self.open_folder_btn)

        layout.addLayout(progress_row)

    def update_progress(self, percent: float, message: str):
        self.progress_bar.setValue(int(percent))
        self.status_label.setText(message)

    def mark_done(self, output_path: str):
        self.is_finished = True
        self._output_path = output_path
        self.progress_bar.setValue(100)
        self.status_label.setText(f"Done: {Path(output_path).name}")
        self.status_label.setStyleSheet("color: #2ecc71; font-weight: bold;")
        self.open_folder_btn.show()

    def mark_error(self, error_msg: str):
        self.is_finished = True
        self.progress_bar.setStyleSheet("QProgressBar::chunk { background: #e74c3c; }")
        self.status_label.setText(f"Error: {error_msg[:80]}")
        self.status_label.setStyleSheet("color: #e74c3c;")

    def _open_output_folder(self):
        if self._output_path:
            folder = str(Path(self._output_path).parent)
            subprocess.Popen(["xdg-open", folder])


# --- Job Runners ---


class JobSignals(QObject):
    progress = pyqtSignal(float, str)
    finished = pyqtSignal(str)  # output path
    error = pyqtSignal(str)


class ConversionRunner(QRunnable):
    def __init__(
        self,
        recording: Recording,
        output_dir: Path,
        output_suffix: str = "_pcm",
        conflict_policy: str = "rename",
    ):
        super().__init__()
        self.recording = recording
        self.output_dir = output_dir
        self.output_suffix = output_suffix
        self.conflict_policy = conflict_policy
        self.signals: JobSignals | None = None

    def run(self):
        try:
            result = convert_recording(
                self.recording,
                self.output_dir,
                output_suffix=self.output_suffix,
                conflict_policy=self.conflict_policy,
                on_progress=lambda pct, msg: (
                    self.signals.progress.emit(pct, msg) if self.signals else None
                ),
            )
            if self.signals:
                self.signals.finished.emit(str(result))
        except Exception as e:
            if self.signals:
                self.signals.error.emit(str(e))


class MergeRunner(QRunnable):
    def __init__(
        self,
        recording: Recording,
        output_dir: Path,
        output_path: Path,
        conflict_policy: str = "rename",
    ):
        super().__init__()
        self.recording = recording
        self.output_dir = output_dir
        self.output_path = output_path
        self.conflict_policy = conflict_policy
        self.signals: JobSignals | None = None

    def run(self):
        try:
            result = merge_chapters(
                self.recording,
                self.output_dir,
                conflict_policy=self.conflict_policy,
                output_path=self.output_path,
                on_progress=lambda pct: (
                    self.signals.progress.emit(pct, "Merging...") if self.signals else None
                ),
            )
            if self.signals:
                self.signals.finished.emit(str(result))
        except Exception as e:
            if self.signals:
                self.signals.error.emit(str(e))


class TranscodeRunner(QRunnable):
    def __init__(self, recording: Recording, output_path: Path, settings: TranscodeSettings):
        super().__init__()
        self.recording = recording
        self.output_path = output_path
        self.settings = settings
        self.signals: JobSignals | None = None

    def run(self):
        try:
            mf = self.recording.primary_file

            result = transcode(
                mf.path,
                self.output_path,
                self.settings,
                duration_sec=self.recording.total_duration,
                on_progress=lambda pct: (
                    self.signals.progress.emit(pct, "Transcoding...") if self.signals else None
                ),
            )
            if self.signals:
                self.signals.finished.emit(str(result))
        except Exception as e:
            if self.signals:
                self.signals.error.emit(str(e))


class TrimRunner(QRunnable):
    def __init__(
        self,
        recording: Recording,
        output_path: Path,
        trim_start: float | None,
        trim_end: float | None,
    ):
        super().__init__()
        self.recording = recording
        self.output_path = output_path
        self.trim_start = trim_start
        self.trim_end = trim_end
        self.signals: JobSignals | None = None

    def run(self):
        try:
            from clipwright.core.transcoder import TranscodeSettings, VideoCodec, AudioCodec, Container

            mf = self.recording.primary_file
            # Copy streams (no re-encode) for fast trim
            settings = TranscodeSettings(
                video_codec=VideoCodec.COPY,
                audio_codec=AudioCodec.COPY,
                container=Container.MOV,
            )

            duration = self.recording.total_duration
            if self.trim_start and self.trim_end:
                duration = self.trim_end - self.trim_start
            elif self.trim_end:
                duration = self.trim_end

            result = transcode(
                mf.path,
                self.output_path,
                settings,
                duration_sec=duration,
                trim_start=self.trim_start,
                trim_end=self.trim_end,
                on_progress=lambda pct: (
                    self.signals.progress.emit(pct, "Trimming...") if self.signals else None
                ),
            )
            if self.signals:
                self.signals.finished.emit(str(result))
        except Exception as e:
            if self.signals:
                self.signals.error.emit(str(e))
