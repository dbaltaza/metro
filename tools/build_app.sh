#!/bin/bash
# Builds a double-clickable app with PyInstaller.
#
#   tools/build_app.sh            build only
#   tools/build_app.sh --install  build and copy the app into /Applications (macOS)
#
# On macOS the result is "dist/Metro Lisboa.app"; on Linux and Windows a
# folder "dist/Metro Lisboa" with an executable inside.
set -euo pipefail

cd "$(dirname "$0")/.."
NAME="Metro Lisboa"
VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' src/version.py)

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
    # PyInstaller writes 0.0.0; give Finder and the Info window the real one.
    PLIST="dist/$NAME.app/Contents/Info.plist"
    for key in CFBundleShortVersionString CFBundleVersion; do
        /usr/libexec/PlistBuddy -c "Set :$key $VERSION" "$PLIST" >/dev/null 2>&1 \
            || /usr/libexec/PlistBuddy -c "Add :$key string $VERSION" "$PLIST" >/dev/null
    done
    echo "Built dist/$NAME.app ($VERSION)"
    if [ "${1:-}" = "--install" ]; then
        TARGET=/Applications
        [ -w "$TARGET" ] || TARGET="$HOME/Applications"
        mkdir -p "$TARGET"
        rm -rf "$TARGET/$NAME.app"
        cp -R "dist/$NAME.app" "$TARGET/"
        echo "Installed $TARGET/$NAME.app"
    fi
else
    echo "Built dist/$NAME/"
fi
