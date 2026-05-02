"""Help system — general help dialog and contextual "What's This?" tooltips."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
)


# Contextual help text for What's This mode
WHATSTHIS = {
    "open_folder": (
        "Add a folder containing camera or video files.\n"
        "Clipwright scans GoPro, DJI Action, and common video files, detects codecs, "
        "and groups GoPro chapters automatically."
    ),
    "open_files": (
        "Add one or more individual video files.\n\n"
        "Use this when you want to import specific clips instead of scanning a whole folder."
    ),
    "convert": (
        "Convert Audio workflow.\n\n"
        "Choose where outputs go, set the filename suffix and conflict policy, then review "
        "the exact source/output plan before starting. Video is copied without re-encoding; "
        "AAC audio is converted to PCM signed 16-bit audio in a MOV container."
    ),
    "merge": (
        "Merge workflow.\n\n"
        "Joins selected multi-chapter recordings into single files without re-encoding. "
        "This is mainly for cameras such as GoPro that split long recordings into chunks."
    ),
    "transcode": (
        "Re-encode video with different resolution, codec, or quality.\n\n"
        "Similar to Handbrake — choose H.264, H.265, ProRes, or DNxHR output. "
        "Set a target resolution, quality level (CRF), or bitrate. "
        "Useful for creating smaller sharing copies or converting to editing codecs.\n\n"
        "Use the Presets dropdown to quickly apply saved configurations, "
        "or configure your own and click 'Save As...' to keep it."
    ),
    "rename": (
        "Batch rename files using a template.\n\n"
        "Available tokens: {date}, {time}, {datetime}, {camera}, {clip_id}, "
        "{resolution}, {fps}, {duration}, {index}, {original}.\n\n"
        "Preview shows exactly what filenames will look like before you commit. "
        "The default template can be changed in Settings."
    ),
    "trim": (
        "Trim workflow.\n\n"
        "Set rough in/out points for the first selected recording. Uses stream copy, "
        "so it is fast and does not re-encode when the source allows it. "
        "Quick buttons let you skip the first/last 5 or 10 seconds."
    ),
    "settings": (
        "Configure application preferences.\n\n"
        "Default output directory, convert-in-place mode, number of parallel "
        "jobs, default rename template, "
        "and whether to auto-open the output folder when jobs finish."
    ),
    "file_panel": (
        "File list showing all detected recordings.\n\n"
        "Select rows for focused operations or use checkboxes for batch operations. "
        "GoPro chapter groups are shown as expandable tree nodes. The Audio column "
        "shows red if a file likely needs audio conversion.\n\n"
        "Right-click any file for a context menu with all available actions."
    ),
    "operations": (
        "Operation tabs.\n\n"
        "Choose Convert Audio, Merge, Transcode, Trim, or Rename. Each tab shows the "
        "current selection context plus the controls and run button for that workflow."
    ),
    "convert_output": (
        "Convert Audio output controls.\n\n"
        "Same folder writes next to each source file. Subfolder writes into a named "
        "folder beside each source. Choose folder writes all outputs into one custom "
        "folder. Suffix and conflict policy control output filenames."
    ),
    "remove": "Remove selected rows from the current list without deleting files from disk.",
    "clear": "Clear the current list. This does not delete source files or completed outputs.",
    "select_all": "Check every loaded top-level recording for batch operations.",
    "select_none": "Uncheck every loaded recording.",
    "preview_panel": (
        "Shows a thumbnail and metadata for the selected recording.\n\n"
        "Displays resolution, framerate, duration, codecs, and editing compatibility status."
    ),
    "thumbnail_grid": (
        "Visual grid of video thumbnails for all loaded recordings.\n\n"
        "Click any thumbnail to view its details in the Details tab. "
        "Files with AAC audio show a red 'AAC' badge."
    ),
    "job_panel": (
        "Shows active and completed conversion/transcode jobs.\n\n"
        "Each job displays a progress bar and status. Jobs run in parallel "
        "(configurable in Settings). Completed jobs show an 'Open Folder' "
        "button to jump to the output in your file manager. "
        "Click 'Clear Completed' to remove finished jobs from the list."
    ),
    "presets": (
        "Transcode preset profiles.\n\n"
        "Select a built-in or custom preset to quickly apply transcode settings. "
        "Click 'Save As...' to save your current configuration as a reusable preset. "
        "Custom presets are stored in ~/.config/clipwright/."
    ),
}


class HelpDialog(QDialog):
    """General help dialog with overview of all features."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clipwright Help")
        self.setMinimumSize(600, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # Overview tab
        overview = self._make_scroll_tab(_HELP_OVERVIEW)
        tabs.addTab(overview, "Overview")

        # Workflow tab
        workflow = self._make_scroll_tab(_HELP_WORKFLOW)
        tabs.addTab(workflow, "Workflow Guide")

        # Keyboard shortcuts
        shortcuts = self._make_scroll_tab(_HELP_SHORTCUTS)
        tabs.addTab(shortcuts, "Shortcuts")

        # About
        from clipwright import __version__

        about = self._make_scroll_tab(_HELP_ABOUT.format(version=__version__))
        tabs.addTab(about, "About")

        layout.addWidget(tabs)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.close)
        layout.addWidget(button_box)

    def _make_scroll_tab(self, html: str) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QLabel(html)
        content.setWordWrap(True)
        content.setTextFormat(Qt.TextFormat.RichText)
        content.setAlignment(Qt.AlignmentFlag.AlignTop)
        content.setContentsMargins(12, 12, 12, 12)
        scroll.setWidget(content)
        return scroll


_HELP_OVERVIEW = """
<h2>Clipwright</h2>
<p>A desktop app for preparing camera and video files for Linux editing workflows.</p>

<h3>Why does this exist?</h3>
<p>Many camera files use <b>AAC audio</b>, which can be awkward in Linux editing
workflows. DaVinci Resolve on Linux is the most common pain point: video imports,
but audio may be silent.</p>
<p>Clipwright fixes that by converting audio to editing-friendly formats while copying
the video stream untouched when possible &mdash; fast and lossless for video.</p>

<h3>Features</h3>
<ul>
<li><b>Operation Tabs</b> &mdash; Convert Audio, Merge, Transcode, Trim, and Rename workflows</li>
<li><b>Convert Audio</b> &mdash; batch AAC-to-PCM audio conversion</li>
<li><b>Merge Chapters</b> &mdash; join GoPro's split chapter files into one</li>
<li><b>Transcode</b> &mdash; re-encode to different resolution/codec/quality (like Handbrake)</li>
<li><b>Preset Profiles</b> &mdash; 8 built-in presets + save your own custom presets</li>
<li><b>Rename</b> &mdash; template-based file renaming with metadata tokens</li>
<li><b>Quick Trim</b> &mdash; set in/out points to remove junk footage</li>
<li><b>Camera Detection</b> &mdash; auto-identifies GoPro and DJI Action 4 files</li>
<li><b>Thumbnail Grid</b> &mdash; visual clip identification with AAC badges</li>
<li><b>Right-Click Menus</b> &mdash; quick access to all operations per file</li>
<li><b>Job Queue</b> &mdash; parallel processing with progress bars and "Open Folder" on completion</li>
<li><b>Settings</b> &mdash; default output dir, convert-in-place, parallel jobs, auto-open behavior, and rename template</li>
</ul>

<h3>Contextual Help</h3>
<p>Click the <b>?</b> button in the toolbar (or press <b>Shift+F1</b>) then click on any
part of the app to see a description of what it does. Operation tabs, output controls,
file lists, preview panels, and the job queue expose targeted help.</p>
"""

_HELP_WORKFLOW = """
<h2>Typical Workflow</h2>

<h3>1. Import footage</h3>
<p>Add individual files, add a folder, or drag-and-drop files/folders onto the app.
Clipwright scans the selected media, detects camera types (GoPro, DJI Action), reads
metadata via ffprobe, and groups GoPro chapter files automatically.</p>

<h3>2. Review files</h3>
<p>Use the <b>file list</b> (left panel) and <b>thumbnail grid</b> (Thumbnails tab) to identify
your clips. Click any file or thumbnail to see detailed metadata in the <b>Details</b> tab,
including resolution, framerate, duration, codecs, and editing compatibility status.</p>
<p>Files with AAC audio are flagged in red &mdash; these are good candidates for audio conversion.</p>

<h3>3. Choose an operation</h3>
<p>Use the operation tabs above the file list: <b>Convert Audio</b>, <b>Merge</b>,
<b>Transcode</b>, <b>Trim</b>, or <b>Rename</b>. Each tab contains the controls and
execution button for that workflow.</p>

<h3>4. Convert audio</h3>
<p>In the <b>Convert Audio</b> tab, choose the destination mode, suffix, and conflict
behavior, then review the planned source/output changes before starting. This creates
.mov files with PCM audio. Video is copied without re-encoding.</p>

<h3>5. Optional: Merge GoPro chapters</h3>
<p>If you have long GoPro recordings split across multiple files (GH010705, GH020705, etc.),
use the <b>Merge</b> tab to join them losslessly into a single file.</p>

<h3>6. Optional: Transcode</h3>
<p>If you need to downscale resolution, change codecs, or reduce file size, use the
<b>Transcode</b> feature (Ctrl+T). Choose from built-in presets like "Sharing Copy (1080p)"
or "Archive (H.265 High Quality)", or configure your own settings and save them as a custom
preset for next time.</p>

<h3>7. Optional: Quick Trim</h3>
<p>Use <b>Trim</b> to set in/out points and remove dead footage. Quick buttons let you
skip the first or last 5/10 seconds. Uses stream copy so it's fast.</p>

<h3>8. Optional: Rename</h3>
<p>Use <b>Rename</b> (F2) to organize files with meaningful names. Templates support
tokens like {date}, {camera}, {clip_id}, and {index} for sequential numbering. A live preview
shows exactly what the filenames will look like.</p>

<h3>9. Open output &amp; import to your editor</h3>
<p>Click the <b>Open Folder</b> button on any completed job to open the output directory in
your file manager. Drag the converted files into your editor.</p>

<h3>Right-click shortcut</h3>
<p>You can also right-click any file in the list for quick access to Convert, Merge, Transcode,
Trim, Rename, and Open Containing Folder.</p>
"""

_HELP_SHORTCUTS = """
<h2>Keyboard Shortcuts</h2>
<table cellpadding="6">
<tr><td><b>Ctrl+O</b></td><td>Add files</td></tr>
<tr><td><b>Ctrl+Shift+O</b></td><td>Add folder</td></tr>
<tr><td><b>Ctrl+Return</b></td><td>Convert selected audio</td></tr>
<tr><td><b>Ctrl+T</b></td><td>Transcode selected</td></tr>
<tr><td><b>F2</b></td><td>Batch rename</td></tr>
<tr><td><b>Ctrl+A</b></td><td>Select all files</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>Quit</td></tr>
<tr><td><b>F1</b></td><td>Open this help dialog</td></tr>
<tr><td><b>Shift+F1</b></td><td>What's This? mode (click any UI element for help)</td></tr>
</table>

<h3>Right-Click Menu</h3>
<p>Right-click any file in the file list for a context menu with:</p>
<ul>
<li>Convert Audio</li>
<li>Merge Chapters (if applicable)</li>
<li>Transcode</li>
<li>Quick Trim</li>
<li>Rename</li>
<li>Open Containing Folder</li>
</ul>
"""

_HELP_ABOUT = """
<h2>About Clipwright</h2>
<p><b>Version {version}</b></p>
<p>Built with Python and PyQt6. Uses ffmpeg/ffprobe for all media processing.</p>
<p>Designed for preparing camera and video files for Linux editing workflows.</p>

<h3>Configuration</h3>
<table cellpadding="4">
<tr><td><b>Settings</b></td><td>~/.config/clipwright/ (QSettings)</td></tr>
<tr><td><b>Presets</b></td><td>~/.config/clipwright/transcode_presets.json</td></tr>
<tr><td><b>Thumbnails</b></td><td>~/.cache/clipwright/thumbnails/</td></tr>
</table>

<h3>Dependencies</h3>
<ul>
<li>Python 3.11+</li>
<li>PyQt6</li>
<li>ffmpeg &amp; ffprobe (system package)</li>
</ul>
"""
