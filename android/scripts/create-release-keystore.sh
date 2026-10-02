#!/usr/bin/env bash
# Create a Play Store upload keystore (run once; keep the output forever).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEYSTORE="$ROOT/release.keystore"
PROPS="$ROOT/keystore.properties"
ALIAS="${KEY_ALIAS:-localpassword}"

if [[ -f "$KEYSTORE" ]]; then
  echo "Already exists: $KEYSTORE" >&2
  echo "Refusing to overwrite. Move it aside if you really intend a new key." >&2
  exit 1
fi

if ! command -v keytool >/dev/null 2>&1; then
  echo "keytool not found. Install a JDK 17+, then retry." >&2
  exit 1
fi

echo "Generating $KEYSTORE (alias=$ALIAS, RSA 2048, 10000 days)..."
keytool -genkeypair -v \
  -keystore "$KEYSTORE" \
  -alias "$ALIAS" \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000 \
  -dname "CN=Local Password, OU=Local Password, O=Local Password, L=Unknown, ST=Unknown, C=US"

echo
echo "Enter the same store/key passwords you just chose for keystore.properties."
read -r -s -p "storePassword: " STORE_PASS
echo
read -r -s -p "keyPassword (same is fine): " KEY_PASS
echo

umask 077
cat > "$PROPS" <<EOF
storeFile=release.keystore
storePassword=$STORE_PASS
keyAlias=$ALIAS
keyPassword=$KEY_PASS
EOF

echo
echo "Wrote $PROPS"
echo "Build a Play upload with:"
echo "  cd android && ./gradlew :app:bundleRelease"
echo "Output: app/build/outputs/bundle/release/app-release.aab"
echo
echo "Back up release.keystore + keystore.properties offline. Do not commit them."
