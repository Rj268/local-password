# Local Password

Generate a cryptographically secure password on this computer and copy it. The password stays in the window until you close it. Save keeps it under a name. A passphrase you choose locks it, and a recovery key shown once can open it too. Neither is stored. Saved passwords stay hidden until you unlock them. Send vault opens a port only while another device on the same Wi-Fi pulls the encrypted file. The passphrase is not sent.

A strong password here has about 75 bits of entropy or more. The strength bar fills toward 256 bits. That is the size of the search space for the length and alphabet you chose. An 8-character mix is about 50 bits, so it is reported as weak. Sixteen characters, or six random words, clears the strong line. Forty characters from digits, letters, and punctuation reach 256 bits, as do twenty words from the EFF list. When the length is long enough, the generator places at least one character from each selected group, then fills the rest at random. Each distinct character is equally likely.

## Install

The Debian package installs the local window:

```bash
sudo dpkg -i dist/local-password_1.6.2_all.deb
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

The window has Dashboard, Generate, Saved, and Settings. The header shows the vault lock status. Dark, on the Settings page, switches the colors and remembers that choice on this computer. Clear clipboard drops a copied password after a short delay. Auto-lock hides saved passwords when the window sits idle. Change passphrase seals the vault under a new passphrase and shows a new recovery key once; the old passphrase and recovery key stop working. Export vault and Import vault copy the encrypted file to or from a path you choose. Import CSV adds password rows from another manager into the unlocked vault. Export CSV writes those rows as a plaintext file you can move elsewhere — keep it private and delete it when you are done. Send vault and Receive vault are on that page too. Generate has Characters and Words. Length, word count, and number of passwords are numeric. Uppercase, Lowercase, Digits, and Symbols show **On** or **Off**. Exclude ambiguous drops characters that are easy to mix up. Words mode can change the separator and capitalize each word. Strength uses Very weak through Very strong from an entropy estimate. Generate fills the window. Each result can be shown, hidden, copied, regenerated, or saved. Copy places the password on the clipboard. Name it, then Save. Generate several and each one has its own name and Save, so you can keep one and leave the rest. The first save asks for a passphrase of at least 8 characters, then shows a recovery key once. Write that key down. Either the passphrase or the recovery key opens every saved password. Neither one is stored. Saving the only password opens Saved, where the name sits above it. Saving one of several stays on Generate, so the others are still there. Search filters that list by name, username, URL, notes, or category. Favorites, Needs attention, and categories narrow the list. Edit adds username, URL, notes, category, and a favorite flag without breaking older vault files. Copy username and Open URL appear when those fields are set. A weak or reused password is called out on the entry, on the Saved heading, and on the Dashboard. Needs attention keeps only those rows. Replace password generates a strong password, saves it on that entry, and copies it. Unknown fields stay in the vault when you save again. Saved passwords stay masked until you show one. Remove asks for confirmation. The next time you open the window, Saved stays locked until you unlock it. The lock file is `~/.local/share/local-password/saved.vault`, readable only by your user. A password you do not save is gone when the window closes. Lock hides them again during this session. Remove drops one after you unlock. Saving the same name again replaces that password. If you lose both the passphrase and the recovery key, those saved passwords cannot be recovered. The window says so before you save.

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
  mingw-w64-ucrt-x86_64-pyinstaller \
  mingw-w64-ucrt-x86_64-librsvg
```

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

The phone app reads and writes the same `saved.vault` file. Generate a password, name it, and save it. The first save asks for a passphrase and shows a recovery key once. Settings holds dark mode, Change passphrase, Send vault, Receive vault, Import vault, Import CSV, Export CSV, and Export vault. Import vault reads a `saved.vault` copied from a computer. Import CSV adds password rows from another manager into the unlocked vault. Export CSV writes those rows as plaintext. Export vault writes that file so it can go back.

Send vault and Receive vault move that encrypted file between a computer and a phone on the same Wi-Fi. One device shows a 6-digit code. The other enters it. The passphrase stays where it already is. If the same name has two different passwords, both are kept and the new one is labeled `(other device)`. The port closes when the send finishes or you cancel it. A lost phone still needs a copy of `saved.vault`; the recovery key opens a file you still have.

Build it from `android/` with the Android SDK installed:

```bash
cd android
export ANDROID_HOME=/path/to/android-sdk
./gradlew :vault:test :app:assembleDebug
```

The installable package is `dist/local-password.apk`. Copy it to the phone, open it, and allow installation from that source. The vault on the phone stays in the app's private storage until you export it.

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
| `-n`, `--count` | How many passwords to generate (1–100) |
| `-c`, `--copy` | Copy to the clipboard |
| `-q`, `--quiet` | Print only the password |
