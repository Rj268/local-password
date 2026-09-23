# Random Password Generator

Generate a cryptographically secure password with Python's `secrets` module. You can answer a short series of prompts, or pass the length and character types as flags.

A strong password here has about 75 bits of entropy or more. That is the size of the search space for the length and alphabet you chose. An 8-character mix is about 50 bits, so it is reported as weak. Sixteen characters, or six random words, clears the line. When the length is long enough, the generator places at least one character from each selected group, then fills the rest at random. Each distinct character is equally likely.

## Run

In a browser:

```bash
python3 password_gui.py
```

Then open [http://127.0.0.1:8741](http://127.0.0.1:8741). The page uses the same generator as the command-line tool: character passwords, symbols, and six-word passphrases. Copy and download stay in the browser. The server listens on this computer only.

Interactive:

```bash
python3 random_password_generator.py
```

The prompts ask whether you want a word passphrase, then a length and which of digits, letters, and special characters to include. The default symbols are safe to paste into a shell: quotes, backticks, backslashes, and other shell metacharacters stay out unless you pass `--all-special`. You can also leave out characters that are easy to mix up (`0`, `O`, `o`, `1`, `l`, `I`). You can copy the result to the clipboard or write it to a `.txt` file in the current directory. An unclear yes/no answer is asked again. An existing file is replaced only after you confirm.

Non-interactive:

```bash
python3 random_password_generator.py --length 16 --digits --letters --special
```

Pass `--length` on its own to use digits, letters, and special characters. The password is printed on its own line so you can pipe it. Strength and entropy notes go to standard error.

```bash
python3 random_password_generator.py --length 20 --quiet
python3 random_password_generator.py --passphrase
python3 random_password_generator.py --words 5
python3 random_password_generator.py --length 20 --count 5 --no-ambiguous
python3 random_password_generator.py --length 20 --all-special
python3 random_password_generator.py --length 20 --output vault
python3 random_password_generator.py --length 20 --output vault --force
python3 random_password_generator.py --length 20 --copy
```

`--passphrase` prints six words from the [EFF large wordlist](https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt), separated by spaces. That list has 7,776 words, so six words are about 78 bits. Five words are about 65 bits and show up as weak. The wordlist is included unmodified. Joseph Bonneau and the Electronic Frontier Foundation created it, and it is used here under [CC BY 3.0 US](https://creativecommons.org/licenses/by/3.0/us/). The EFF does not endorse this project.

`--output vault` writes `vault.txt` in the current directory. The file mode is readable and writable only by you, and the contents are the password in plaintext. A second run leaves that file in place until you pass `--force`. Several passwords are stored one per line. Names are stripped of path characters, so the file stays in the current directory, and a symbolic link is refused.

Clipboard copy uses [pyperclip](https://pypi.org/project/pyperclip/):

```bash
pip install -r requirements.txt
```

Generation itself needs only the Python standard library.

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
| `-o`, `--output` | Save to a `.txt` file in the current directory |
| `-f`, `--force` | Replace an existing output file |
| `-q`, `--quiet` | Print only the password |
