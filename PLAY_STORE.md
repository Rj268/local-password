# Google Play Store — Local Password

Prep for listing the Android app (`app.localpassword`) on Google Play.
Desktop version is **1.31.0**; Android `versionName` / `versionCode` match that cut (**1.31.0** / **13100**).

## Already done in the repo

- [x] Application id `app.localpassword`
- [x] Target API 35, min API 26
- [x] Adaptive launcher icon
- [x] `allowBackup="false"` (vault stays out of cloud backup)
- [x] Release signing wired through `android/keystore.properties` (local only)
- [x] Privacy policy in repo: [`PRIVACY.md`](PRIVACY.md)

## You do in Google Play Console

### 1. Create the developer account

1. Open [Google Play Console](https://play.google.com/console) and pay the one-time registration fee.
2. Create an app named **Local Password**, default language English (or your preference).
3. App type: **App** → free.

### 2. Create and keep the upload keystore

On a machine with JDK 17+ (your PC is fine):

```bash
cd android
bash scripts/create-release-keystore.sh
```

That writes (gitignored):

- `android/release.keystore`
- `android/keystore.properties`

**Back these up offline.** Losing them blocks updates for `app.localpassword`.

### 3. Build the Play App Bundle

```bash
cd android
./gradlew :vault:test :app:bundleRelease
```

Upload this file in Play Console:

`android/app/build/outputs/bundle/release/app-release.aab`

Without `keystore.properties`, the release bundle is **unsigned** and Play will reject it.

### 4. Store listing copy (draft)

**Short description** (≤80 characters):

```text
Local password manager. Vault stays on your phone. No account.
```

**Full description** (edit as you like):

```text
Local Password keeps saved passwords in an encrypted vault on this phone. There is no Local Password account and no analytics in the free core.

Generate strong passwords or passphrases, save them under a name, and unlock with a passphrase or recovery key. Send vault and Receive vault move the encrypted file to another device on the same Wi‑Fi — the passphrase is not sent.

Optional features such as LAN transfer use the network only when you start them. Opening and unlocking the vault does not contact a Local Password server.

See the privacy policy in the app listing for details. This project has not had a formal third-party security audit yet.
```

**Privacy policy URL** (required):

```text
https://github.com/Rj268/local-password/blob/main/PRIVACY.md
```

### 5. Graphics you must supply

Play will not accept the listing without these (create on your machine; do not invent fake screenshots in CI):

| Asset | Spec (approx.) |
| --- | --- |
| App icon | 512×512 PNG |
| Feature graphic | 1024×500 PNG |
| Phone screenshots | at least 2 (JPEG/PNG) |
| Tablet screenshots | optional but good |

Use real UI captures from a device or emulator: Generate, Saved (locked/unlocked), Dashboard.

### 6. Data safety form (suggested answers)

Match [`PRIVACY.md`](PRIVACY.md):

- **Does the app collect or share user data?** No for the free core’s analytics/ads. Declare network use carefully:
  - **Data collected:** none by Local Password servers (there are none).
  - **Data processed ephemerally / on device:** passwords and vault stay on device.
- **Security practices:** data is encrypted in transit for HTTPS system calls if any; vault is encrypted at rest on device.
- **Permissions in the manifest today:**
  - `INTERNET` — for optional network features you start (LAN vault transfer).
  - `ACCESS_WIFI_STATE` / `CHANGE_WIFI_MULTICAST_STATE` — LAN discovery for Send/Receive vault.

Be accurate if Android later gains the desktop-style HIBP breach check; then declare that optional hash-prefix contact with Have I Been Pwned.

### 7. Content rating & target audience

- Complete the IARC questionnaire (password manager → typically everyone / tools; answer truthfully).
- Target age: **18+** is a reasonable choice for a credential manager even if the app is not adult content.
- No ads, no in-app purchases in the free core (unless you add them later).

### 8. Release track

1. Testing → **Internal testing** first (your Gmail).
2. Then **Closed** or **Open** testing if you want wider feedback.
3. **Production** when install, unlock, save, and Send/Receive look solid on a physical phone.

### 9. After Play is live

- Attach a release-signed APK/AAB story to [GitHub Releases](https://github.com/Rj268/local-password/releases) if you want sideloaders too.
- Next store slice: **Zapstore** (same Android package, `zapstore.yaml` + `zsp`).

## Commands cheat sheet

```bash
# One-time keystore
cd android && bash scripts/create-release-keystore.sh

# Tests + Play bundle
./gradlew :vault:test :app:bundleRelease

# Debug APK (sideload / emulator — not for Play)
./gradlew :app:assembleDebug
```
