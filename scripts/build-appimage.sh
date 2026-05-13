#!/bin/bash
set -euo pipefail

# Build an AppImage for Clipwright
# Usage: ./scripts/build-appimage.sh [version]
#   version defaults to the value in src/clipwright/__init__.py

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

VERSION="${1:-$(python3 -c "import re; print(re.search(r'__version__\s*=\s*\"(.+?)\"', open('src/clipwright/__init__.py').read()).group(1))")}"
APP_NAME="Clipwright"
ARCH="x86_64"
APPDIR="${APP_NAME}.AppDir"

echo "==> Building Clipwright v${VERSION} AppImage"

# Clean previous build
rm -rf "$APPDIR" build/

# --- Download standalone Python ---
PYTHON_VERSION="3.11.15"
PYTHON_BUILD="20260320"
PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_BUILD}/cpython-${PYTHON_VERSION}+${PYTHON_BUILD}-${ARCH}-unknown-linux-gnu-install_only.tar.gz"
PYTHON_TAR="build/python-standalone.tar.gz"
PYTHON_SHA256="413d40229a362e3b7b676b0dedad1eb543b0a1a5337dabf5b42818cdc4439911"

download_verified() {
    local url="$1"
    local output="$2"
    local sha256="$3"

    if [ ! -f "$output" ]; then
        echo "==> Downloading $(basename "$output")..."
        curl -L --fail --proto '=https' --tlsv1.2 -o "$output" "$url"
    fi

    printf '%s  %s\n' "$sha256" "$output" | sha256sum -c -
}

mkdir -p build
download_verified "$PYTHON_URL" "$PYTHON_TAR" "$PYTHON_SHA256"

# --- Create AppDir structure ---
echo "==> Creating AppDir..."
mkdir -p "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/scalable/apps"

# Extract Python into AppDir/usr
echo "==> Extracting Python..."
tar -xzf "$PYTHON_TAR" -C "$APPDIR/usr" --strip-components=1

# --- Install app and dependencies ---
echo "==> Installing Clipwright and dependencies..."
"$APPDIR/usr/bin/python3" -m pip install --no-cache-dir --upgrade pip
"$APPDIR/usr/bin/python3" -m pip install --no-cache-dir "$PROJECT_DIR"

# --- Trim unnecessary files to reduce size ---
echo "==> Trimming fat..."
SITE_PACKAGES="$APPDIR/usr/lib/python3.11/site-packages"
# Remove test suites, docs, and type stubs
find "$APPDIR/usr" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$APPDIR/usr" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$APPDIR/usr" -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
rm -rf "$APPDIR/usr/share/man" "$APPDIR/usr/share/doc"
rm -rf "$APPDIR/usr/lib/python3.11/test"
rm -rf "$APPDIR/usr/lib/python3.11/unittest"
# Remove pip/setuptools from the bundled image
"$APPDIR/usr/bin/python3" -m pip uninstall -y pip setuptools 2>/dev/null || true
rm -rf "$SITE_PACKAGES/pip" "$SITE_PACKAGES/setuptools"

# --- Desktop integration ---
cp assets/clipwright.desktop "$APPDIR/clipwright.desktop"
echo "X-AppImage-Version=${VERSION}" >> "$APPDIR/clipwright.desktop"
cp assets/clipwright.desktop "$APPDIR/usr/share/applications/"
echo "X-AppImage-Version=${VERSION}" >> "$APPDIR/usr/share/applications/clipwright.desktop"
cp assets/clipwright.svg "$APPDIR/clipwright.svg"
cp assets/clipwright.svg "$APPDIR/usr/share/icons/hicolor/scalable/apps/"

# --- AppRun entry point ---
cat > "$APPDIR/AppRun" << 'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
export PATH="$HERE/usr/bin:$PATH"
export LD_LIBRARY_PATH="$HERE/usr/lib:${LD_LIBRARY_PATH:-}"
export PYTHONHOME="$HERE/usr"
export PYTHONDONTWRITEBYTECODE=1
# Qt platform plugin path (bundled with PyQt6)
export QT_PLUGIN_PATH="$HERE/usr/lib/python3.11/site-packages/PyQt6/Qt6/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="$QT_PLUGIN_PATH/platforms"
exec "$HERE/usr/bin/python3" -m clipwright "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

# --- Download appimagetool and build ---
APPIMAGETOOL="build/appimagetool"
APPIMAGETOOL_VERSION="1.9.1"
APPIMAGETOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-x86_64.AppImage"
download_verified "$APPIMAGETOOL_URL" "$APPIMAGETOOL" "$APPIMAGETOOL_SHA256"
chmod +x "$APPIMAGETOOL"

echo "==> Packaging AppImage..."
VERSIONED="${APP_NAME}-${VERSION}-${ARCH}.AppImage"
STABLE="${APP_NAME}-${ARCH}.AppImage"
ARCH="$ARCH" "$APPIMAGETOOL" "$APPDIR" "$VERSIONED"
cp "$VERSIONED" "$STABLE"

echo ""
echo "==> Built: $VERSIONED ($(du -h "$VERSIONED" | cut -f1))"
echo "==> Stable: $STABLE"
