# Local Password

Generate a cryptographically secure password on this computer and copy it. The password stays in the window until you close it. Save keeps it under a name. A passphrase you choose locks it, and a recovery key shown once can open it too. Neither is stored. Saved passwords stay hidden until you unlock them. Send vault opens a port only while another device on the same Wi-Fi pulls the encrypted file. The passphrase is not sent.

A strong password here has about 75 bits of entropy or more. The strength bar fills toward 256 bits. That is the size of the search space for the length and alphabet you chose. An 8-character mix is about 50 bits, so it is reported as weak. Sixteen characters, or six random words, clears the strong line. Forty characters from digits, letters, and punctuation reach 256 bits, as do twenty words from the EFF list. When the length is long enough, the generator places at least one character from each selected group, then fills the rest at random. Each distinct character is equally likely.

## Install

The Debian package installs the local window:

```bash
sudo dpkg -i dist/local-password_1.31.0_all.deb
local-password
```

It depends on `python3`, `python3-gi`, `gir1.2-gtk-3.0`, `python3-cryptography`, and `xclip`. After install, "Local Password" is also in the application menu.

Rebuild the package with:

```bash
sh packaging/build-deb.sh
```

## Run from a checkout

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 python3-cryptography xclip
python3 password_app.py
```

The desktop app is version **1.31.8**, with **Create**, **Vault**, and **Settings** pages. The layout follows Android's flow while using two columns for the desktop generator. Light, Dark, and System themes are available in Settings.

- **Create:** choose Characters or Words, adjust length and options, and generate a masked password. Show and Copy work on the result. Save to Vault asks for a name. Batch generation lets you name and save individual results.
- **Vault:** search names, usernames, URLs, notes, and categories. Filter favorites, archived entries, or entries needing attention, and sort by Name, Recent, or Changed. View details expands an account's masked password, notes, dates, and actions. Show, Copy, Edit, Replace, and Manage are available there; the star marks a favorite.
- **Password health:** local estimates flag weak passwords, identical-password reuse, and entries unchanged for 180 days. Age alone does not mean a password is unsafe. Optional Check breaches uses Have I Been Pwned with a short hash prefix; it does not send your password or vault.
- **Settings:** choose appearance, clipboard clearing, auto-lock, confirmation before reveal, and lock on open. Change passphrase, encrypted backup/import, CSV import/export, and Send/Receive vault are also available. CSV exports contain plaintext and must be kept private.

The first save asks for a passphrase of at least 8 characters and shows a recovery key once. Write that key down. Either secret opens the encrypted vault; neither is stored as plaintext. If you lose both, the app cannot unlock the vault. A password that you generate but do not save is lost when the app closes.

Vault writes use an atomic replacement so an interrupted save preserves the previous complete file. Windows stores its vault in `%LOCALAPPDATA%\local-password\saved.vault`; Linux uses `~/.local/share/local-password/saved.vault`. The desktop update retains existing vault formats. Windows Hello and browser Autofill are not part of the desktop layout update. See [USER_GUIDE.md](USER_GUIDE.md) for everyday use.

## Command line

The same generator can print a password in a terminal. It still does not write a file.

```bash
python3 random_password_generator.py
python3 random_password_generator.py --length 16 --digits --letters --special
python3 random_password_generator.py --length 20 --quiet
python3 random_password_generator.py --passphrase
python3 random_password_generator.py --words 5
python3 random_password_generator.py --length 20 --count 5 --no-ambiguous
python3 random_password_generator.py --length 20 --all-special
python3 random_password_generator.py --length 20 --copy
```

With no options, the prompts ask whether you want a word passphrase, then a length and which of digits, letters, and special characters to include. The default symbols are safe to paste into a shell. `--all-special` mixes in quotes, backticks, and backslashes. You can leave out characters that are easy to mix up (`0`, `O`, `o`, `1`, `l`, `I`). The last prompt copies to the clipboard.

Pass `--length` on its own to use digits, letters, and special characters. The password is printed on its own line so you can pipe it. Strength and entropy notes go to standard error.

`--passphrase` prints six words from the [EFF large wordlist](https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt), separated by spaces. That list has 7,776 words, so six words are about 78 bits. Five words are about 65 bits and show up as weak. The wordlist is included unmodified. Joseph Bonneau and the Electronic Frontier Foundation created it, and it is used here under [CC BY 3.0 US](https://creativecommons.org/licenses/by/3.0/us/). The EFF does not endorse this project.

Clipboard copy uses `xclip`, or [pyperclip](https://pypi.org/project/pyperclip/) when that package is installed:

```bash
pip install -r requirements.txt
```

Generation itself needs only the Python standard library. The window needs GTK 3.

## Windows

The window is ready to build on Windows. Saved passwords go in `%LOCALAPPDATA%\local-password\saved.vault`. Copy uses the Windows clipboard. This Linux machine cannot build or run the `.exe`, because the Windows copies of GTK have to come from a Windows setup.

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

A macOS disk image is built on macOS.

## Android

The phone app reads and writes the same `saved.vault` file. Generate a password, name it, and save it. The first save asks for a passphrase and shows a recovery key once. Saved can sort by Name, Recent, or Changed; each entry shows Created and Changed dates; copying a saved password marks it Recent and shows Last used. Favorite stars or clears a row without opening Edit. Duplicate copies a row under a new name. Rename changes only the name without opening Edit. Category sets or clears the category without opening Edit. Username sets or clears the username without opening Edit. Archive hides a row from the main list. Remove can be undone with Undo. Settings holds dark mode, Change passphrase, Send vault, Receive vault, Import vault, Import CSV, Export CSV, and Export vault. Category dialogs offer the same default presets as the desktop app. URL and Notes can be set without opening Edit. Import vault reads a `saved.vault` copied from a computer. Import CSV adds password rows from another manager into the unlocked vault. Export CSV writes those rows as plaintext. Export vault writes that file so it can go back.

Send vault and Receive vault move that encrypted file between a computer and a phone on the same Wi-Fi. One device shows a 6-digit code. The other enters it. The passphrase stays where it already is. If the same name has two different passwords, both are kept and the new one is labeled `(other device)`. The port closes when the send finishes or you cancel it. A lost phone still needs a copy of `saved.vault`; the recovery key opens a file you still have.

Android version **1.31.7** uses version code **13109**, minimum SDK 26, compile SDK 37, and target SDK 36. Install the Android API 37 platform and use JDK 17 or newer compatible with the build tools.

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

## Privacy and security

- [`PRIVACY.md`](PRIVACY.md) — what stays on device, optional breach checks
- [`SECURITY.md`](SECURITY.md) — encryption and honest limits
- [`PUBLIC_RELEASE.md`](PUBLIC_RELEASE.md) — checklist for shipping publicly
- [`LICENSE`](LICENSE) — MIT

## Tests

```bash
python3 -m unittest discover -s tests -t .
```

## Options

| Flag | Meaning |
| --- | --- |
| `-l`, `--length` | Password length from 1 to 1024 |
| `-d`, `--digits` | Include `0-9` |
| `-a`, `--letters` | Include `a-z` and `A-Z` |
| `-s`, `--special` | Include shell-safe symbols such as `@%+=` |
| `--all-special` | Include every punctuation character, including quotes and backslashes |
| `--passphrase` | Generate six random words |
| `-w`, `--words` | Passphrase length in words (1–20) |
| `--no-ambiguous` | Leave out `0`/`O`, `1`/`l`/`I`, and the vertical bar |
| `--exclude` | Extra characters to leave out of the alphabet |
| `-n`, `--count` | How many passwords to generate (1–100) |
| `-c`, `--copy` | Copy to the clipboard |
| `-q`, `--quiet` | Print only the password |
