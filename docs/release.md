# Release Process

Clipwright publishes Linux builds and source artifacts from GitHub tags.

## Recommended Public Artifact

Use a GitHub Release with an x86_64 AppImage as the primary public install
option. That gives Linux users a single downloadable file and avoids
distro-specific Python, Qt, and PyQt packaging differences.

The current AppImage bundles Python and PyQt6. Users still need `ffmpeg` and
`ffprobe` installed on the host system.

The release workflow also uploads Python source/package artifacts from `dist/`.
GitHub automatically adds source archives for each tag as well.

## Release Checklist

1. Update the version in `pyproject.toml` and `src/clipwright/__init__.py`.
2. Run local checks:

   ```bash
   source .venv/bin/activate
   pip install -e '.[dev]'
   ruff check src tests
   python -m compileall -q src tests
   pytest -q
   pip-audit
   python -m build --sdist --wheel
   ```

3. Commit the version bump and release notes.
4. Create and push a signed tag:

   ```bash
   git tag -s v1.0.0 -m "Clipwright 1.0.0"
   git push origin v1.0.0
   ```

5. The GitHub Actions release workflow will lint, compile, test, audit, build
   source/package artifacts, build the AppImage, upload all artifacts, and
   create the GitHub Release using `docs/release-notes/v1.0.0.md`.

## Longer-Term Packaging

AppImage is the simplest first release target. For broader desktop integration,
add Flatpak/Flathub after the AppImage path is stable. Flatpak is a better fit
when Clipwright is ready for portal-aware file access, automatic app-store style
updates, and packaged ffmpeg dependencies.
