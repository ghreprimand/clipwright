# Clipwright

Clipwright is a Linux desktop utility for preparing camera and video files before editing. It is built around a practical workflow: add files or folders, inspect the media, choose an output destination, and run conversion jobs that make the files easier to use in Linux editing tools.

The original itch was DaVinci Resolve on Linux and its AAC audio limitations, but Clipwright is not only a Resolve helper. It is a general media-prep workbench for remuxing, audio conversion, camera chapter handling, transcodes, trims, and batch organization.

## What It Does

- Imports individual files, folders, or drag-and-dropped media
- Inspects media with `ffprobe`
- Shows duration, resolution, frame rate, video codec, audio codec, size, and thumbnails
- Flags AAC audio that may need conversion for Linux editing workflows
- Converts AAC audio to PCM in a `.mov` container while copying video without re-encoding
- Lets you choose output behavior before jobs start:
  - same folder
  - named subfolder
  - custom output folder
  - filename suffix
  - rename-or-overwrite conflict policy
- Merges GoPro chapter files losslessly
- Transcodes to H.264, H.265/HEVC, ProRes, DNxHR, or stream copy
- Provides reusable transcode presets
- Performs quick stream-copy trims
- Batch-renames files using metadata tokens
- Runs jobs in the background with progress and output-folder access

## Why It Exists

Many cameras, screen recorders, and phones write MP4/MOV files with AAC audio. That is fine for playback, but it can be awkward in some Linux editing workflows. DaVinci Resolve on Linux is the common example: the video imports, but the AAC audio may be silent or unavailable.

The fastest reliable fix is often:

```bash
ffmpeg -i input.mp4 -c:v copy -c:a pcm_s16le output.mov
```

Clipwright turns that fix, and the surrounding file-management work, into a desktop workflow.

## Workflow

1. **Add media**

   Use **Add Files**, **Add Folder**, or drag files/folders into the media list. Dropping a file imports that file directly; it does not scan the whole parent folder.

2. **Inspect**

   Select a row to see metadata and a thumbnail. AAC audio is highlighted so you can quickly see what likely needs conversion.

3. **Choose destination**

   Pick whether outputs go next to the source, into a subfolder, or into a custom folder. Set the output suffix and conflict behavior before starting a job.

4. **Run an operation**

   Use **Convert Audio**, **Merge Chapters**, **Transcode**, **Trim**, or **Batch Rename**. Conversion jobs show a preflight summary before they start.

5. **Open output**

   Completed jobs include an **Open Folder** button.

## Main Tools

### Convert Audio

Converts the audio stream to PCM while copying the video stream. This avoids generation loss and is usually much faster than a full transcode.

Default output:

```text
source_name_pcm.mov
```

### Merge Chapters

GoPro cameras split long recordings into chapter files. Clipwright detects those groups and can concatenate them without re-encoding.

### Transcode

Use the transcode dialog for full re-encoding or stream-copy presets:

- H.264
- H.265/HEVC
- ProRes
- DNxHR
- stream copy
- AAC / PCM / copied / stripped audio
- resolution presets
- CRF or target bitrate
- reusable presets

### Trim

Quickly remove unwanted heads/tails with stream-copy trimming.

### Batch Rename

Rename files using metadata tokens:

```text
{date}_{camera}_{clip_id}_{index}
```

Useful tokens include `{date}`, `{time}`, `{datetime}`, `{camera}`, `{clip_id}`, `{resolution}`, `{fps}`, `{duration}`, `{index}`, and `{original}`.

## Supported Inputs

Clipwright currently scans common video/camera extensions:

- `.mp4`
- `.mov`
- `.mkv`
- `.avi`
- `.m4v`
- `.mts`
- `.m2ts`
- `.webm`
- GoPro sidecars: `.lrv`, `.thm`, `.wav`
- DJI proxy sidecars: `.lrf`

It recognizes GoPro and DJI Action naming patterns, including DJI files shaped like `DJI_20250816174012_0001_D.MP4` with matching `.LRF` proxy files. Unknown camera files still load as normal video files.

## Requirements

- Linux
- Python 3.11+
- PyQt6
- `ffmpeg`
- `ffprobe`

On Debian/Ubuntu:

```bash
sudo apt install ffmpeg python3-venv
```

## Install From Source

```bash
git clone git@github.com:ghreprimand/clipwright.git
cd clipwright
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run:

```bash
clipwright
```

Or from the checkout:

```bash
./clipwright.sh
```

## Development

```bash
source .venv/bin/activate
pip install -e '.[dev]'
ruff check src
python -m py_compile $(rg --files src -g '*.py')
```

The Python package is `clipwright`. Runtime settings are stored under `~/.config/clipwright/`, and thumbnails are cached under `~/.cache/clipwright/`.

## Project Structure

```text
src/clipwright/
├── app.py
├── core/
│   ├── converter.py
│   ├── ffmpeg.py
│   ├── mediafile.py
│   ├── merger.py
│   ├── presets.py
│   ├── renamer.py
│   ├── scanner.py
│   └── transcoder.py
├── ui/
│   ├── dialogs/
│   ├── widgets/
│   ├── filepanel.py
│   ├── jobpanel.py
│   ├── mainwindow.py
│   └── previewpanel.py
└── util/
    ├── config.py
    └── paths.py
```

## Public Roadmap

- Better stream-level inspection
- Job cancel/retry/log controls
- More explicit output filename preview for all operations
- Audio extraction presets
- Proxy/intermediate workflow polish
- More conflict policies, including skip and ask
- More camera/file naming patterns

## License

GPL-3.0-only. See `LICENSE`.

Clipwright uses PyQt6, which is available under GPL v3 or a commercial license. GPL-3.0-only keeps the application license aligned with that dependency. If the GUI is later migrated to PySide6, a more permissive license could be reconsidered.
