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
  echo "    mingw-w64-ucrt-x86_64-pyinstaller" >&2
  exit 1
fi

ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
# PyInstaller is a Windows program. An MSYS path such as /c/Users, once it
# sits in a --add-data argument that contains ";", is left unconverted and
# Windows then reads it as C:/c/Users. cygpath -m yields C:/Users/...
WINROOT=$(cygpath -m "$ROOT")
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
  echo "  pacman -S --needed mingw-w64-ucrt-x86_64-gtk3 mingw-w64-ucrt-x86_64-python mingw-w64-ucrt-x86_64-python-gobject mingw-w64-ucrt-x86_64-python-cryptography mingw-w64-ucrt-x86_64-pyinstaller" >&2
  exit 1
fi

# Keep MSYS from rewriting the Windows paths in this command line.
MSYS2_ARG_CONV_EXCL='*' python -m PyInstaller --noconfirm --windowed --onedir --name LocalPassword \
  --distpath "$WINROOT/dist/windows" \
  --workpath "$WINROOT/build/windows" \
  --specpath "$WINROOT/build/windows" \
  --runtime-hook "$WINROOT/packaging/windows/pyi_rth_gtk.py" \
  --add-data "$WINROOT/eff_large_wordlist.txt;." \
  --add-data "$WINROOT/eff_large_wordlist.LICENSE.txt;." \
  --add-data "$WINROOT/packaging/local-password.svg;." \
  "$WINROOT/password_app.py"

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
# librsvg ships one of pixbufloader_svg.dll or libpixbufloader_svg.dll.
# Windows GTK tries both names, then loads that DLL from the loaders folder,
# where the matching dependency DLLs also have to be visible.
loaders="$DEST/lib/gdk-pixbuf-2.0/2.10.0/loaders"
for loader in "$loaders"/*.dll; do
  [ -e "$loader" ] || continue
  base=$(basename "$loader")
  if [ "${base#lib}" != "$base" ]; then
    cp -an "$loader" "$loaders/${base#lib}"
  else
    cp -an "$loader" "$loaders/lib$base"
  fi
done
for dll in "$DEST"/*.dll; do
  [ -e "$dll" ] || continue
  ln -f "$dll" "$loaders/$(basename "$dll")" 2>/dev/null || cp -a "$dll" "$loaders/"
done
gdk-pixbuf-query-loaders > "$DEST/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache"
cp "$ROOT/packaging/windows/fonts.conf" "$DEST/etc/fonts/fonts.conf"

echo "Built $DEST/LocalPassword.exe"
echo "Run that file on this Windows computer. The saved vault will be in %LOCALAPPDATA%\\local-password\\saved.vault"
