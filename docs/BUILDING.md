# Building and testing

Run commands from the repository root unless stated otherwise.

## Linux

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-cryptography xclip
python3 password_app.py
python3 -m unittest discover -s tests -t .
sh packaging/build-deb.sh
```

GUI tests require a display or Xvfb. The package workflow validates Ubuntu 22.04 and 24.04. Native Wayland clipboard behavior needs separate testing.

## Windows

The window is ready to build on Windows. Saved passwords go in `%LOCALAPPDATA%\local-password\saved.vault`. Copy uses the Windows clipboard. Build on Windows using MSYS2 UCRT64. The packaged application bundles Python and GTK; users do not need to install Python separately.

On a Windows computer:

1. Install [MSYS2](https://www.msys2.org/) and open the **UCRT64** shell.
2. Install the libraries and the packager:

```bash
pacman -S --needed \
  mingw-w64-ucrt-x86_64-gtk3 \
  mingw-w64-ucrt-x86_64-python \
  mingw-w64-ucrt-x86_64-python-gobject \
  mingw-w64-ucrt-x86_64-python-cryptography \
  mingw-w64-ucrt-x86_64-python-pillow \
  mingw-w64-ucrt-x86_64-pyinstaller \
  mingw-w64-ucrt-x86_64-librsvg
```

Pillow is optional for a normal build when `packaging/windows/local-password.ico` is already in the repo. Install it only if you need to regenerate icons with `python packaging/windows/make_icon.py`.

3. From the project folder, run `bash packaging/windows/build.sh`. The script removes SVG theme icons and leaves a PNG fallback, so the window can open. It also stamps the green key onto `LocalPassword.exe` and writes `dist/windows/LocalPassword-windows.zip`.
4. Install it into the Start menu and onto the desktop:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File dist/windows/install.ps1 -Source dist/windows/LocalPassword
```

Open **Local Password** from the Start menu. Dark, on the Settings page, switches the colors and remembers that choice in `%LOCALAPPDATA%\local-password\appearance`. Clipboard clear and auto-lock preferences stay in `%LOCALAPPDATA%\local-password\preferences`. Change passphrase, Export vault, Import vault, Import CSV, Export CSV, Send vault, and Receive vault are on that page too. Those files hold no passwords. Remove the app from Settings, Apps.

The zip is what other people download. Send `dist/windows/LocalPassword-windows.zip`. They unzip it and double-click **Install Local Password**. The program then appears in the Start menu and on the desktop. The libraries stay in the installed folder.

Windows may warn that the program is unrecognized until it is signed with a code-signing certificate. Signing is a separate step after the exe runs. Recipients choose **More info**, then **Run anyway**.


## macOS

See the [Mac build guide](../packaging/macos/README.md).

## Android

Android version **1.31.10** uses version code **13111**, minimum SDK 26, compile SDK 37, and target SDK 36. Install the Android API 37 platform and use JDK 17 or newer compatible with the build tools.

Android includes biometric unlock with passphrase fallback and an Autofill service. Enable Local Password as the Autofill provider in Android settings, save an entry with the matching website URL, then focus a sign-in field. Check the destination shown before selecting a login. These features work with the local encrypted vault.

Build it from `android/` with the Android SDK installed:

```bash
cd android
export ANDROID_HOME=/path/to/android-sdk
./gradlew :vault:test :app:assembleDebug
```

For Google Play, create an upload keystore with `bash scripts/create-release-keystore.sh` in `android/` (keep `release.keystore` and `keystore.properties` offline — never commit them), then build the App Bundle with `./gradlew :app:bundleRelease`. Upload `app/build/outputs/bundle/release/app-release.aab` in Play Console. Privacy policy URL: this repo’s `PRIVACY.md`.

For sideloading a debug build during development:

```bash
cd android
./gradlew :app:assembleDebug
```

Copy the APK from `app/build/outputs/apk/debug/` to the phone and allow installation from that source. The vault on the phone stays in the app's private storage until you export it.
