# Public release checklist

Use this when shipping Local Password beyond private use.

## Ready in the repo

- [x] Privacy policy (`PRIVACY.md`) and About copy that matches it
- [x] Security notes (`SECURITY.md`) covering vault crypto, breach checks, and limits
- [x] User guide (`USER_GUIDE.md`)
- [x] MIT license (`LICENSE`)
- [x] Debian package includes `vault_sync.py`, privacy, and security docs
- [x] Windows share text covers SmartScreen, vault path, and uninstall
- [x] Recovery / import overwrite warnings remain in the UI

## You still do outside the repo

### 1. Security review

Have an independent review of:

- Vault format (LPV1/LPV2, scrypt, AES-GCM)
- Send / Receive vault pairing
- Desktop and Android clients
- Optional HIBP breach-check path

Until that lands, say clearly that the project has not had a formal audit.

### 2. Code signing

- **Windows:** Sign `LocalPassword.exe` (and the installer/zip contents as needed) with a code-signing certificate so SmartScreen warnings ease over time.
- **macOS:** Notarize when you ship a Mac build.

Until signed, keep the “More info → Run anyway” note in `SHARE.txt`.

### 3. Build the shareable packages

On Windows, from an MSYS2 UCRT64 shell:

```bash
bash packaging/windows/build.sh
```

Share `dist/windows/LocalPassword-windows.zip`. Recipients unzip and double-click **Install Local Password**.

Published Windows installers are available on [GitHub Releases](https://github.com/Rj268/local-password/releases/latest).

On Debian/Ubuntu:

```bash
sh packaging/build-deb.sh
```

Share the versioned `.deb` file produced in `dist/`.

### 4. Android / Google Play

```bash
cd android
bash scripts/create-release-keystore.sh   # once; keep offline backup
./gradlew :vault:test :app:bundleRelease
```

Upload `app/build/outputs/bundle/release/app-release.aab` in Play Console.
Use this repo’s `PRIVACY.md` as the listing privacy policy URL.
Ship a sideload APK from GitHub Releases only if you want that channel too.

### 5. Public page copy

When you post a download link, include:

- Local-first: no account, no analytics
- Link or quote `PRIVACY.md`
- Link or quote `SECURITY.md` limits
- “Not yet independently audited” until a review exists
- Windows SmartScreen note until the build is signed
