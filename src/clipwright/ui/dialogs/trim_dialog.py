"""Quick trim dialog — set in/out points to cut footage before processing."""

from __future__ import annotations


from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from clipwright.core.mediafile import Recording


def _format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS.s"""
    if seconds < 0:
        seconds = 0
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}:{m:02d}:{s:05.2f}"
    return f"{m:02d}:{s:05.2f}"


class TrimDialog(QDialog):
    def __init__(self, recording: Recording, parent=None):
        super().__init__(parent)
        self.recording = recording
        self.duration = recording.total_duration
        self.trim_start: float = 0.0
        self.trim_end: float = self.duration

        self.setWindowTitle(f"Trim — {recording.display_name}")
        self.setMinimumWidth(550)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Info
        info = QLabel(
            f"<b>{self.recording.display_name}</b> — "
            f"Duration: {_format_time(self.duration)}"
        )
        layout.addWidget(info)

        # Trim controls
        trim_group = QGroupBox("Set In / Out Points")
        trim_layout = QVBoxLayout()

        # In point
        in_layout = QHBoxLayout()
        in_layout.addWidget(QLabel("In:"))
        self.in_slider = QSlider(Qt.Orientation.Horizontal)
        self.in_slider.setRange(0, int(self.duration * 10))  # 0.1s resolution
        self.in_slider.setValue(0)
        self.in_slider.valueChanged.connect(self._on_in_changed)
        in_layout.addWidget(self.in_slider)
        self.in_label = QLabel(_format_time(0))
        self.in_label.setMinimumWidth(90)
        in_layout.addWidget(self.in_label)
        trim_layout.addLayout(in_layout)

        # Out point
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("Out:"))
        self.out_slider = QSlider(Qt.Orientation.Horizontal)
        self.out_slider.setRange(0, int(self.duration * 10))
        self.out_slider.setValue(int(self.duration * 10))
        self.out_slider.valueChanged.connect(self._on_out_changed)
        out_layout.addWidget(self.out_slider)
        self.out_label = QLabel(_format_time(self.duration))
        self.out_label.setMinimumWidth(90)
        out_layout.addWidget(self.out_label)
        trim_layout.addLayout(out_layout)

        # Result duration
        self.result_label = QLabel("")
        self.result_label.setStyleSheet("font-weight: bold;")
        trim_layout.addWidget(self.result_label)

        trim_group.setLayout(trim_layout)
        layout.addWidget(trim_group)

        # Quick buttons
        quick_layout = QHBoxLayout()
        quick_layout.addWidget(QLabel("Quick:"))

        trim_first_5 = QPushButton("Skip first 5s")
        trim_first_5.clicked.connect(lambda: self._set_in(5.0))
        quick_layout.addWidget(trim_first_5)

        trim_first_10 = QPushButton("Skip first 10s")
        trim_first_10.clicked.connect(lambda: self._set_in(10.0))
        quick_layout.addWidget(trim_first_10)

        trim_last_5 = QPushButton("Cut last 5s")
        trim_last_5.clicked.connect(lambda: self._set_out(self.duration - 5.0))
        quick_layout.addWidget(trim_last_5)

        trim_last_10 = QPushButton("Cut last 10s")
        trim_last_10.clicked.connect(lambda: self._set_out(self.duration - 10.0))
        quick_layout.addWidget(trim_last_10)

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._reset)
        quick_layout.addWidget(reset_btn)

        quick_layout.addStretch()
        layout.addLayout(quick_layout)

        # Buttons
        button_box = QDialogButtonBox()
        self.apply_btn = QPushButton("Apply Trim")
        self.apply_btn.setDefault(True)
        button_box.addButton(self.apply_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._update_result()

    def _on_in_changed(self, value: int):
        self.trim_start = value / 10.0
        # Don't let in pass out
        if self.trim_start >= self.trim_end:
            self.trim_start = max(0, self.trim_end - 0.1)
            self.in_slider.setValue(int(self.trim_start * 10))
        self.in_label.setText(_format_time(self.trim_start))
        self._update_result()

    def _on_out_changed(self, value: int):
        self.trim_end = value / 10.0
        # Don't let out pass in
        if self.trim_end <= self.trim_start:
            self.trim_end = min(self.duration, self.trim_start + 0.1)
            self.out_slider.setValue(int(self.trim_end * 10))
        self.out_label.setText(_format_time(self.trim_end))
        self._update_result()

    def _set_in(self, seconds: float):
        self.in_slider.setValue(int(seconds * 10))

    def _set_out(self, seconds: float):
        self.out_slider.setValue(int(max(0, seconds) * 10))

    def _reset(self):
        self.in_slider.setValue(0)
        self.out_slider.setValue(int(self.duration * 10))

    def _update_result(self):
        result_dur = self.trim_end - self.trim_start
        removed = self.duration - result_dur
        pct = (removed / self.duration * 100) if self.duration > 0 else 0
        self.result_label.setText(
            f"Output duration: {_format_time(result_dur)} "
            f"(removing {_format_time(removed)}, {pct:.1f}%)"
        )

    def get_trim_points(self) -> tuple[float | None, float | None]:
        """Return (start, end) trim points, or None if no trimming."""
        start = self.trim_start if self.trim_start > 0.05 else None
        end = self.trim_end if self.trim_end < (self.duration - 0.05) else None
        if start is None and end is None:
            return None, None
        return self.trim_start, self.trim_end
