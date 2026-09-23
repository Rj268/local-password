#!/bin/sh
# Build an architecture-independent Debian package for the local window.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
VERSION=1.0.0
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
PKG="$STAGE/local-password"

mkdir -p \
  "$PKG/DEBIAN" \
  "$PKG/usr/bin" \
  "$PKG/usr/share/local-password" \
  "$PKG/usr/share/applications" \
  "$PKG/usr/share/doc/local-password" \
  "$PKG/usr/share/icons/hicolor/scalable/apps"

install -m 0755 "$ROOT/packaging/local-password" "$PKG/usr/bin/local-password"
install -m 0755 "$ROOT/packaging/random-password-generator" "$PKG/usr/bin/random-password-generator"
install -m 0644 \
  "$ROOT/password_app.py" \
  "$ROOT/random_password_generator.py" \
  "$ROOT/eff_large_wordlist.txt" \
  "$ROOT/eff_large_wordlist.LICENSE.txt" \
  "$ROOT/packaging/local-password.svg" \
  "$PKG/usr/share/local-password/"
install -m 0644 "$ROOT/packaging/local-password.desktop" "$PKG/usr/share/applications/local-password.desktop"
install -m 0644 "$ROOT/packaging/local-password.svg" \
  "$PKG/usr/share/icons/hicolor/scalable/apps/local-password.svg"
install -m 0644 "$ROOT/eff_large_wordlist.LICENSE.txt" \
  "$PKG/usr/share/doc/local-password/eff_large_wordlist.LICENSE.txt"

cat > "$PKG/usr/share/doc/local-password/copyright" <<'EOF'
Local Password generates a password in a local window.

The Debian package installs that window. Copy is the only way a password leaves.
The program does not write the password to disk.

The EFF large wordlist is included unmodified.
Joseph Bonneau and the Electronic Frontier Foundation created it.
It is used under CC BY 3.0 US.
https://creativecommons.org/licenses/by/3.0/us/
The EFF does not endorse this project.
EOF

cat > "$PKG/DEBIAN/control" <<EOF
Package: local-password
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-3.0, xclip
Maintainer: Local Password <local-password@localhost>
Description: Air-gapped password generator
 Generate a password in a local window and copy it.
 The password is not written to disk and the app does not open a network port.
EOF

cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q /usr/share/applications || true
fi
EOF
chmod 0755 "$PKG/DEBIAN/postinst"

mkdir -p "$ROOT/dist"
dpkg-deb --root-owner-group --build "$PKG" "$ROOT/dist/local-password_${VERSION}_all.deb"
echo "Built $ROOT/dist/local-password_${VERSION}_all.deb"
