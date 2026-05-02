"""Batch rename dialog with template editor and live preview."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from clipwright.core.mediafile import Recording
from clipwright.core.renamer import AVAILABLE_TOKENS, execute_rename, preview_rename
from clipwright.util.config import Config


class RenameDialog(QDialog):
    def __init__(
        self,
        recordings: list[Recording],
        config: Config,
        parent=None,
    ):
        super().__init__(parent)
        self.recordings = recordings
        self.config = config
        self.setWindowTitle("Batch Rename")
        self.setMinimumSize(650, 500)
        self._setup_ui()
        self._update_preview()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Template input
        template_group = QGroupBox("Rename Template")
        template_layout = QVBoxLayout()

        self.template_input = QLineEdit()
        self.template_input.setText(self.config.get("rename_template"))
        self.template_input.setPlaceholderText("{date}_{camera}_{clip_id}")
        self.template_input.textChanged.connect(self._update_preview)
        template_layout.addWidget(self.template_input)

        # Available tokens
        tokens_label = QLabel(
            "Available tokens: "
            + ", ".join(f"<code>{{{k}}}</code>" for k in AVAILABLE_TOKENS)
        )
        tokens_label.setWordWrap(True)
        tokens_label.setTextFormat(Qt.TextFormat.RichText)
        tokens_label.setStyleSheet("color: palette(mid); font-size: 11px;")
        template_layout.addWidget(tokens_label)

        template_group.setLayout(template_layout)
        layout.addWidget(template_group)

        # Options row
        options_layout = QFormLayout()
        self.start_index_spin = QSpinBox()
        self.start_index_spin.setRange(1, 9999)
        self.start_index_spin.setValue(1)
        self.start_index_spin.valueChanged.connect(self._update_preview)
        options_layout.addRow("Start index:", self.start_index_spin)
        layout.addLayout(options_layout)

        # Preview list
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout()
        self.preview_list = QListWidget()
        self.preview_list.setAlternatingRowColors(True)
        preview_layout.addWidget(self.preview_list)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # Buttons
        button_box = QDialogButtonBox()
        self.rename_btn = QPushButton("Rename Files")
        self.rename_btn.setDefault(True)
        button_box.addButton(self.rename_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._do_rename)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _update_preview(self):
        """Update the preview list based on current template."""
        self.preview_list.clear()
        template = self.template_input.text()
        if not template:
            return

        try:
            previews = preview_rename(
                self.recordings,
                template,
                start_index=self.start_index_spin.value(),
            )
            for p in previews:
                self.preview_list.addItem(
                    f"{p.source.name}  →  {p.destination.name}"
                )
        except Exception as e:
            self.preview_list.addItem(f"Template error: {e}")

    def _do_rename(self):
        """Execute the rename operation."""
        template = self.template_input.text()
        if not template:
            return

        previews = preview_rename(
            self.recordings,
            template,
            start_index=self.start_index_spin.value(),
        )

        # Check for conflicts
        dest_names = [p.destination for p in previews]
        if len(dest_names) != len(set(dest_names)):
            QMessageBox.warning(
                self,
                "Naming Conflict",
                "Some files would end up with the same name. "
                "Add {index} to your template to make names unique.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirm Rename",
            f"Rename {len(previews)} file(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                execute_rename(previews)
                self.config.set("rename_template", template)
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Rename Failed", str(e))
