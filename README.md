# Random Password Generator

Generate a cryptographically secure password with Python's `secrets` module. You can answer a short series of prompts, or pass the length and character types as flags.

A strong password here has at least 8 characters, with a lowercase letter, an uppercase letter, a digit, and a special character. The generator also prints an entropy estimate: the size of the search space for that length and alphabet, in bits. When the length is long enough, it places at least one character from each selected group, then fills the rest at random. Each distinct character is equally likely.

## Run

Interactive:

```bash
python3 random_password_generator.py
```

The prompts ask for a length, then which of digits, letters, and special characters to include. You can leave out characters that are easy to mix up (`0`, `O`, `o`, `1`, `l`, `I`, `|`). You can copy the result to the clipboard or write it to a `.txt` file in the current directory. An unclear yes/no answer is asked again. An existing file is replaced only after you confirm.

Non-interactive:

```bash
python3 random_password_generator.py --length 16 --digits --letters --special
```

Pass `--length` on its own to use digits, letters, and special characters. The password is printed on its own line so you can pipe it. Strength and entropy notes go to standard error.

```bash
python3 random_password_generator.py --length 20 --quiet
python3 random_password_generator.py --length 20 --count 5 --no-ambiguous
python3 random_password_generator.py --length 20 --output vault
python3 random_password_generator.py --length 20 --output vault --force
python3 random_password_generator.py --length 20 --copy
```

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
| `-s`, `--special` | Include punctuation |
| `--no-ambiguous` | Leave out `0`/`O`, `1`/`l`/`I`, and the vertical bar |
| `-n`, `--count` | How many passwords to generate (1–100) |
| `-c`, `--copy` | Copy to the clipboard |
| `-o`, `--output` | Save to a `.txt` file in the current directory |
| `-f`, `--force` | Replace an existing output file |
| `-q`, `--quiet` | Print only the password |
