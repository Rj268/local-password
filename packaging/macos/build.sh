#!/bin/bash
# Run on a Mac matching the desired architecture. No signing secrets are used.
set -euo pipefail
if [ "$(uname -s)" != Darwin ]; then
  echo "A macOS host is required to build a working Mac app and DMG." >&2
  exit 1
fi
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
PYTHON=${PYTHON:-python3}
ARCH=$(uname -m)
case "$ARCH" in arm64|x86_64) ;; *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;; esac
VERSION=$($PYTHON -c 'import ast; t=ast.parse(open("password_app.py").read()); print(next(n.value.value for n in t.body if isinstance(n,ast.Assign) and any(isinstance(v,ast.Name) and v.id=="APP_VERSION" for v in n.targets)))')
OUT="$ROOT/dist/macos-$ARCH"
BUILD="$ROOT/build/macos"
mkdir -p "$OUT" "$BUILD"
export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-15.0}"

# Generate only the Mac icon. Do not regenerate Android or Windows assets.
$PYTHON - "$ROOT/packaging/branding/app-icon.png" "$BUILD/LocalPassword.icns" <<'PY'
from PIL import Image
import sys
image = Image.open(sys.argv[1]).convert('RGBA')
image.save(sys.argv[2], format='ICNS')
PY
$PYTHON -m PyInstaller --noconfirm --clean --distpath "$OUT" --workpath "$BUILD/pyinstaller" packaging/macos/LocalPassword.spec
APP="$OUT/Local Password.app"
$PYTHON packaging/macos/verify_bundle.py "$APP" "$ARCH" "$OUT/bundle-verification.json"

STAGE=$(mktemp -d "$BUILD/dmg-stage.XXXXXX")
MOUNT=$(mktemp -d "$BUILD/dmg-mount.XXXXXX")
TEST_HOME=$(mktemp -d "$BUILD/test-home.XXXXXX")
MOUNTED=0
cleanup() {
  if [ "$MOUNTED" = 1 ]; then /usr/bin/hdiutil detach "$MOUNT" -quiet || true; fi
}
trap cleanup EXIT
/usr/bin/ditto "$APP" "$STAGE/Local Password.app"
ln -s /Applications "$STAGE/Applications"
cp packaging/macos/README.md "$STAGE/Read Me.md"
cp LICENSE "$STAGE/LICENSE.txt"
DMG="$OUT/LocalPassword-$VERSION-macos${MACOSX_DEPLOYMENT_TARGET%%.*}-$ARCH.dmg"
/usr/bin/hdiutil create -volname "Local Password $VERSION" -srcfolder "$STAGE" -format UDZO -ov "$DMG"
/usr/bin/hdiutil verify "$DMG"
/usr/bin/hdiutil attach "$DMG" -readonly -nobrowse -mountpoint "$MOUNT"
MOUNTED=1
test -L "$MOUNT/Applications"

# Start the mounted, read-only application with no Homebrew environment and an
# empty home directory. This checks the actual distributed app, not source Python.
$PYTHON - "$MOUNT/Local Password.app/Contents/MacOS/LocalPassword" "$TEST_HOME" "$OUT/smoke-test.json" <<'PY'
import os
import subprocess
import sys
executable, home, report = sys.argv[1:]
environment = {k: v for k, v in os.environ.items() if k in ('TMPDIR', 'USER', 'LOGNAME', 'LANG')}
environment.update(HOME=home, PATH='/usr/bin:/bin:/usr/sbin:/sbin')
subprocess.run([executable, '--self-test', report], env=environment, check=True, timeout=90)
PY
/usr/bin/codesign --verify --deep --strict "$MOUNT/Local Password.app"
/usr/bin/hdiutil detach "$MOUNT" -quiet
MOUNTED=0
(cd "$OUT" && /usr/bin/shasum -a 256 "$(basename "$DMG")" > SHA256SUMS.txt)
echo "Verified DMG: $DMG"
