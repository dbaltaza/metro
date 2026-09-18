#!/bin/bash
# Builds a double-clickable app with PyInstaller.
#
#   tools/build_app.sh
#
# On macOS the result is "dist/Metro Lisboa.app" (drag it to Applications);
# on Linux and Windows a folder "dist/Metro Lisboa" with an executable inside.
set -euo pipefail

cd "$(dirname "$0")/.."
NAME="Metro Lisboa"

if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt pyinstaller

ICON_ARGS=()
if [ "$(uname)" = "Darwin" ]; then
    # macOS wants an .icns; build one from the pixel badge at several sizes.
    ICONSET=build/icon.iconset
    rm -rf "$ICONSET" && mkdir -p "$ICONSET"
    for size in 16 32 64 128 256 512; do
        sips -z $size $size docs/icon.png --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
        double=$((size * 2))
        sips -z $double $double docs/icon.png --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
    done
    iconutil -c icns "$ICONSET" -o build/icon.icns
    ICON_ARGS=(--icon build/icon.icns --osx-bundle-identifier pt.metro.lisboa)
fi

SEP=":"
case "$(uname)" in MINGW*|MSYS*|CYGWIN*) SEP=";";; esac

.venv/bin/pyinstaller --noconfirm --clean --windowed \
    --name "$NAME" \
    --add-data "data${SEP}data" \
    --add-data "docs/icon.png${SEP}docs" \
    "${ICON_ARGS[@]}" \
    init.py

echo
if [ "$(uname)" = "Darwin" ]; then
    echo "Built dist/$NAME.app"
else
    echo "Built dist/$NAME/"
fi
