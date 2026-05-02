"""Transcode dialog — resolution, codec, and quality conversion UI."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from clipwright.core.mediafile import Recording
from clipwright.core.presets import (
    delete_user_preset,
    get_all_presets,
    save_user_preset,
)
from clipwright.core.transcoder import (
    PRORES_PROFILES,
    QUALITY_PRESETS,
    RESOLUTION_PRESETS,
    SPEED_PRESETS,
    AudioCodec,
    Container,
    TranscodeSettings,
    VideoCodec,
    estimate_output_size,
)
from clipwright.ui.file_dialogs import choose_directory
from clipwright.util.config import Config


class TranscodeDialog(QDialog):
    def __init__(
        self,
        recordings: list[Recording],
        config: Config,
        parent=None,
    ):
        super().__init__(parent)
        self.recordings = recordings
        self.config = config
        self.setWindowTitle("Transcode / Convert")
        self.setMinimumSize(550, 600)
        self._setup_ui()
        self._on_codec_changed()
        self._update_estimate()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Preset selector ---
        preset_group = QGroupBox("Presets")
        preset_group.setWhatsThis(
            "Transcode preset profiles.\n\n"
            "Select a built-in or custom preset to quickly apply transcode settings. "
            "Click 'Save As...' to save your current configuration as a reusable preset. "
            "Custom presets are stored in ~/.config/clipwright/."
        )
        preset_layout = QHBoxLayout()

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Custom")
        self._presets = get_all_presets()
        for name in self._presets:
            self.preset_combo.addItem(name)
        self.preset_combo.currentTextChanged.connect(self._on_preset_selected)
        preset_layout.addWidget(self.preset_combo, stretch=1)

        save_preset_btn = QPushButton("Save As...")
        save_preset_btn.clicked.connect(self._save_preset)
        preset_layout.addWidget(save_preset_btn)

        delete_preset_btn = QPushButton("Delete")
        delete_preset_btn.clicked.connect(self._delete_preset)
        preset_layout.addWidget(delete_preset_btn)

        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        # Source info
        info_label = QLabel(f"<b>{len(self.recordings)} file(s) selected</b>")
        total_dur = sum(r.total_duration for r in self.recordings)
        mins = int(total_dur) // 60
        secs = int(total_dur) % 60
        info_label.setText(
            f"<b>{len(self.recordings)} file(s)</b> — total duration: {mins}m {secs}s"
        )
        layout.addWidget(info_label)

        # --- Video Settings ---
        video_group = QGroupBox("Video")
        video_layout = QFormLayout()

        # Codec
        self.codec_combo = QComboBox()
        self.codec_combo.addItems([
            "H.264 (best compatibility)",
            "H.265 / HEVC (smaller files)",
            "ProRes (editing codec)",
            "DNxHR (editing codec)",
            "Copy (no re-encode)",
        ])
        self.codec_combo.currentIndexChanged.connect(self._on_codec_changed)
        video_layout.addRow("Codec:", self.codec_combo)

        # Resolution
        self.resolution_combo = QComboBox()
        for name in RESOLUTION_PRESETS:
            self.resolution_combo.addItem(name)
        self.resolution_combo.currentIndexChanged.connect(self._update_estimate)
        video_layout.addRow("Resolution:", self.resolution_combo)

        # Quality mode
        self.quality_mode_widget = QWidget()
        qm_layout = QVBoxLayout(self.quality_mode_widget)
        qm_layout.setContentsMargins(0, 0, 0, 0)

        # CRF slider
        self.crf_widget = QWidget()
        crf_layout = QHBoxLayout(self.crf_widget)
        crf_layout.setContentsMargins(0, 0, 0, 0)
        self.crf_slider = QSlider(Qt.Orientation.Horizontal)
        self.crf_slider.setRange(0, 51)
        self.crf_slider.setValue(23)
        self.crf_slider.valueChanged.connect(self._on_crf_changed)
        self.crf_label = QLabel("23 (Medium)")
        self.crf_label.setMinimumWidth(140)
        crf_layout.addWidget(self.crf_slider)
        crf_layout.addWidget(self.crf_label)
        qm_layout.addWidget(self.crf_widget)

        # Bitrate override
        self.bitrate_check = QCheckBox("Use target bitrate instead")
        self.bitrate_check.toggled.connect(self._on_bitrate_toggled)
        qm_layout.addWidget(self.bitrate_check)

        self.bitrate_input = QLineEdit()
        self.bitrate_input.setPlaceholderText("e.g. 20M, 5000k")
        self.bitrate_input.setEnabled(False)
        self.bitrate_input.textChanged.connect(self._update_estimate)
        qm_layout.addWidget(self.bitrate_input)

        video_layout.addRow("Quality:", self.quality_mode_widget)

        # Speed preset
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(SPEED_PRESETS)
        self.speed_combo.setCurrentText("medium")
        video_layout.addRow("Encoding speed:", self.speed_combo)

        # ProRes profile (hidden by default)
        self.prores_combo = QComboBox()
        for name in PRORES_PROFILES:
            self.prores_combo.addItem(name)
        self.prores_combo.setCurrentText("Standard")
        self.prores_combo.currentIndexChanged.connect(self._update_estimate)
        self.prores_label = QLabel("Profile:")
        video_layout.addRow(self.prores_label, self.prores_combo)

        video_group.setLayout(video_layout)
        layout.addWidget(video_group)

        # --- Audio Settings ---
        audio_group = QGroupBox("Audio")
        audio_layout = QFormLayout()

        self.audio_combo = QComboBox()
        self.audio_combo.addItems([
            "AAC (compressed)",
            "PCM (uncompressed, editing-friendly)",
            "Copy (keep original)",
            "No audio",
        ])
        self.audio_combo.currentIndexChanged.connect(self._update_estimate)
        audio_layout.addRow("Audio codec:", self.audio_combo)

        self.audio_bitrate_combo = QComboBox()
        self.audio_bitrate_combo.addItems(["128k", "192k", "256k", "320k"])
        self.audio_bitrate_combo.setCurrentText("192k")
        audio_layout.addRow("Audio bitrate:", self.audio_bitrate_combo)

        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)

        # --- Output Settings ---
        output_group = QGroupBox("Output")
        output_layout = QFormLayout()

        self.container_combo = QComboBox()
        self.container_combo.addItems(["MP4 (.mp4)", "MOV (.mov)", "MKV (.mkv)"])
        output_layout.addRow("Container:", self.container_combo)

        # Output directory
        dir_layout = QHBoxLayout()
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText("Same as source")
        last_out = self.config.get("output_dir")
        if last_out:
            self.output_dir_input.setText(last_out)
        dir_layout.addWidget(self.output_dir_input)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output)
        dir_layout.addWidget(browse_btn)
        output_layout.addRow("Output folder:", dir_layout)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # --- Size Estimate ---
        self.estimate_label = QLabel("")
        self.estimate_label.setStyleSheet("font-size: 12px; color: palette(mid);")
        layout.addWidget(self.estimate_label)

        # --- Buttons ---
        button_box = QDialogButtonBox()
        self.transcode_btn = QPushButton("Start Transcode")
        self.transcode_btn.setDefault(True)
        button_box.addButton(self.transcode_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_codec_changed(self):
        idx = self.codec_combo.currentIndex()
        is_h26x = idx in (0, 1)
        is_prores = idx == 2
        is_copy = idx == 4

        # Show/hide quality controls
        self.quality_mode_widget.setVisible(is_h26x)
        self.speed_combo.setVisible(is_h26x)
        # Find the speed label in the form layout and hide it too
        self.speed_combo.parentWidget()  # The form layout manages visibility

        self.prores_combo.setVisible(is_prores)
        self.prores_label.setVisible(is_prores)

        self.resolution_combo.setEnabled(not is_copy)

        self._update_estimate()

    def _on_crf_changed(self, value: int):
        # Find the closest named preset
        closest_name = "Custom"
        for name, crf in QUALITY_PRESETS.items():
            if value == crf:
                closest_name = name
                break
        self.crf_label.setText(f"{value} ({closest_name})")
        self._update_estimate()

    def _on_bitrate_toggled(self, checked: bool):
        self.bitrate_input.setEnabled(checked)
        self.crf_slider.setEnabled(not checked)
        self._update_estimate()

    def _browse_output(self):
        folder = choose_directory(self, "Choose Output Directory")
        if folder:
            self.output_dir_input.setText(folder)

    def _update_estimate(self):
        settings = self.get_settings()
        total_dur = sum(r.total_duration for r in self.recordings)
        if total_dur <= 0:
            self.estimate_label.setText("")
            return
        source_res = self.recordings[0].resolution if self.recordings else (1920, 1080)
        est = estimate_output_size(total_dur, settings, source_res)
        self.estimate_label.setText(f"Estimated output size: {est}")

    def _on_preset_selected(self, name: str):
        """Load a preset's settings into the UI."""
        if name == "Custom":
            return
        settings = self._presets.get(name)
        if not settings:
            return
        self._apply_settings(settings)

    def _apply_settings(self, s: TranscodeSettings):
        """Set all UI controls from a TranscodeSettings object."""
        # Video codec
        codec_map = {
            VideoCodec.H264: 0, VideoCodec.H265: 1, VideoCodec.PRORES: 2,
            VideoCodec.DNXHD: 3, VideoCodec.COPY: 4,
        }
        self.codec_combo.setCurrentIndex(codec_map.get(s.video_codec, 0))

        # Resolution
        if s.resolution is None:
            self.resolution_combo.setCurrentIndex(0)  # "Original"
        else:
            # Try to find matching preset
            for i, (name, res) in enumerate(RESOLUTION_PRESETS.items()):
                if res == s.resolution:
                    self.resolution_combo.setCurrentIndex(i)
                    break

        # CRF / bitrate
        self.crf_slider.setValue(s.crf)
        if s.target_bitrate:
            self.bitrate_check.setChecked(True)
            self.bitrate_input.setText(s.target_bitrate)
        else:
            self.bitrate_check.setChecked(False)

        # Speed
        idx = self.speed_combo.findText(s.speed_preset)
        if idx >= 0:
            self.speed_combo.setCurrentIndex(idx)

        # ProRes profile
        for i, (name, val) in enumerate(PRORES_PROFILES.items()):
            if val == s.prores_profile:
                self.prores_combo.setCurrentIndex(i)
                break

        # Audio
        audio_map = {AudioCodec.AAC: 0, AudioCodec.PCM: 1, AudioCodec.COPY: 2, AudioCodec.NONE: 3}
        self.audio_combo.setCurrentIndex(audio_map.get(s.audio_codec, 0))

        idx = self.audio_bitrate_combo.findText(s.audio_bitrate)
        if idx >= 0:
            self.audio_bitrate_combo.setCurrentIndex(idx)

        # Container
        container_map = {Container.MP4: 0, Container.MOV: 1, Container.MKV: 2}
        self.container_combo.setCurrentIndex(container_map.get(s.container, 0))

        self._update_estimate()

    def _save_preset(self):
        """Save the current settings as a named preset."""
        name, ok = QInputDialog.getText(
            self, "Save Preset", "Preset name:"
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        settings = self.get_settings()
        save_user_preset(name, settings)
        # Refresh preset list
        self._presets = get_all_presets()
        self.preset_combo.clear()
        self.preset_combo.addItem("Custom")
        for n in self._presets:
            self.preset_combo.addItem(n)
        self.preset_combo.setCurrentText(name)

    def _delete_preset(self):
        """Delete the currently selected user preset."""
        name = self.preset_combo.currentText()
        if name == "Custom":
            return
        from clipwright.core.presets import BUILTIN_PRESETS
        if name in BUILTIN_PRESETS:
            QMessageBox.information(self, "Cannot Delete", "Built-in presets cannot be deleted.")
            return
        reply = QMessageBox.question(
            self, "Delete Preset", f"Delete preset '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_user_preset(name)
            self._presets = get_all_presets()
            self.preset_combo.clear()
            self.preset_combo.addItem("Custom")
            for n in self._presets:
                self.preset_combo.addItem(n)

    def get_settings(self) -> TranscodeSettings:
        """Build TranscodeSettings from the current UI state."""
        codec_map = [
            VideoCodec.H264, VideoCodec.H265, VideoCodec.PRORES,
            VideoCodec.DNXHD, VideoCodec.COPY,
        ]
        audio_map = [AudioCodec.AAC, AudioCodec.PCM, AudioCodec.COPY, AudioCodec.NONE]
        container_map = [Container.MP4, Container.MOV, Container.MKV]

        res_name = self.resolution_combo.currentText()
        resolution = RESOLUTION_PRESETS.get(res_name)

        prores_name = self.prores_combo.currentText()
        prores_profile = PRORES_PROFILES.get(prores_name, 2)

        settings = TranscodeSettings(
            video_codec=codec_map[self.codec_combo.currentIndex()],
            audio_codec=audio_map[self.audio_combo.currentIndex()],
            container=container_map[self.container_combo.currentIndex()],
            resolution=resolution,
            crf=self.crf_slider.value(),
            target_bitrate=self.bitrate_input.text() if self.bitrate_check.isChecked() else None,
            speed_preset=self.speed_combo.currentText(),
            prores_profile=prores_profile,
            audio_bitrate=self.audio_bitrate_combo.currentText(),
        )
        return settings

    def get_output_dir(self) -> Path | None:
        """Return the chosen output directory, or None for same-as-source."""
        text = self.output_dir_input.text().strip()
        return Path(text) if text else None
