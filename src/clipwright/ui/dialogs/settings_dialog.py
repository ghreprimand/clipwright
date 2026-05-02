"""Application settings dialog."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from clipwright.ui.file_dialogs import choose_directory
from clipwright.util.config import Config


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Output Settings ---
        output_group = QGroupBox("Output Defaults")
        output_layout = QFormLayout()

        dir_layout = QHBoxLayout()
        self.default_output_dir = QLineEdit()
        self.default_output_dir.setPlaceholderText("Ask every time")
        dir_layout.addWidget(self.default_output_dir)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output_dir)
        dir_layout.addWidget(browse_btn)
        output_layout.addRow("Default output folder:", dir_layout)

        self.convert_in_place = QCheckBox("Convert files next to originals (ignore output folder)")
        output_layout.addRow(self.convert_in_place)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # --- Processing ---
        proc_group = QGroupBox("Processing")
        proc_layout = QFormLayout()

        self.parallel_jobs_spin = QSpinBox()
        self.parallel_jobs_spin.setRange(1, 8)
        proc_layout.addRow("Parallel jobs:", self.parallel_jobs_spin)

        self.open_output_check = QCheckBox("Open output folder when done")
        proc_layout.addRow(self.open_output_check)

        proc_group.setLayout(proc_layout)
        layout.addWidget(proc_group)

        # --- Rename ---
        rename_group = QGroupBox("Batch Rename")
        rename_layout = QFormLayout()

        self.rename_template = QLineEdit()
        self.rename_template.setPlaceholderText("{date}_{camera}_{clip_id}")
        rename_layout.addRow("Default template:", self.rename_template)

        rename_group.setLayout(rename_layout)
        layout.addWidget(rename_group)

        # --- Buttons ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_and_close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _load_settings(self):
        self.default_output_dir.setText(self.config.get("output_dir"))
        self.convert_in_place.setChecked(self.config.get("convert_in_place") == "true")
        self.parallel_jobs_spin.setValue(self.config.get_int("parallel_jobs"))
        self.open_output_check.setChecked(self.config.get("open_output_folder") == "true")
        self.rename_template.setText(self.config.get("rename_template"))

    def _save_and_close(self):
        self.config.set("output_dir", self.default_output_dir.text())
        self.config.set("convert_in_place", str(self.convert_in_place.isChecked()).lower())
        self.config.set("parallel_jobs", self.parallel_jobs_spin.value())
        self.config.set("open_output_folder", str(self.open_output_check.isChecked()).lower())
        self.config.set("rename_template", self.rename_template.text())

        self.config.sync()
        self.accept()

    def _browse_output_dir(self):
        folder = choose_directory(self, "Choose Default Output Directory")
        if folder:
            self.default_output_dir.setText(folder)
