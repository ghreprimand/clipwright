"""Main application window."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtGui import QAction, QDragEnterEvent, QDragMoveEvent, QDropEvent, QKeySequence
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QRadioButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWhatsThis,
    QWidget,
)

from clipwright.ui.file_dialogs import choose_directory, choose_video_files
from clipwright.ui.filepanel import FilePanel
from clipwright.ui.jobpanel import JobPanel
from clipwright.ui.previewpanel import PreviewPanel
from clipwright.ui.dialogs.help_dialog import WHATSTHIS
from clipwright.ui.widgets.thumbnail import ThumbnailGrid
from clipwright.util.config import Config


class MainWindow(QMainWindow):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(config.get_int("parallel_jobs"))

        self.setWindowTitle("Clipwright")
        self.setMinimumSize(1000, 650)
        self.setAcceptDrops(True)

        self._setup_menubar()
        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()
        self._restore_geometry()

    def _setup_menubar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        open_files_action = QAction("Add Files...", self)
        open_files_action.setShortcut(QKeySequence("Ctrl+O"))
        open_files_action.triggered.connect(self._open_files)
        file_menu.addAction(open_files_action)

        open_action = QAction("Add Folder...", self)
        open_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        open_action.triggered.connect(self._open_folder)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Tools menu
        tools_menu = menubar.addMenu("Tools")

        convert_action = QAction("Convert Audio", self)
        convert_action.setShortcut(QKeySequence("Ctrl+Return"))
        convert_action.triggered.connect(self._convert_selected)
        tools_menu.addAction(convert_action)

        merge_action = QAction("Merge Chapters", self)
        merge_action.triggered.connect(self._merge_selected)
        tools_menu.addAction(merge_action)

        transcode_action = QAction("Transcode...", self)
        transcode_action.setShortcut(QKeySequence("Ctrl+T"))
        transcode_action.triggered.connect(self._open_transcode_dialog)
        tools_menu.addAction(transcode_action)

        trim_action = QAction("Quick Trim...", self)
        trim_action.triggered.connect(self._open_trim_dialog)
        tools_menu.addAction(trim_action)

        tools_menu.addSeparator()

        rename_action = QAction("Batch Rename...", self)
        rename_action.setShortcut(QKeySequence("F2"))
        rename_action.triggered.connect(self._open_rename_dialog)
        tools_menu.addAction(rename_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        help_action = QAction("Help", self)
        help_action.setShortcut(QKeySequence("F1"))
        help_action.triggered.connect(self._open_help)
        help_menu.addAction(help_action)

        whatsthis_action = QAction("What's This?", self)
        whatsthis_action.setShortcut(QKeySequence("Shift+F1"))
        whatsthis_action.triggered.connect(QWhatsThis.enterWhatsThisMode)
        help_menu.addAction(whatsthis_action)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main horizontal splitter: file panel | right panel (tabs)
        self.h_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.file_panel = FilePanel(self)
        self.file_panel.setWhatsThis(WHATSTHIS["file_panel"])
        self.h_splitter.addWidget(self.file_panel)

        # Right side: tabbed preview + thumbnail grid
        self.right_tabs = QTabWidget()

        self.preview_panel = PreviewPanel(self)
        self.preview_panel.setWhatsThis(WHATSTHIS["preview_panel"])
        self.right_tabs.addTab(self.preview_panel, "Details")

        self.thumbnail_grid = ThumbnailGrid(self)
        self.thumbnail_grid.setWhatsThis(WHATSTHIS["thumbnail_grid"])
        self.right_tabs.addTab(self.thumbnail_grid, "Thumbnails")

        self.h_splitter.addWidget(self.right_tabs)
        self.h_splitter.setSizes([350, 650])

        # Vertical splitter: top content | job panel
        self.v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.v_splitter.addWidget(self.h_splitter)

        self.job_panel = JobPanel(self.config, self)
        self.job_panel.setWhatsThis(WHATSTHIS["job_panel"])
        self.v_splitter.addWidget(self.job_panel)
        self.v_splitter.setSizes([500, 150])

        self._setup_operation_tabs(layout)
        layout.addWidget(self.v_splitter)

        # Persistent action bar — always visible, prominent Convert button
        self._setup_action_bar(layout)

        # Connect signals
        self.file_panel.recording_selected.connect(self.preview_panel.show_recording)
        self.file_panel.recording_selected.connect(
            lambda r: self.right_tabs.setCurrentWidget(self.preview_panel)
        )
        self.file_panel.recordings_loaded.connect(self._on_recordings_loaded)
        self.file_panel.recordings_loaded.connect(lambda _count: self._update_operation_summary())
        self.file_panel.tree.itemSelectionChanged.connect(self._update_operation_summary)
        self.file_panel.tree.itemChanged.connect(self._update_operation_summary)
        self.thumbnail_grid.recording_clicked.connect(self.preview_panel.show_recording)
        self.thumbnail_grid.recording_clicked.connect(
            lambda r: self.right_tabs.setCurrentWidget(self.preview_panel)
        )

        # Context menu signals from file panel
        self.file_panel.convert_requested.connect(self._convert_recordings)
        self.file_panel.merge_requested.connect(self._merge_recordings)
        self.file_panel.transcode_requested.connect(self._transcode_recordings)
        self.file_panel.trim_requested.connect(self._trim_recording)
        self.file_panel.rename_requested.connect(self._rename_recordings)

    def _setup_action_bar(self, layout: QVBoxLayout) -> None:
        """Add a persistent bottom action bar with a prominent Convert button."""
        self.action_bar = QHBoxLayout()
        self.action_bar.setContentsMargins(8, 6, 8, 6)
        self.action_bar.setSpacing(12)

        # "Convert Audio" — the primary action, always visible
        self.convert_primary_button = QPushButton("▶  Convert Audio")
        self.convert_primary_button.setObjectName("convertPrimaryButton")
        self.convert_primary_button.setMinimumHeight(36)
        self.convert_primary_button.setStyleSheet("""
            QPushButton#convertPrimaryButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#convertPrimaryButton:hover {
                background-color: #1976D2;
            }
            QPushButton#convertPrimaryButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton#convertPrimaryButton:disabled {
                background-color: #B0BEC5;
                color: #78909C;
            }
        """)
        self.convert_primary_button.setMaximumHeight(42)
        self.convert_primary_button.setEnabled(False)
        self.convert_primary_button.clicked.connect(self._convert_selected)
        self.action_bar.addWidget(self.convert_primary_button, stretch=1)

        # Status hint label
        self.action_bar_hint = QLabel("Select recordings to convert")
        self.action_bar_hint.setStyleSheet("color: gray; font-size: 12px;")
        self.action_bar.addWidget(self.action_bar_hint)

        layout.addLayout(self.action_bar)

    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Add files
        add_files_action = QAction("Add Files", self)
        add_files_action.setWhatsThis(WHATSTHIS["open_files"])
        add_files_action.triggered.connect(self._open_files)
        toolbar.addAction(add_files_action)

        # Add folder
        add_folder_action = QAction("Add Folder", self)
        add_folder_action.setWhatsThis(WHATSTHIS["open_folder"])
        add_folder_action.triggered.connect(self._open_folder)
        toolbar.addAction(add_folder_action)

        toolbar.addSeparator()

        remove_action = QAction("Remove", self)
        remove_action.setWhatsThis(WHATSTHIS["remove"])
        remove_action.triggered.connect(self.file_panel.remove_selected)
        toolbar.addAction(remove_action)

        clear_action = QAction("Clear", self)
        clear_action.setWhatsThis(WHATSTHIS["clear"])
        clear_action.triggered.connect(self.file_panel.clear)
        toolbar.addAction(clear_action)

        toolbar.addSeparator()

        # Select all / none
        select_all_action = QAction("Select All", self)
        select_all_action.setShortcut(QKeySequence("Ctrl+A"))
        select_all_action.setWhatsThis(WHATSTHIS["select_all"])
        select_all_action.triggered.connect(self.file_panel.select_all)
        toolbar.addAction(select_all_action)

        deselect_action = QAction("Select None", self)
        deselect_action.setWhatsThis(WHATSTHIS["select_none"])
        deselect_action.triggered.connect(self.file_panel.select_none)
        toolbar.addAction(deselect_action)

        toolbar.addSeparator()

        # What's This
        help_action = QAction("?", self)
        help_action.setWhatsThis("Click this, then click on any part of the app to learn what it does.")
        help_action.triggered.connect(QWhatsThis.enterWhatsThisMode)
        toolbar.addAction(help_action)

    def _setup_operation_tabs(self, layout: QVBoxLayout):
        self.operation_tabs = QTabWidget()
        self.operation_tabs.setObjectName("operation_tabs")
        self.operation_tabs.setWhatsThis(WHATSTHIS["operations"])
        self.operation_tabs.addTab(self._build_convert_tab(), "Convert Audio")
        self.operation_tabs.addTab(
            self._build_action_tab(
                "Merge split camera chapters into a single file.",
                "Merge Selected Chapter Groups",
                self._merge_selected,
                summary_attr="merge_summary_label",
                button_attr="merge_button",
                whatsthis_key="merge",
            ),
            "Merge",
        )
        self.operation_tabs.addTab(
            self._build_action_tab(
                "Change codec, resolution, quality, or container.",
                "Configure Transcode...",
                self._open_transcode_dialog,
                summary_attr="transcode_summary_label",
                button_attr="transcode_button",
                whatsthis_key="transcode",
            ),
            "Transcode",
        )
        self.operation_tabs.addTab(
            self._build_action_tab(
                "Set rough in/out points for one selected recording.",
                "Open Trim Controls...",
                self._open_trim_dialog,
                summary_attr="trim_summary_label",
                button_attr="trim_button",
                whatsthis_key="trim",
            ),
            "Trim",
        )
        self.operation_tabs.addTab(
            self._build_action_tab(
                "Preview and apply metadata-based filenames.",
                "Open Batch Rename...",
                self._open_rename_dialog,
                summary_attr="rename_summary_label",
                button_attr="rename_button",
                whatsthis_key="rename",
            ),
            "Rename",
        )
        layout.addWidget(self.operation_tabs)
        self._update_operation_summary()

    def _build_convert_tab(self) -> QWidget:
        tab = QWidget()
        tab.setWhatsThis(WHATSTHIS["convert"])
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        self.convert_summary_label = QLabel()
        self.convert_summary_label.setWordWrap(True)
        outer.addWidget(self.convert_summary_label)

        settings_group = QGroupBox("Output")
        settings_group.setWhatsThis(WHATSTHIS["convert_output"])
        settings_layout = QVBoxLayout(settings_group)

        row = QHBoxLayout()
        row.setSpacing(8)

        row.addWidget(QLabel("Destination:"))

        self.output_mode_group = QButtonGroup(self)
        self.output_mode_buttons: dict[str, QRadioButton] = {}
        for button_id, (label, mode_value) in enumerate(
            (
                ("Same folder", "same_folder"),
                ("Subfolder", "subfolder"),
                ("Choose folder", "custom"),
            )
        ):
            button = QRadioButton(label)
            self.output_mode_group.addButton(button, button_id)
            self.output_mode_buttons[mode_value] = button
            row.addWidget(button)

        mode = self.config.get("output_mode") or "same_folder"
        self.output_mode_buttons.get(mode, self.output_mode_buttons["same_folder"]).setChecked(True)

        self.output_path_input = QLineEdit()
        self.output_path_input.setPlaceholderText("Output folder or subfolder name")
        path_text = self.config.get("output_dir") or self.config.get("output_subfolder")
        self.output_path_input.setText(path_text)
        self.output_path_input.textChanged.connect(self._save_destination_settings)
        row.addWidget(self.output_path_input, stretch=1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_destination)
        row.addWidget(browse_btn)

        row.addWidget(QLabel("Suffix:"))
        self.output_suffix_input = QLineEdit(self.config.get("output_suffix") or "_pcm")
        self.output_suffix_input.setMaximumWidth(90)
        self.output_suffix_input.textChanged.connect(self._save_destination_settings)
        row.addWidget(self.output_suffix_input)

        self.conflict_combo = QComboBox()
        self.conflict_combo.addItem("Rename if exists", "rename")
        self.conflict_combo.addItem("Overwrite", "overwrite")
        conflict = self.config.get("conflict_policy") or "rename"
        conflict_idx = self.conflict_combo.findData(conflict)
        self.conflict_combo.setCurrentIndex(conflict_idx if conflict_idx >= 0 else 0)
        for button in self.output_mode_buttons.values():
            button.toggled.connect(self._save_destination_settings)
        self.conflict_combo.currentIndexChanged.connect(self._save_destination_settings)
        row.addWidget(self.conflict_combo)

        settings_layout.addLayout(row)
        outer.addWidget(settings_group)

        details = QGroupBox("Conversion")
        details_layout = QFormLayout(details)
        details_layout.addRow("Output container:", QLabel("MOV"))
        details_layout.addRow("Video:", QLabel("Copied without re-encoding"))
        details_layout.addRow("Audio:", QLabel("AAC/aac_latm -> PCM signed 16-bit"))
        outer.addWidget(details)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        convert_btn = QPushButton("Review and Convert Selected")
        convert_btn.setWhatsThis(WHATSTHIS["convert"])
        convert_btn.clicked.connect(self._convert_selected)
        self.convert_button = convert_btn
        action_row.addWidget(convert_btn)
        outer.addLayout(action_row)

        return tab

    def _build_action_tab(
        self,
        description: str,
        button_text: str,
        callback,
        summary_attr: str,
        button_attr: str,
        whatsthis_key: str,
    ) -> QWidget:
        tab = QWidget()
        tab.setWhatsThis(WHATSTHIS[whatsthis_key])
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        summary = QLabel()
        summary.setWordWrap(True)
        setattr(self, summary_attr, summary)
        layout.addWidget(summary)

        desc = QLabel(description)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        layout.addStretch(1)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        button = QPushButton(button_text)
        button.setWhatsThis(WHATSTHIS[whatsthis_key])
        button.clicked.connect(callback)
        setattr(self, button_attr, button)
        action_row.addWidget(button)
        layout.addLayout(action_row)
        return tab

    def _setup_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Add files, add a folder, or drag media here to get started")

    def _update_operation_summary(self, *args):
        if not hasattr(self, "file_panel") or not hasattr(self, "convert_summary_label"):
            return

        selected = self.file_panel.get_selected_recordings()
        total = len(self.file_panel.recordings)
        selected_count = len(selected)
        needs_audio = sum(1 for rec in selected if rec.needs_audio_conversion)
        mergeable = sum(1 for rec in selected if rec.needs_merge)

        base = f"{selected_count} selected of {total} loaded recording(s)."
        self.convert_summary_label.setText(
            f"{base} {needs_audio} selected recording(s) need AAC audio conversion."
        )
        self.merge_summary_label.setText(
            f"{base} {mergeable} selected recording(s) have multiple chapters."
        )
        self.transcode_summary_label.setText(
            f"{base} Transcode will open codec, resolution, quality, and output controls."
        )
        self.trim_summary_label.setText(
            f"{base} Trim uses the first selected recording."
        )
        self.rename_summary_label.setText(
            f"{base} Rename previews new filenames before applying changes."
        )

        if hasattr(self, "convert_button"):
            has_selection = selected_count > 0
            self.convert_button.setEnabled(has_selection)
            self.merge_button.setEnabled(mergeable > 0)
            self.transcode_button.setEnabled(has_selection)
            self.trim_button.setEnabled(has_selection)
            self.rename_button.setEnabled(has_selection)

        # --- Persistent action bar ---
        if hasattr(self, "convert_primary_button") and hasattr(self, "action_bar_hint"):
            has_selection = selected_count > 0
            self.convert_primary_button.setEnabled(has_selection)
            if has_selection:
                needs_audio = sum(1 for rec in selected if rec.needs_audio_conversion)
                self.action_bar_hint.setText(
                    f"{selected_count} selected — {needs_audio} need conversion"
                )
            else:
                self.action_bar_hint.setText("Select recordings to convert")

    def _restore_geometry(self):
        from PyQt6.QtCore import QByteArray

        # Restore window geometry
        geom = self.config.get("window_geometry")
        if geom:
            try:
                self.restoreGeometry(QByteArray.fromHex(geom.encode()))
            except Exception:
                pass

        state = self.config.get("window_state")
        if state:
            try:
                self.restoreState(QByteArray.fromHex(state.encode()))
            except Exception:
                pass

        last_dir = self.config.get("last_open_dir")
        if last_dir:
            self.setWindowTitle(f"Clipwright — {Path(last_dir).name}")

    # --- Output destination ---

    def _output_mode(self) -> str:
        for mode, button in self.output_mode_buttons.items():
            if button.isChecked():
                return mode
        return "same_folder"

    def _output_mode_label(self) -> str:
        return {
            "same_folder": "Same folder",
            "subfolder": "Subfolder",
            "custom": "Choose folder",
        }.get(self._output_mode(), "Same folder")

    def _get_output_dir(self, prompt: str = "Choose Output Directory") -> Path | None:
        """Get the output directory based on settings or prompt the user."""
        # Check if "convert in place" is enabled
        if self.config.get("convert_in_place") == "true":
            return None  # Signal to use source directory

        # Check for default output dir
        default_dir = self.config.get("output_dir")
        if default_dir:
            return Path(default_dir)

        # Ask the user
        last_dir = self.config.get("last_open_dir") or str(Path.home())
        folder = choose_directory(self, prompt, last_dir)
        if not folder:
            return None
        return Path(folder)

    def _save_destination_settings(self, *args):
        mode = self._output_mode()
        self.config.set("output_mode", mode)
        if mode == "custom":
            self.config.set("output_dir", self.output_path_input.text())
        else:
            self.config.set("output_subfolder", self.output_path_input.text() or "converted")
        self.config.set("output_suffix", self.output_suffix_input.text())
        self.config.set("conflict_policy", self.conflict_combo.currentData())

    def _browse_destination(self):
        folder = choose_directory(
            self, "Choose Output Folder", self.config.get("output_dir") or str(Path.home())
        )
        if folder:
            self.output_mode_buttons["custom"].setChecked(True)
            self.output_path_input.setText(folder)
            self._save_destination_settings()

    def _destination_for(self, rec) -> Path | None:
        mode = self._output_mode()
        text = self.output_path_input.text().strip()
        if mode == "same_folder":
            return rec.primary_file.path.parent
        if mode == "subfolder":
            return rec.primary_file.path.parent / (text or "converted")
        if mode == "custom":
            if not text:
                self._browse_destination()
                text = self.output_path_input.text().strip()
            return Path(text) if text else None
        return rec.primary_file.path.parent

    def _confirm_conversion(self, recordings) -> bool:
        from clipwright.ui.dialogs.convert_dialog import (
            ConvertReviewDialog,
            build_conversion_plans,
        )

        suffix = self.output_suffix_input.text()
        conflict_policy = self.conflict_combo.currentData()

        destinations = []
        for rec in recordings:
            dest = self._destination_for(rec)
            if dest is None:
                return False
            destinations.append(dest)

        plans = build_conversion_plans(
            recordings,
            destinations,
            suffix,
            conflict_policy,
        )
        dialog = ConvertReviewDialog(
            recordings,
            plans,
            self._output_mode_label(),
            self.conflict_combo.currentText(),
            self,
        )
        return dialog.exec() == ConvertReviewDialog.DialogCode.Accepted

    # --- Actions ---

    def _open_folder(self):
        last_dir = self.config.get("last_open_dir") or str(Path.home())
        folder = choose_directory(self, "Open Camera Folder", last_dir)
        if folder:
            self.config.set("last_open_dir", folder)
            self.file_panel.load_directory(Path(folder))
            self.setWindowTitle(f"Clipwright — {Path(folder).name}")

    def _open_files(self):
        last_dir = self.config.get("last_open_dir") or str(Path.home())
        files = choose_video_files(self, "Add Video Files", last_dir)
        if files:
            paths = [Path(f) for f in files]
            self.config.set("last_open_dir", str(paths[0].parent))
            self.file_panel.load_paths(paths, append=bool(self.file_panel.recordings))
            self.setWindowTitle(f"Clipwright — {len(self.file_panel.recordings) + len(paths)} item(s)")

    def _convert_selected(self):
        recordings = self.file_panel.get_selected_recordings()
        if not recordings:
            self.status_bar.showMessage("No recordings selected")
            return

        if not self._confirm_conversion(recordings):
            return

        for rec in recordings:
            output_dir = self._destination_for(rec)
            if output_dir is None:
                return
            self.job_panel.submit_conversions(
                [rec],
                output_dir,
                output_suffix=self.output_suffix_input.text(),
                conflict_policy=self.conflict_combo.currentData(),
            )

    def _merge_selected(self):
        recordings = [
            r for r in self.file_panel.get_selected_recordings()
            if r.needs_merge
        ]
        if not recordings:
            self.status_bar.showMessage("No multi-chapter recordings selected")
            return

        output_dir = self._get_output_dir()
        if output_dir is None and self.config.get("convert_in_place") != "true":
            return

        if output_dir is None:
            for rec in recordings:
                source_dir = rec.primary_file.path.parent
                self.job_panel.submit_merges([rec], source_dir)
        else:
            self.job_panel.submit_merges(recordings, output_dir)

    def _open_transcode_dialog(self):
        from clipwright.ui.dialogs.transcode_dialog import TranscodeDialog

        recordings = self.file_panel.get_selected_recordings()
        if not recordings:
            self.status_bar.showMessage("No recordings selected")
            return

        dialog = TranscodeDialog(recordings, self.config, self)
        if dialog.exec():
            settings = dialog.get_settings()
            output_dir = dialog.get_output_dir()

            # Submit transcode jobs
            for rec in recordings:
                dest_dir = output_dir or rec.primary_file.path.parent
                self.job_panel.submit_transcodes([rec], dest_dir, settings)

    def _open_trim_dialog(self):
        from clipwright.ui.dialogs.trim_dialog import TrimDialog

        recordings = self.file_panel.get_selected_recordings()
        if not recordings:
            self.status_bar.showMessage("No recordings selected")
            return

        # Trim one recording at a time
        rec = recordings[0]
        dialog = TrimDialog(rec, self)
        if dialog.exec():
            trim_start, trim_end = dialog.get_trim_points()
            if trim_start is not None or trim_end is not None:
                output_dir = self._get_output_dir("Choose Output for Trimmed File")
                if output_dir is None and self.config.get("convert_in_place") != "true":
                    return
                dest_dir = output_dir or rec.primary_file.path.parent
                self.job_panel.submit_trim(rec, dest_dir, trim_start, trim_end)

    def _open_rename_dialog(self):
        from clipwright.ui.dialogs.rename_dialog import RenameDialog

        recordings = self.file_panel.get_selected_recordings()
        if not recordings:
            self.status_bar.showMessage("No recordings selected for renaming")
            return

        dialog = RenameDialog(recordings, self.config, self)
        dialog.exec()

    def _open_settings(self):
        from clipwright.ui.dialogs.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            # Apply changed settings
            self.thread_pool.setMaxThreadCount(self.config.get_int("parallel_jobs"))

    def _open_help(self):
        from clipwright.ui.dialogs.help_dialog import HelpDialog

        dialog = HelpDialog(self)
        dialog.exec()

    # --- Context menu handlers (accept recordings directly) ---

    def _convert_recordings(self, recordings):
        if not recordings:
            return
        if not self._confirm_conversion(recordings):
            return
        for rec in recordings:
            output_dir = self._destination_for(rec)
            if output_dir is None:
                return
            self.job_panel.submit_conversions(
                [rec],
                output_dir,
                output_suffix=self.output_suffix_input.text(),
                conflict_policy=self.conflict_combo.currentData(),
            )

    def _merge_recordings(self, recordings):
        if not recordings:
            return
        output_dir = self._get_output_dir()
        if output_dir is None and self.config.get("convert_in_place") != "true":
            return
        if output_dir is None:
            for rec in recordings:
                self.job_panel.submit_merges([rec], rec.primary_file.path.parent)
        else:
            self.job_panel.submit_merges(recordings, output_dir)

    def _transcode_recordings(self, recordings):
        from clipwright.ui.dialogs.transcode_dialog import TranscodeDialog

        if not recordings:
            return
        dialog = TranscodeDialog(recordings, self.config, self)
        if dialog.exec():
            settings = dialog.get_settings()
            output_dir = dialog.get_output_dir()
            for rec in recordings:
                dest_dir = output_dir or rec.primary_file.path.parent
                self.job_panel.submit_transcodes([rec], dest_dir, settings)

    def _trim_recording(self, recording):
        from clipwright.ui.dialogs.trim_dialog import TrimDialog

        dialog = TrimDialog(recording, self)
        if dialog.exec():
            trim_start, trim_end = dialog.get_trim_points()
            if trim_start is not None or trim_end is not None:
                output_dir = self._get_output_dir("Choose Output for Trimmed File")
                if output_dir is None and self.config.get("convert_in_place") != "true":
                    return
                dest_dir = output_dir or recording.primary_file.path.parent
                self.job_panel.submit_trim(recording, dest_dir, trim_start, trim_end)

    def _rename_recordings(self, recordings):
        from clipwright.ui.dialogs.rename_dialog import RenameDialog

        if not recordings:
            return
        dialog = RenameDialog(recordings, self.config, self)
        dialog.exec()

    def _on_recordings_loaded(self, count: int):
        self.status_bar.showMessage(f"Loaded {count} recording(s)")
        # Also populate thumbnail grid
        self.thumbnail_grid.set_recordings(self.file_panel.recordings)

    # --- Drag and Drop ---

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            paths = [Path(url.toLocalFile()) for url in urls if url.isLocalFile()]
            if not paths:
                return
            first = paths[0]
            self.config.set("last_open_dir", str(first if first.is_dir() else first.parent))
            self.file_panel.load_paths(paths, append=bool(self.file_panel.recordings))
            self.setWindowTitle(f"Clipwright — {len(paths)} item(s) added")

    def closeEvent(self, event):
        # Save window geometry
        self.config.set("window_geometry", bytes(self.saveGeometry().toHex()).decode())
        self.config.set("window_state", bytes(self.saveState().toHex()).decode())
        self.config.sync()
        super().closeEvent(event)
