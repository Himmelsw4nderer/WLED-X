#!/usr/bin/env bash
# Builds a self-contained WLED-X.AppImage: bundles a portable CPython (with
# the backend + its dependencies pip-installed into it), the production
# frontend build, and libportaudio's shared libs, so the result runs on a
# bare Linux desktop without needing Python, Node, or `libportaudio2`
# preinstalled. Needs: internet access (to fetch the portable Python and
# appimagetool, both cached under build/ after the first run), npm, and a
# Linux x86_64 host (see PY_ARCH below for other architectures).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
WORK="$HERE/build"
OUT="$HERE/dist"
APPDIR="$WORK/AppDir"

PY_VERSION="3.13.15+20260901"
PY_ARCH="x86_64-unknown-linux-gnu"
PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20260901/cpython-${PY_VERSION/+/%2B}-${PY_ARCH}-install_only.tar.gz"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage"

mkdir -p "$WORK" "$OUT"

echo "==> 1/6 Building frontend"
(
    cd "$ROOT/frontend"
    if [ -f package-lock.json ]; then npm ci; else npm install; fi
    npm run build
)

echo "==> 2/6 Fetching portable CPython (cached after first run)"
PY_TARBALL="$WORK/cpython-${PY_ARCH}.tar.gz"
if [ ! -f "$PY_TARBALL" ]; then
    curl -L --fail -o "$PY_TARBALL" "$PY_URL"
fi
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr"
tar -xzf "$PY_TARBALL" -C "$APPDIR/usr"  # extracts to $APPDIR/usr/python/...
PYBIN="$APPDIR/usr/python/bin/python3"

echo "==> 3/6 Installing the backend + dependencies into the portable Python"
# Without this, a package already present in the *build host's* user site
# (~/.local/lib/pythonX.Y/site-packages, same Python minor version) reads as
# "already satisfied" and pip skips it -- leaving it missing from the bundle
# and silently depending on the build host's own state instead of being
# self-contained.
export PYTHONNOUSERSITE=1
"$PYBIN" -m pip install --disable-pip-version-check "$ROOT/backend"
PKG_DIR="$("$PYBIN" -c 'import pathlib, wled_x; print(pathlib.Path(wled_x.__file__).parent)')"
rm -rf "$PKG_DIR/static"
cp -r "$ROOT/frontend/dist" "$PKG_DIR/static"

echo "==> 4/6 Bundling libportaudio (sounddevice's runtime dependency on Linux)"
mkdir -p "$APPDIR/usr/lib"
# Captured to a variable first, then awk'd out of that -- piping ldconfig
# straight into an awk that `exit`s on its first match sends ldconfig a
# SIGPIPE the moment awk stops reading, which `pipefail` turns into a hard
# script failure even though the match was already found.
LDCONFIG_CACHE="$(ldconfig -p 2>/dev/null || true)"
for lib_name in libportaudio.so.2 libasound.so.2; do
    lib_path="$(awk -v n="$lib_name" '$1==n {print $NF; exit}' <<< "$LDCONFIG_CACHE")"
    if [ -n "$lib_path" ]; then
        cp -L "$lib_path" "$APPDIR/usr/lib/$lib_name"
        echo "    bundled $lib_name (from $lib_path)"
    else
        echo "    WARNING: $lib_name not found on this build host -- target systems will need it installed"
    fi
done

echo "==> 5/6 Assembling AppDir metadata"
ICON_SVG="$ROOT/frontend/public/favicon.svg"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps" "$APPDIR/usr/share/applications"
magick -background none -density 384 "$ICON_SVG" -resize 256x256 "$APPDIR/wled-x.png"
cp "$APPDIR/wled-x.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/wled-x.png"

cat > "$APPDIR/wled-x.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=WLED-X
Comment=Self-hosted lighting controller for WLED devices
Exec=wled-x
Icon=wled-x
Categories=AudioVideo;Utility;
Terminal=false
EOF
cp "$APPDIR/wled-x.desktop" "$APPDIR/usr/share/applications/wled-x.desktop"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$(readlink -f "${0}")")" && pwd)"

export LD_LIBRARY_PATH="$HERE/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
# Keep the bundled interpreter from picking up anything in the host user's
# own ~/.local/lib/pythonX.Y/site-packages (see build.sh) -- self-contained
# means self-contained at runtime too, not just at build time.
export PYTHONNOUSERSITE=1

DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/wled-x"
mkdir -p "$DATA_DIR"
export WLEDX_DB_PATH="${WLEDX_DB_PATH:-$DATA_DIR/wled_x.db}"
# No source tree to watch in a frozen bundle, and a stray reloader subprocess
# would just double-start the render loop / audio capture.
export WLEDX_RELOAD=0

PORT="${WLEDX_PORT:-8000}"
(
    sleep 1
    command -v xdg-open >/dev/null 2>&1 && xdg-open "http://127.0.0.1:$PORT" >/dev/null 2>&1 || true
) &

exec "$HERE/usr/python/bin/python3" -m wled_x.main
EOF
chmod +x "$APPDIR/AppRun"

echo "==> 6/6 Running appimagetool"
APPIMAGETOOL="$WORK/appimagetool-x86_64.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
    curl -L --fail -o "$APPIMAGETOOL" "$APPIMAGETOOL_URL"
    chmod +x "$APPIMAGETOOL"
fi

VERSION="$(cd "$ROOT/backend" && "$PYBIN" -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')"
rm -f "$OUT"/WLED-X-*.AppImage
ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$OUT/WLED-X-${VERSION}-x86_64.AppImage"

echo
echo "==> Done: $OUT/WLED-X-${VERSION}-x86_64.AppImage"
