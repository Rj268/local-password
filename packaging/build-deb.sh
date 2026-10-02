#!/bin/sh
# Build an architecture-independent Debian package for the local window.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
VERSION=1.31.0
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
  "$ROOT/vault_sync.py" \
  "$ROOT/eff_large_wordlist.txt" \
  "$ROOT/eff_large_wordlist.LICENSE.txt" \
  "$ROOT/packaging/local-password.svg" \
  "$PKG/usr/share/local-password/"
install -m 0644 "$ROOT/packaging/local-password.desktop" "$PKG/usr/share/applications/local-password.desktop"
install -m 0644 "$ROOT/packaging/local-password.svg" \
  "$PKG/usr/share/icons/hicolor/scalable/apps/local-password.svg"
install -m 0644 "$ROOT/eff_large_wordlist.LICENSE.txt" \
  "$PKG/usr/share/doc/local-password/eff_large_wordlist.LICENSE.txt"
install -m 0644 "$ROOT/PRIVACY.md" "$PKG/usr/share/doc/local-password/PRIVACY.md"
install -m 0644 "$ROOT/SECURITY.md" "$PKG/usr/share/doc/local-password/SECURITY.md"
install -m 0644 "$ROOT/USER_GUIDE.md" "$PKG/usr/share/doc/local-password/USER_GUIDE.md"
install -m 0644 "$ROOT/LICENSE" "$PKG/usr/share/doc/local-password/LICENSE"

cat > "$PKG/usr/share/doc/local-password/copyright" <<'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/

Files: *
Copyright: 2026 Ronnie Samuel
License: MIT
 See /usr/share/doc/local-password/LICENSE

Files: usr/share/local-password/eff_large_wordlist.txt
       usr/share/doc/local-password/eff_large_wordlist.LICENSE.txt
Copyright: Joseph Bonneau and the Electronic Frontier Foundation
License: CC-BY-3.0-US
 The EFF large wordlist is included unmodified under CC BY 3.0 US.
 https://creativecommons.org/licenses/by/3.0/us/
 The EFF does not endorse this project.
EOF

cat > "$PKG/DEBIAN/control" <<EOF
Package: local-password
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-3.0, python3-cryptography, xclip
Maintainer: Local Password <local-password@localhost>
Description: Air-gapped password generator
 Generate a password in a local window and copy it.
 Dark, beside the title, switches the colors on this computer.
 Save keeps a named password, locked with a passphrase, after the window closes.
 A recovery key is shown once. Either it or the passphrase opens saved passwords.
 If both are lost, the saved passwords cannot be recovered.
 Each generated password can be saved on its own.
 Send vault opens a port only while another device pulls the encrypted file.
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
