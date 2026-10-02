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
  echo "    mingw-w64-ucrt-x86_64-pyinstaller \\" >&2
  echo "    mingw-w64-ucrt-x86_64-librsvg" >&2
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
  echo "  pacman -S --needed mingw-w64-ucrt-x86_64-gtk3 mingw-w64-ucrt-x86_64-python mingw-w64-ucrt-x86_64-python-gobject mingw-w64-ucrt-x86_64-python-cryptography mingw-w64-ucrt-x86_64-pyinstaller mingw-w64-ucrt-x86_64-librsvg" >&2
  exit 1
fi

# Keep MSYS from rewriting the Windows paths in this command line.
MSYS2_ARG_CONV_EXCL='*' python -m PyInstaller --noconfirm --windowed --onedir --name LocalPassword \
  --distpath "$WINROOT/dist/windows" \
  --workpath "$WINROOT/build/windows" \
  --specpath "$WINROOT/build/windows" \
  --runtime-hook "$WINROOT/packaging/windows/pyi_rth_gtk.py" \
  --hidden-import vault_sync \
  --add-data "$WINROOT/eff_large_wordlist.txt;." \
  --add-data "$WINROOT/eff_large_wordlist.LICENSE.txt;." \
  --add-data "$WINROOT/PRIVACY.md;." \
  --add-data "$WINROOT/SECURITY.md;." \
  --add-data "$WINROOT/USER_GUIDE.md;." \
  --add-data "$WINROOT/LICENSE;." \
  --icon "$WINROOT/packaging/windows/local-password.ico" \
  --add-data "$WINROOT/packaging/local-password.svg;." \
  --add-data "$WINROOT/packaging/windows/local-password.png;." \
  --add-data "$WINROOT/packaging/windows/scrub_icons.py;." \
  "$WINROOT/password_app.py"

mkdir -p \
  "$DEST/lib/girepository-1.0" \
  "$DEST/lib/gdk-pixbuf-2.0/2.10.0" \
  "$DEST/share/glib-2.0/schemas" \
  "$DEST/etc/fonts"
if [ ! -f "$PREFIX/lib/gdk-pixbuf-2.0/2.10.0/loaders/pixbufloader_svg.dll" ]; then
  echo "Missing the SVG icon loader. From the UCRT64 shell, install:" >&2
  echo "  pacman -S --needed mingw-w64-ucrt-x86_64-librsvg" >&2
  exit 1
fi
cp -a "$PREFIX/bin/"*.dll "$DEST/"
# PyInstaller searches _internal for DLLs. The SVG loader also needs those
# libraries beside itself, under both filenames Windows asks for.
mkdir -p "$DEST/_internal" "$DEST/lib/gdk-pixbuf-2.0/2.10.0/loaders"
cp -a "$PREFIX/bin/"*.dll "$DEST/_internal/"
cp -a "$PREFIX/lib/girepository-1.0/." "$DEST/lib/girepository-1.0/"
cp -a "$PREFIX/lib/gdk-pixbuf-2.0/2.10.0/." "$DEST/lib/gdk-pixbuf-2.0/2.10.0/"
cp -a "$PREFIX/share/glib-2.0/schemas/." "$DEST/share/glib-2.0/schemas/"
glib-compile-schemas "$DEST/share/glib-2.0/schemas"
loaders="$DEST/lib/gdk-pixbuf-2.0/2.10.0/loaders"
cp -a "$loaders/pixbufloader_svg.dll" "$loaders/libpixbufloader_svg.dll"
cp -a "$PREFIX/bin/"*.dll "$loaders/"
gdk-pixbuf-query-loaders > "$DEST/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache"
cp "$ROOT/packaging/windows/fonts.conf" "$DEST/etc/fonts/fonts.conf"

# Adwaita symbolic icons are SVG. The Windows SVG loader aborts GTK when it
# cannot open, including on the fallback image-missing icon. Keep the PNG icons.
# cygpath -m so Windows Python sees C:/Users/... even when MSYS leaves
# arguments that start with /c/ unconverted.
WINDEST=$(cygpath -m "$DEST")
WINBIN=$(cygpath -m "$PREFIX/bin")
python "$WINROOT/packaging/windows/scrub_icons.py" "$WINDEST" "$WINBIN"
cp "$ROOT/packaging/windows/SHARE.txt" "$DEST/Read-this.txt"
cp "$ROOT/packaging/windows/install.ps1" "$ROOT/dist/windows/install.ps1"
cp "$ROOT/packaging/windows/Install Local Password.cmd" "$ROOT/dist/windows/Install Local Password.cmd"

# The exe needs the libraries beside it. The zip is the file other people download.
python - "$WINDEST" "$WINROOT/dist/windows/LocalPassword-windows.zip" "$WINROOT/dist/windows" << 'PY'
import sys
import zipfile
from pathlib import Path

folder = Path(sys.argv[1])
archive_path = Path(sys.argv[2])
bundle = Path(sys.argv[3])
exe = folder / "LocalPassword.exe"
if not exe.is_file():
    raise SystemExit(f"Missing {exe}")
if archive_path.exists():
    archive_path.unlink()
with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for name in ("install.ps1", "Install Local Password.cmd"):
        path = bundle / name
        if path.is_file():
            archive.write(path, name)
    for path in folder.rglob("*"):
        if path.is_file():
            archive.write(path, "LocalPassword/" + path.relative_to(folder).as_posix())
print(f"Shareable zip: {archive_path}")
PY

echo "Built $DEST/LocalPassword.exe"
echo "Install it into the Start menu with: powershell.exe -NoProfile -ExecutionPolicy Bypass -File dist/windows/install.ps1 -Source dist/windows/LocalPassword"
echo "Other people unzip dist/windows/LocalPassword-windows.zip and double-click Install Local Password."
echo "The saved vault will be in %LOCALAPPDATA%\\local-password\\saved.vault"
