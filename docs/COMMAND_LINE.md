# Command-line generator

Run commands from the repository root.

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
