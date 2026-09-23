#!/usr/bin/env python3
"""Generate cryptographically secure random passwords and passphrases.

Interactive prompts match a simple question-and-answer flow. Pass ``--length``
to generate a character password, or ``--passphrase`` for random words.
Character selection is uniform: each distinct character is equally likely, and
a long enough password includes at least one character from every selected group.

The password is printed and can be copied. It is never written to a file.
"""

from __future__ import annotations

import argparse
import math
import secrets
import shutil
import string
import subprocess
import sys
from pathlib import Path

MIN_PASSWORD_LENGTH = 1
MAX_PASSWORD_LENGTH = 1024
MAX_PASSWORD_COUNT = 100
MIN_WORD_COUNT = 1
MAX_WORD_COUNT = 20
DEFAULT_WORD_COUNT = 6
# An 8-character mix is about 50 bits. Six words from the EFF list are about 78.
STRONG_ENTROPY_BITS = 75
# Characters that are easy to misread in many fonts: 0/O, 1/l/I, and a bar.
AMBIGUOUS_CHARACTERS = "0Ool1I|"
# Metacharacters that change meaning when pasted into a shell unquoted.
SHELL_SENSITIVE_CHARACTERS = "!\"#$&'()*;<>?\\`|[]~{}"
WORDLIST_PATH = Path(__file__).with_name("eff_large_wordlist.txt")
_WORDLIST: tuple[str, ...] | None = None


def without_ambiguous(character_list: str) -> str:
    """Drop characters that are easy to confuse when a password is read or typed."""
    skip = set(AMBIGUOUS_CHARACTERS)
    return "".join(char for char in character_list if char not in skip)


def prepare_character_list(character_list: str, *, exclude_ambiguous: bool = False) -> str:
    """Return the distinct characters that will actually be used."""
    pool = unique_characters(character_list)
    if exclude_ambiguous:
        pool = without_ambiguous(pool)
    if pool:
        return pool
    if exclude_ambiguous and unique_characters(character_list):
        raise ValueError("Excluding ambiguous characters left no characters to use.")
    raise ValueError("Choose at least one character type.")


def password_entropy_bits(length: int, pool_size: int) -> float:
    """Estimate the search space as length * log2(pool size).

    The attacker is assumed to know the length and the alphabet. Guaranteeing
    one character from each group trims this number slightly.
    """
    if length <= 0 or pool_size <= 1:
        return 0.0
    return length * math.log2(pool_size)


def special_characters(*, all_special: bool = False) -> str:
    """Return punctuation. The default set is safe to paste into a shell unquoted."""
    if all_special:
        return string.punctuation
    skip = set(SHELL_SENSITIVE_CHARACTERS)
    return "".join(char for char in string.punctuation if char not in skip)


def default_character_list() -> str:
    return string.digits + string.ascii_letters + special_characters()


def load_wordlist() -> tuple[str, ...]:
    """Load the EFF large passphrase wordlist. The file itself is unmodified."""
    global _WORDLIST
    if _WORDLIST is not None:
        return _WORDLIST
    try:
        text = WORDLIST_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Could not read the passphrase word list: {exc}") from exc
    words = [line.split()[-1] for line in text.splitlines() if line.split()]
    if len(words) < 1000:
        raise ValueError("The passphrase word list is missing or too small.")
    _WORDLIST = tuple(words)
    return _WORDLIST


def passphrase_entropy_bits(word_count: int, wordlist_size: int) -> float:
    """Entropy of a passphrase drawn with replacement from a word list."""
    if word_count <= 0 or wordlist_size <= 1:
        return 0.0
    return word_count * math.log2(wordlist_size)


def require_word_count(word_count: int) -> int:
    if isinstance(word_count, bool) or not isinstance(word_count, int):
        raise ValueError("Word count must be an integer.")
    if word_count < MIN_WORD_COUNT or word_count > MAX_WORD_COUNT:
        raise ValueError(f"Word count must be between {MIN_WORD_COUNT} and {MAX_WORD_COUNT}.")
    return word_count


def generate_passphrase(word_count: int, *, wordlist: tuple[str, ...] | None = None) -> str:
    """Build a passphrase of ``word_count`` words separated by spaces."""
    word_count = require_word_count(word_count)
    words = load_wordlist() if wordlist is None else wordlist
    if not words:
        raise ValueError("The passphrase word list is empty.")
    return " ".join(secrets.choice(words) for _ in range(word_count))


def unique_characters(character_list: str) -> str:
    """Return each distinct character once, in first-seen order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for char in character_list:
        if char not in seen:
            seen.add(char)
            ordered.append(char)
    return "".join(ordered)


def character_groups(character_list: str) -> list[str]:
    """Split a character pool into digit, letter case, punctuation, and other groups."""
    pool = set(unique_characters(character_list))
    groups = [
        "".join(char for char in string.digits if char in pool),
        "".join(char for char in string.ascii_lowercase if char in pool),
        "".join(char for char in string.ascii_uppercase if char in pool),
        "".join(char for char in string.punctuation if char in pool),
    ]
    known = set("".join(groups))
    extra = "".join(char for char in unique_characters(character_list) if char not in known)
    if extra:
        groups.append(extra)
    return [group for group in groups if group]


def _secure_shuffle(items: list[str]) -> None:
    for index in range(len(items) - 1, 0, -1):
        swap_with = secrets.randbelow(index + 1)
        items[index], items[swap_with] = items[swap_with], items[index]


def require_password_length(length: int) -> int:
    if isinstance(length, bool) or not isinstance(length, int):
        raise ValueError("Password length must be an integer.")
    if length < MIN_PASSWORD_LENGTH or length > MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"Password length must be between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH}."
        )
    return length


def generate_password(length: int, character_list: str) -> str:
    """Build a password of ``length`` from ``character_list`` using ``secrets``."""
    length = require_password_length(length)
    pool = unique_characters(character_list)
    if not pool:
        raise ValueError("Choose at least one character type.")

    groups = character_groups(pool)
    characters: list[str] = []
    if length >= len(groups):
        characters.extend(secrets.choice(group) for group in groups)
    characters.extend(secrets.choice(pool) for _ in range(length - len(characters)))
    _secure_shuffle(characters)
    return "".join(characters)


def estimated_pool_size(password: str) -> int:
    """Guess the alphabet size from the character classes present in a password."""
    size = 0
    if any(char.islower() for char in password):
        size += len(string.ascii_lowercase)
    if any(char.isupper() for char in password):
        size += len(string.ascii_uppercase)
    if any(char.isdigit() for char in password):
        size += len(string.digits)
    if any(char in string.punctuation for char in password):
        size += len(string.punctuation)
    extras = {
        char
        for char in password
        if not (char.islower() or char.isupper() or char.isdigit() or char in string.punctuation)
    }
    return size + len(extras)


def password_strength_bits(
    password: str,
    pool_size: int | None = None,
    entropy_bits: float | None = None,
) -> float:
    if entropy_bits is not None:
        return entropy_bits
    size = estimated_pool_size(password) if pool_size is None else pool_size
    return password_entropy_bits(len(password), size)


def is_strong_password(
    password: str,
    pool_size: int | None = None,
    *,
    entropy_bits: float | None = None,
) -> bool:
    """A strong password has about 75 bits of entropy or more."""
    return password_strength_bits(password, pool_size, entropy_bits) >= STRONG_ENTROPY_BITS


def strength_label(
    password: str,
    pool_size: int | None = None,
    *,
    entropy_bits: float | None = None,
) -> str:
    if is_strong_password(password, pool_size, entropy_bits=entropy_bits):
        return "Strong Password"
    return "Weak Password"


def describe_passwords(
    passwords: list[str],
    pool_size: int | None = None,
    *,
    entropy_bits: float | None = None,
) -> str:
    """Summarize strength and the approximate size of the search space."""
    exact_bits = password_strength_bits(passwords[0], pool_size, entropy_bits)
    bits = round(exact_bits)
    kind = "strong" if exact_bits >= STRONG_ENTROPY_BITS else "weak"
    if len(passwords) == 1:
        title = "Strong Password" if kind == "strong" else "Weak Password"
        return f"{title}; about {bits} bits"
    noun = "password" if len(passwords) == 1 else "passwords"
    return f"About {bits} bits of entropy each.\n{len(passwords)} {kind} {noun}."


def can_be_strong(length: int, character_list: str) -> bool:
    pool = unique_characters(character_list)
    return password_entropy_bits(length, len(pool)) >= STRONG_ENTROPY_BITS


def strong_line_message() -> str:
    return (
        f"These options stay under {STRONG_ENTROPY_BITS} bits. "
        "Add length or more character types to reach a strong password."
    )


def _copy_with_pyperclip(password: str) -> bool:
    try:
        import pyperclip
    except ImportError:
        return False
    try:
        pyperclip.copy(password)
    except pyperclip.PyperclipException as exc:
        print(f"Error copying password to clipboard: {exc}", file=sys.stderr)
        return False
    return True


def _copy_with_xclip(password: str) -> bool:
    """Hand the password to xclip on standard input so it stays in memory."""
    if shutil.which("xclip") is None:
        return False
    try:
        subprocess.run(
            ["xclip", "-selection", "clipboard", "-in"],
            input=password.encode("utf-8"),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def copy_to_clipboard(password: str) -> bool:
    """Place the password on the clipboard. Nothing is written to disk."""
    if _copy_with_pyperclip(password) or _copy_with_xclip(password):
        print("Password copied.", file=sys.stderr)
        return True
    print(
        "Clipboard support needs the pyperclip package or the xclip program.",
        file=sys.stderr,
    )
    return False


def _read_line(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        print()
        raise SystemExit(1) from None


def ask_yes_no(prompt: str) -> bool:
    while True:
        answer = _read_line(prompt).strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer yes or no.")


def get_valid_integer_input(
    prompt: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    while True:
        raw_value = _read_line(prompt)
        try:
            value = int(raw_value.strip())
        except ValueError:
            print("Please enter a valid integer.")
            continue
        if minimum is not None and value < minimum:
            print(f"Please enter a number of at least {minimum}.")
            continue
        if maximum is not None and value > maximum:
            print(f"Please enter a number no greater than {maximum}.")
            continue
        return value


def choose_character_types() -> str | None:
    print("Choose the character types to include in your password:")
    print("1. Digits (0-9)")
    print("2. Letters (both uppercase and lowercase)")
    print("3. Special characters (shell-safe, such as @%+=)")
    print("4. Finish")

    selected: set[int] = set()
    labels = {
        1: "digits",
        2: "letters",
        3: "special characters",
    }
    while True:
        choice = get_valid_integer_input("Pick a number (1-4): ")
        if choice in labels:
            if choice in selected:
                print(f"{labels[choice].capitalize()} are already included.")
                continue
            selected.add(choice)
            print(f"Added {labels[choice]}.")
        elif choice == 4:
            if not selected:
                print("You have chosen to exit.")
                return None
            return _pool_from_choices(selected)
        else:
            print("Invalid option. Please pick a number between 1 and 4.")


def _pool_from_choices(selected: set[int]) -> str:
    parts: list[str] = []
    if 1 in selected:
        parts.append(string.digits)
    if 2 in selected:
        parts.append(string.ascii_letters)
    if 3 in selected:
        parts.append(special_characters())
    return "".join(parts)


def _warn_if_cannot_be_strong(length: int, character_list: str) -> None:
    if can_be_strong(length, character_list):
        return
    print(strong_line_message())


def offer_copy(password: str) -> None:
    """Copy is the only way out. Declining leaves the password on screen only."""
    if not ask_yes_no("Copy the password to the clipboard? (yes/no): "):
        print("Password was not copied.")
        return
    copy_to_clipboard(password)


def run_interactive_passphrase() -> None:
    word_count = get_valid_integer_input(
        f"How many words ({MIN_WORD_COUNT}-{MAX_WORD_COUNT}, 6 is a readable default): ",
        minimum=MIN_WORD_COUNT,
        maximum=MAX_WORD_COUNT,
    )
    try:
        wordlist = load_wordlist()
        passphrase = generate_passphrase(word_count, wordlist=wordlist)
    except ValueError as exc:
        print(f"Error: {exc}")
        return
    print("Generated Passphrase:", passphrase)
    offer_copy(passphrase)
    bits = passphrase_entropy_bits(word_count, len(wordlist))
    print(describe_passwords([passphrase], entropy_bits=bits))


def run_interactive() -> None:
    print("Welcome to the Password Generator")
    print("Follow the prompts to create a secure password.")
    print("The password is shown here and can be copied. It is not written to a file.")
    print(
        f"A strong password has about {STRONG_ENTROPY_BITS} bits of entropy or more. "
        "Sixteen random characters, or six random words, reaches that."
    )
    if ask_yes_no("Generate a word passphrase? (yes/no): "):
        run_interactive_passphrase()
        return

    length = get_valid_integer_input(
        "Enter password length (e.g., 16): ",
        minimum=MIN_PASSWORD_LENGTH,
        maximum=MAX_PASSWORD_LENGTH,
    )
    character_list = choose_character_types()
    if character_list is None:
        return

    exclude_ambiguous = False
    if any(char in AMBIGUOUS_CHARACTERS for char in character_list):
        exclude_ambiguous = ask_yes_no(
            "Exclude ambiguous characters (0, O, o, 1, l, I, |)? (yes/no): "
        )
    try:
        character_list = prepare_character_list(
            character_list,
            exclude_ambiguous=exclude_ambiguous,
        )
    except ValueError as exc:
        print(f"Error: {exc}")
        return

    _warn_if_cannot_be_strong(length, character_list)
    password = generate_password(length, character_list)
    print("Generated Password:", password)
    offer_copy(password)
    print(describe_passwords([password], len(character_list)))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a cryptographically secure random password.",
        epilog=(
            "With no options, the generator asks questions interactively. "
            "The password is printed and can be copied. It is not written to a file."
        ),
    )
    parser.add_argument(
        "-l",
        "--length",
        type=int,
        help=f"Password length ({MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH})",
    )
    parser.add_argument("-d", "--digits", action="store_true", help="Include digits 0-9")
    parser.add_argument(
        "-a",
        "--letters",
        action="store_true",
        help="Include uppercase and lowercase letters",
    )
    parser.add_argument(
        "-s",
        "--special",
        action="store_true",
        help="Include shell-safe special characters such as @%+=",
    )
    parser.add_argument(
        "--all-special",
        action="store_true",
        help="Include every punctuation character, including quotes, backticks, and backslashes",
    )
    parser.add_argument(
        "--passphrase",
        action="store_true",
        help=f"Generate {DEFAULT_WORD_COUNT} random words instead of a character password",
    )
    parser.add_argument(
        "-w",
        "--words",
        type=int,
        default=None,
        help=f"Passphrase length in words ({MIN_WORD_COUNT}-{MAX_WORD_COUNT})",
    )
    parser.add_argument(
        "--no-ambiguous",
        action="store_true",
        help=f"Leave out easily confused characters ({AMBIGUOUS_CHARACTERS})",
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=None,
        help=f"How many passwords to generate (1-{MAX_PASSWORD_COUNT})",
    )
    parser.add_argument(
        "-c",
        "--copy",
        action="store_true",
        help="Copy the password to the clipboard",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Print only the password",
    )
    return parser


def _noninteractive_pool(args: argparse.Namespace) -> str:
    class_chosen = args.digits or args.letters or args.special
    if not class_chosen:
        return string.digits + string.ascii_letters + special_characters(all_special=args.all_special)
    parts: list[str] = []
    if args.digits:
        parts.append(string.digits)
    if args.letters:
        parts.append(string.ascii_letters)
    if args.special or args.all_special:
        parts.append(special_characters(all_special=args.all_special))
    return "".join(parts)


def _passphrase_requested(args: argparse.Namespace) -> bool:
    return args.passphrase or args.words is not None


def _reject_mixed_passphrase_options(args: argparse.Namespace) -> None:
    character_options = any(
        (args.length is not None, args.digits, args.letters, args.special, args.all_special, args.no_ambiguous)
    )
    if _passphrase_requested(args) and character_options:
        print(
            "Error: a passphrase is made of words. "
            "Leave off --length and the character-type options.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _password_count(args: argparse.Namespace) -> int:
    count = 1 if args.count is None else args.count
    if isinstance(count, bool) or not isinstance(count, int):
        raise ValueError("Password count must be an integer.")
    if count < 1 or count > MAX_PASSWORD_COUNT:
        raise ValueError(f"Password count must be between 1 and {MAX_PASSWORD_COUNT}.")
    return count


def _passwords_as_text(passwords: list[str]) -> str:
    if len(passwords) == 1:
        return passwords[0]
    return "\n".join(passwords)


def _generate_values(args: argparse.Namespace) -> tuple[list[str], str]:
    """Return the generated secrets and the strength report for them."""
    count = _password_count(args)
    if _passphrase_requested(args):
        word_count = DEFAULT_WORD_COUNT if args.words is None else require_word_count(args.words)
        wordlist = load_wordlist()
        values = [generate_passphrase(word_count, wordlist=wordlist) for _ in range(count)]
        bits = passphrase_entropy_bits(word_count, len(wordlist))
        return values, describe_passwords(values, entropy_bits=bits)

    require_password_length(args.length)
    character_list = prepare_character_list(
        _noninteractive_pool(args),
        exclude_ambiguous=args.no_ambiguous,
    )
    values = [generate_password(args.length, character_list) for _ in range(count)]
    return values, describe_passwords(values, len(character_list))


def run_noninteractive(args: argparse.Namespace) -> None:
    _reject_mixed_passphrase_options(args)
    if args.length is None and not _passphrase_requested(args):
        print("Error: --length is required when other options are set.", file=sys.stderr)
        raise SystemExit(2)

    explicit_types = args.digits or args.letters or args.special
    try:
        values, report = _generate_values(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    print(_passwords_as_text(values))
    sys.stdout.flush()
    if not args.quiet:
        if not _passphrase_requested(args) and not explicit_types:
            print(
                "Password uses digits, letters, and special characters.",
                file=sys.stderr,
            )
        if args.all_special:
            print(
                "Special characters include quotes, backticks, and backslashes.",
                file=sys.stderr,
            )
        if args.no_ambiguous:
            print(
                f"Ambiguous characters left out: {AMBIGUOUS_CHARACTERS}.",
                file=sys.stderr,
            )
        if not _passphrase_requested(args) and not can_be_strong(args.length, prepare_character_list(
            _noninteractive_pool(args),
            exclude_ambiguous=args.no_ambiguous,
        )):
            print(strong_line_message(), file=sys.stderr)
        print(report, file=sys.stderr)

    if args.copy and not copy_to_clipboard(_passwords_as_text(values)):
        raise SystemExit(1)


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    interactive = not any(
        (
            args.length is not None,
            args.digits,
            args.letters,
            args.special,
            args.all_special,
            args.passphrase,
            args.words is not None,
            args.no_ambiguous,
            args.count is not None,
            args.copy,
            args.quiet,
        )
    )
    if interactive:
        run_interactive()
        return
    run_noninteractive(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        raise SystemExit(130) from None
