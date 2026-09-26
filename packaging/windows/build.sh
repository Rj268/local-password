#!/bin/bash
# Build LocalPassword.exe on a Windows computer, inside the MSYS2 UCRT64 shell.
# This script cannot run on Linux. GTK's Windows libraries come from MSYS2.
set -eu

if [ "${MSYSTEM:-}" != "UCRT64" ]; then
  echo "Open the MSYS2 UCRT64 shell on Windows, then run this script." >&2
  echo "Install MSYS2 from https://www.msys2.org/ if that shell is not there." >&2
  echo "Then install the build tools:" >&2
  echo "  pacman -S --needed \\" >&2
  echo "    mingw-w64-ucrt-x86_64-gtk3 \\" >&2
  echo "    mingw-w64-ucrt-x86_64-python \\" >&2
  echo "    mingw-w64-ucrt-x86_64-python-gobject \\" >&2
  echo "    mingw-w64-ucrt-x86_64-python-cryptography \\" >&2
  echo "    mingw-w64-ucrt-x86_64-python-pyinstaller" >&2
  exit 1
fi

ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
PREFIX="${MINGW_PREFIX:-/ucrt64}"
DEST="$ROOT/dist/windows/LocalPassword"

missing=0
for tool in python pyinstaller gdk-pixbuf-query-loaders glib-compile-schemas; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing $tool." >&2
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  echo "From the UCRT64 shell, install:" >&2
  echo "  pacman -S --needed mingw-w64-ucrt-x86_64-gtk3 mingw-w64-ucrt-x86_64-python mingw-w64-ucrt-x86_64-python-gobject mingw-w64-ucrt-x86_64-python-cryptography mingw-w64-ucrt-x86_64-python-pyinstaller" >&2
  exit 1
fi

python -m PyInstaller --noconfirm --windowed --onedir --name LocalPassword \
  --distpath "$ROOT/dist/windows" \
  --workpath "$ROOT/build/windows" \
  --specpath "$ROOT/build/windows" \
  --runtime-hook "$ROOT/packaging/windows/pyi_rth_gtk.py" \
  --add-data "$ROOT/eff_large_wordlist.txt;." \
  --add-data "$ROOT/eff_large_wordlist.LICENSE.txt;." \
  --add-data "$ROOT/packaging/local-password.svg;." \
  "$ROOT/password_app.py"

mkdir -p \
  "$DEST/lib/girepository-1.0" \
  "$DEST/lib/gdk-pixbuf-2.0/2.10.0" \
  "$DEST/share/glib-2.0/schemas" \
  "$DEST/etc/fonts"
cp -a "$PREFIX/bin/"*.dll "$DEST/"
cp -a "$PREFIX/lib/girepository-1.0/." "$DEST/lib/girepository-1.0/"
cp -a "$PREFIX/lib/gdk-pixbuf-2.0/2.10.0/." "$DEST/lib/gdk-pixbuf-2.0/2.10.0/"
cp -a "$PREFIX/share/glib-2.0/schemas/." "$DEST/share/glib-2.0/schemas/"
glib-compile-schemas "$DEST/share/glib-2.0/schemas"
gdk-pixbuf-query-loaders > "$DEST/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache"
cp "$ROOT/packaging/windows/fonts.conf" "$DEST/etc/fonts/fonts.conf"

echo "Built $DEST/LocalPassword.exe"
echo "Run that file on this Windows computer. The saved vault will be in %LOCALAPPDATA%\\local-password\\saved.vault"
