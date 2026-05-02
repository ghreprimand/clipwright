#!/bin/bash
# Resolve to this script's own directory so the launcher works regardless of where the repo lives
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$DIR"
export CLIPWRIGHT_QT_PLATFORM="${CLIPWRIGHT_QT_PLATFORM:-xcb}"
exec "$DIR/.venv/bin/python" -X faulthandler -m clipwright "$@"
