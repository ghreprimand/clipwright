"""Conversion review dialog."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from clipwright.core.mediafile import Recording


class ConvertReviewDialog(QDialog):
    """Show exactly what Convert Audio will do before jobs are submitted."""

    def __init__(
        self,
        recordings: list[Recording],
        plans: list[dict[str, str]],
        destination_mode: str,
        conflict_policy: str,
        parent=None,
    ):
        super().__init__(parent)
        self.recordings = recordings
        self.plans = plans
        self.destination_mode = destination_mode
        self.conflict_policy = conflict_policy

        self.setWindowTitle("Review Audio Conversion")
        self.setMinimumSize(900, 520)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        needs_conversion = sum(1 for r in self.recordings if r.needs_audio_conversion)
        merge_count = sum(1 for r in self.recordings if r.needs_merge)
        compatible_count = len(self.recordings) - needs_conversion

        intro = QLabel(
            f"<b>Convert audio for {len(self.recordings)} selected recording(s)</b><br>"
            "Video will be copied without re-encoding. AAC audio will be converted "
            "to PCM signed 16-bit audio in a MOV container."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        summary_group = QGroupBox("Summary")
        summary = QFormLayout(summary_group)
        summary.addRow("Needs audio conversion:", QLabel(str(needs_conversion)))
        summary.addRow("Already compatible:", QLabel(str(compatible_count)))
        summary.addRow("Chapter groups to merge:", QLabel(str(merge_count)))
        summary.addRow("Destination mode:", QLabel(self.destination_mode))
        summary.addRow("Conflict policy:", QLabel(self.conflict_policy))
        layout.addWidget(summary_group)

        table = QTableWidget(len(self.plans), 4)
        table.setHorizontalHeaderLabels(["Source", "Input", "Action", "Output"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setWordWrap(True)

        for row, plan in enumerate(self.plans):
            for col, key in enumerate(("source", "input", "action", "output")):
                item = QTableWidgetItem(plan[key])
                item.setToolTip(plan[key])
                item.setTextAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
                table.setItem(row, col, item)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.resizeRowsToContents()
        layout.addWidget(table, stretch=1)

        note = QLabel(
            "Outputs are created only when conversion or merging is needed. "
            "Already compatible single files are left unchanged."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Start Conversion")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def build_conversion_plans(
    recordings: list[Recording],
    destinations: list[Path],
    output_suffix: str,
    conflict_policy: str,
) -> list[dict[str, str]]:
    return [
        _build_plan(rec, output_dir, output_suffix, conflict_policy)
        for rec, output_dir in zip(recordings, destinations)
    ]


def _build_plan(
    recording: Recording,
    output_dir: Path,
    output_suffix: str,
    conflict_policy: str,
) -> dict[str, str]:
    primary = recording.primary_file
    source = str(primary.path)
    input_text = (
        f"{primary.video_codec or 'unknown'} video, "
        f"{primary.audio_codec or 'no'} audio, "
        f"{primary.resolution_str}, {recording.duration_str}, "
        f"{primary.size_str}"
    )

    actions = []
    if recording.needs_merge:
        actions.append(f"merge {len(recording.chapters)} chapters")
    if recording.needs_audio_conversion:
        actions.append(f"convert {primary.audio_codec or 'audio'} to pcm_s16le")
    if not actions:
        actions.append("leave unchanged; already compatible")

    output = "No new file"
    if recording.needs_merge or recording.needs_audio_conversion:
        output = str(
            _planned_output_path(recording, output_dir, output_suffix, conflict_policy)
        )

    return {
        "source": source,
        "input": input_text,
        "action": "; ".join(actions),
        "output": output,
    }


def _planned_output_path(
    recording: Recording,
    output_dir: Path,
    output_suffix: str,
    conflict_policy: str,
) -> Path:
    stem = recording.primary_file.path.stem
    if recording.needs_merge:
        stem = f"{stem}_merged"
    path = output_dir / f"{stem}{output_suffix}.mov"
    if conflict_policy == "overwrite" or not path.exists():
        return path

    for index in range(1, 10_000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    return path
