#!/usr/bin/env python3
"""Generate cryptographically secure random passwords.

Interactive prompts match a simple question-and-answer flow. Pass ``--length``
to generate a password without prompts. Character selection is uniform: each
distinct character is equally likely, and a long enough password includes at
least one character from every selected group.
"""

from __future__ import annotations

import argparse
import math
import os
import secrets
import string
import sys
from pathlib import Path

MIN_PASSWORD_LENGTH = 1
MAX_PASSWORD_LENGTH = 1024
MAX_PASSWORD_COUNT = 100
STRONG_PASSWORD_LENGTH = 8
# Characters that are easy to misread in many fonts: 0/O, 1/l/I, and a bar.
AMBIGUOUS_CHARACTERS = "0Ool1I|"


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


def is_strong_password(password: str) -> bool:
    """A strong password is at least 8 characters and mixes both letter cases, a digit, and punctuation."""
    return (
        len(password) >= STRONG_PASSWORD_LENGTH
        and any(char.islower() for char in password)
        and any(char.isupper() for char in password)
        and any(char.isdigit() for char in password)
        and any(char in string.punctuation for char in password)
    )


def strength_label(password: str) -> str:
    if is_strong_password(password):
        return "Strong Password"
    missing: list[str] = []
    if len(password) < STRONG_PASSWORD_LENGTH:
        missing.append(f"at least {STRONG_PASSWORD_LENGTH} characters")
    if not any(char.islower() for char in password):
        missing.append("a lowercase letter")
    if not any(char.isupper() for char in password):
        missing.append("an uppercase letter")
    if not any(char.isdigit() for char in password):
        missing.append("a digit")
    if not any(char in string.punctuation for char in password):
        missing.append("a special character")
    return "Weak Password (missing " + ", ".join(missing) + ")"


def describe_passwords(passwords: list[str], pool_size: int) -> str:
    """Summarize strength and the approximate size of the search space."""
    bits = round(password_entropy_bits(len(passwords[0]), pool_size))
    if len(passwords) == 1:
        return f"{strength_label(passwords[0])}; about {bits} bits"
    strong = sum(1 for password in passwords if is_strong_password(password))
    weak = len(passwords) - strong
    lines = [f"About {bits} bits of entropy each."]
    if weak == 0:
        noun = "password" if strong == 1 else "passwords"
        lines.append(f"{strong} strong {noun}.")
    elif strong == 0:
        noun = "password" if weak == 1 else "passwords"
        lines.append(f"{weak} weak {noun}.")
    else:
        strong_noun = "password" if strong == 1 else "passwords"
        weak_noun = "password" if weak == 1 else "passwords"
        lines.append(f"{strong} strong {strong_noun}, {weak} weak {weak_noun}.")
    return "\n".join(lines)


def can_be_strong(length: int, character_list: str) -> bool:
    pool = unique_characters(character_list)
    return (
        length >= STRONG_PASSWORD_LENGTH
        and any(char.islower() for char in pool)
        and any(char.isupper() for char in pool)
        and any(char.isdigit() for char in pool)
        and any(char in string.punctuation for char in pool)
    )


def sanitize_filename(filename: str) -> str:
    """Keep a file name inside the current directory."""
    cleaned = "".join(char for char in filename.strip() if char.isalnum() or char in "._-")
    cleaned = cleaned.strip(".")
    if not cleaned:
        raise ValueError("Filename is empty or contains no usable characters.")
    return cleaned


def password_file_path(filename: str) -> Path:
    safe_name = sanitize_filename(filename)
    if not safe_name.lower().endswith(".txt"):
        safe_name += ".txt"
    path = Path(safe_name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Filename must stay in the current directory.")
    return path


def save_password_to_file(password: str, filename: str, *, overwrite: bool = False) -> Path:
    """Write the password to a text file readable only by the current user.

    Existing files are left untouched unless ``overwrite`` is true. A single
    password is stored without a trailing newline. Several passwords are stored
    one per line.
    """
    path = password_file_path(filename)
    if path.is_symlink():
        raise ValueError(f"'{path.name}' is a symbolic link. Choose another filename.")
    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_TRUNC if overwrite else os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
    except OSError:
        os.close(descriptor)
        raise
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        file.write(password)
    return path


def copy_to_clipboard(password: str) -> bool:
    try:
        import pyperclip
    except ImportError:
        print(
            "Clipboard support needs the pyperclip package. Install it with: pip install pyperclip",
            file=sys.stderr,
        )
        return False
    try:
        pyperclip.copy(password)
    except pyperclip.PyperclipException as exc:
        print(f"Error saving password to clipboard: {exc}", file=sys.stderr)
        return False
    print("Password saved to clipboard.", file=sys.stderr)
    return True


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
    print("3. Special Characters (e.g. @#$%)")
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
        parts.append(string.punctuation)
    return "".join(parts)


def _warn_if_cannot_be_strong(length: int, character_list: str) -> None:
    if can_be_strong(length, character_list):
        return
    print(
        "These options cannot produce a strong password. "
        "A strong password needs at least 8 characters, lowercase and uppercase letters, "
        "a digit, and a special character."
    )


def save_password(password: str) -> None:
    if not ask_yes_no("Do you want to save the password? (yes/no): "):
        print("Password not saved")
        return

    if ask_yes_no("Do you want to save to your clipboard? (yes/no): "):
        copy_to_clipboard(password)
        return

    filename = _read_line("Enter the filename to save the password: ")
    try:
        path = password_file_path(filename)
        if path.is_symlink():
            print(f"Error: '{path.name}' is a symbolic link. Choose another filename.")
            return
        overwrite = False
        if path.exists():
            overwrite = ask_yes_no(f"Replace existing file '{path.name}'? (yes/no): ")
            if not overwrite:
                print("Password not saved")
                return
        path = save_password_to_file(password, filename, overwrite=overwrite)
    except ValueError as exc:
        print(f"Error: {exc}")
    except FileExistsError:
        print(f"Error: '{password_file_path(filename).name}' already exists.")
    except FileNotFoundError:
        print("Error: The specified directory does not exist.")
    except PermissionError:
        print("Error: Permission denied. You do not have permission to save the file.")
    except OSError as exc:
        print(f"Error saving password to file: {exc}")
    else:
        print(f"Password saved to '{path.name}' file")


def run_interactive() -> None:
    print("Welcome to the Password Generator")
    print("Follow the prompts to create a secure password.")
    print(
        "A strong password should be at least 8 characters long and include "
        "lowercase and uppercase letters, digits, and special characters."
    )

    length = get_valid_integer_input(
        "Enter password length (e.g., 12): ",
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
    save_password(password)
    print(describe_passwords([password], len(character_list)))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a cryptographically secure random password.",
        epilog="With no options, the generator asks questions interactively.",
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
        help="Include special characters",
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
        help="Copy the password to the clipboard (requires pyperclip)",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILENAME",
        help="Save the password to FILENAME in the current directory (.txt is added if needed)",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Replace the output file if it already exists",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Print only the password",
    )
    return parser


def _noninteractive_pool(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.digits:
        parts.append(string.digits)
    if args.letters:
        parts.append(string.ascii_letters)
    if args.special:
        parts.append(string.punctuation)
    if parts:
        return "".join(parts)
    return string.digits + string.ascii_letters + string.punctuation


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


def run_noninteractive(args: argparse.Namespace) -> None:
    if args.length is None:
        print("Error: --length is required when other options are set.", file=sys.stderr)
        raise SystemExit(2)

    explicit_types = args.digits or args.letters or args.special
    output_path: Path | None = None
    try:
        count = _password_count(args)
        require_password_length(args.length)
        character_list = prepare_character_list(
            _noninteractive_pool(args),
            exclude_ambiguous=args.no_ambiguous,
        )
        if args.output:
            output_path = password_file_path(args.output)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    if output_path is not None and output_path.is_symlink():
        print(
            f"Error: '{output_path.name}' is a symbolic link. Choose another filename.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if output_path is not None and output_path.exists() and not args.force:
        print(
            f"Error: '{output_path.name}' already exists. Pass --force to replace it.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    passwords = [generate_password(args.length, character_list) for _ in range(count)]
    print(_passwords_as_text(passwords))
    sys.stdout.flush()
    if not args.quiet:
        if not explicit_types:
            print(
                "Password uses digits, letters, and special characters.",
                file=sys.stderr,
            )
        if args.no_ambiguous:
            print(
                f"Ambiguous characters left out: {AMBIGUOUS_CHARACTERS}.",
                file=sys.stderr,
            )
        if not can_be_strong(args.length, character_list):
            print(
                "These options cannot produce a strong password. "
                "A strong password needs at least 8 characters, lowercase and uppercase letters, "
                "a digit, and a special character.",
                file=sys.stderr,
            )
        print(describe_passwords(passwords, len(character_list)), file=sys.stderr)

    exit_code = 0
    if args.copy and not copy_to_clipboard(_passwords_as_text(passwords)):
        exit_code = 1
    if args.output:
        try:
            path = save_password_to_file(
                _passwords_as_text(passwords),
                args.output,
                overwrite=args.force,
            )
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            exit_code = 1
        except FileExistsError:
            name = output_path.name if output_path is not None else args.output
            print(
                f"Error: '{name}' already exists. Pass --force to replace it.",
                file=sys.stderr,
            )
            exit_code = 1
        except FileNotFoundError:
            print("Error: The specified directory does not exist.", file=sys.stderr)
            exit_code = 1
        except PermissionError:
            print(
                "Error: Permission denied. You do not have permission to save the file.",
                file=sys.stderr,
            )
            exit_code = 1
        except OSError as exc:
            print(f"Error saving password to file: {exc}", file=sys.stderr)
            exit_code = 1
        else:
            if not args.quiet:
                print(f"Password saved to '{path.name}' file", file=sys.stderr)
    if exit_code:
        raise SystemExit(exit_code)


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    interactive = not any(
        (
            args.length is not None,
            args.digits,
            args.letters,
            args.special,
            args.no_ambiguous,
            args.count is not None,
            args.copy,
            args.output,
            args.force,
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
