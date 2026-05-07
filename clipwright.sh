#!/bin/bash
# Resolve to this script's own directory so the launcher works regardless of where the repo lives
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$DIR"
unset QT_PLUGIN_PATH
# Let Qt auto-detect the platform (wayland on Wayland, xcb on X11)
unset CLIPWRIGHT_QT_PLATFORM
exec "$DIR/.venv/bin/python" -X faulthandler -m clipwright "$@"
