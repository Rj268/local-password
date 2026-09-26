# Local Password

Generate a cryptographically secure password on this computer and copy it. The password stays in the window until you close it. Save keeps it under a name. A passphrase you choose locks it, and a recovery key shown once can open it too. Neither is stored. Saved passwords stay hidden until you unlock them. The app does not open a network port.

A strong password here has about 75 bits of entropy or more. The strength bar fills toward 256 bits. That is the size of the search space for the length and alphabet you chose. An 8-character mix is about 50 bits, so it is reported as weak. Sixteen characters, or six random words, clears the strong line. Forty characters from digits, letters, and punctuation reach 256 bits, as do twenty words from the EFF list. When the length is long enough, the generator places at least one character from each selected group, then fills the rest at random. Each distinct character is equally likely.

## Install

The Debian package installs the local window:

```bash
sudo dpkg -i dist/local-password_1.6.1_all.deb
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

The window has Create and Saved. Dark, beside the title, switches the colors and remembers that choice on this computer. Create has Characters and Words. Length, word count, and number of passwords are numeric. Digits, Letters, and Symbols show **On** or **Off**. Symbols include quotes, backticks, and backslashes. Generate fills the window. Copy places the password on the clipboard. Name it, then Save. Generate several and each one has its own name and Save, so you can keep one and leave the rest. The first save asks for a passphrase of at least 8 characters, then shows a recovery key once. Write that key down. Either the passphrase or the recovery key opens every saved password. Neither one is stored. Saving the only password opens Saved, where the name sits above it. Saving one of several stays on Create, so the others are still there. Find filters that list by name. The next time you open the window, Saved stays locked until you unlock it. The lock file is `~/.local/share/local-password/saved.vault`, readable only by your user. A password you do not save is gone when the window closes. Lock hides them again during this session. Remove drops one after you unlock. Saving the same name again replaces that password. If you lose both the passphrase and the recovery key, those saved passwords cannot be recovered. The window says so before you save.

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

3. From the project folder, run `bash packaging/windows/build.sh`. The script removes SVG theme icons and leaves a PNG fallback, so the window can open.
4. Run `dist/windows/LocalPassword/LocalPassword.exe` and try Generate, Copy, and Save. Dark, beside the title, switches the colors and remembers that choice in `%LOCALAPPDATA%\local-password\appearance`. That file holds no passwords.

Windows may warn that the program is unrecognized until it is signed with a code-signing certificate. Signing is a separate step after the exe runs.

A macOS disk image is built on macOS. An Android package is built with the Android SDK. Those are not on this machine.

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
