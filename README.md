# Random Password Generator

Generate a cryptographically secure password with Python's `secrets` module. You can answer a short series of prompts, or pass the length and character types as flags.

A strong password here is at least 8 characters and includes a lowercase letter, an uppercase letter, a digit, and a special character. When the length is long enough, the generator places at least one character from each selected group, then fills the rest at random. Each distinct character is equally likely.

## Run

Interactive:

```bash
python random_password_generator.py
```

The prompts ask for a length, then which of digits, letters, and special characters to include. You can copy the result to the clipboard or write it to a `.txt` file in the current directory.

Non-interactive:

```bash
python random_password_generator.py --length 16 --digits --letters --special
```

If you pass `--length` and no character-type flags, the generator uses digits, letters, and special characters. The password is printed on its own line so you can pipe it. Strength notes go to standard error.

```bash
python random_password_generator.py --length 20 --quiet
python random_password_generator.py --length 20 --output vault
python random_password_generator.py --length 20 --copy
```

`--output vault` writes `vault.txt` in the current directory. The file mode is readable and writable only by you, and the contents are the password in plaintext. Names are stripped of path characters, so the file stays in the current directory.

Clipboard copy uses [pyperclip](https://pypi.org/project/pyperclip/):

```bash
pip install -r requirements.txt
```

Generation itself needs only the Python standard library.

## Tests

```bash
python -m unittest discover -s tests -t .
```

## Options

| Flag | Meaning |
| --- | --- |
| `-l`, `--length` | Password length from 1 to 1024 |
| `-d`, `--digits` | Include `0-9` |
| `-a`, `--letters` | Include `a-z` and `A-Z` |
| `-s`, `--special` | Include punctuation |
| `-c`, `--copy` | Copy to the clipboard |
| `-o`, `--output` | Save to a `.txt` file in the current directory |
| `-q`, `--quiet` | Print only the password |
