#!/usr/bin/env python3
"""Local window for the password generator.

The password stays in this process until you close the window.
Copy places it on the clipboard. Save keeps it for the next time you open the app.
The app does not listen on a network port.
"""

from __future__ import annotations

import base64
import json
import math
import os
import secrets
import shutil
import string
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

import random_password_generator as generator

METER_CAP_BITS = 256
MAX_NAME_LENGTH = 80
MIN_PASSPHRASE_LENGTH = 8
PASSPHRASE_LOSS_WARNING = (
    "If you lose both this passphrase and the recovery key, your saved passwords cannot be recovered."
)
RECOVERY_WORD_COUNT = 8
# scrypt memory is 128 * N * r bytes. 2**15 is 32 MB, slow enough to resist guessing.
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
VAULT_MAGIC = b"LPV1"
VAULT_MAGIC_V2 = b"LPV2"
WRAP_LEN = 60

STYLES = """
window.app {
  background-color: #ebe4d8;
  color: #1c1915;
  font-family: "DejaVu Sans", sans-serif;
}
.card {
  background-color: #f7f3ec;
  background-image: none;
  border: 1px solid #ddd4c6;
  border-radius: 18px;
}
.eyebrow {
  color: #0e6b52;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.5px;
}
.title {
  font-family: "DejaVu Serif", Palatino, serif;
  font-size: 32px;
  font-weight: 700;
}
.lede, .hint, .footer, .caption {
  color: #5f584e;
}
.saved-name {
  font-weight: 700;
  color: #1c1915;
}
.recovery-key {
  font-family: "DejaVu Sans Mono", monospace;
  font-size: 16px;
  font-weight: 700;
  color: #1c1915;
}
.strength.strong { color: #0e6b52; font-weight: 700; }
.strength.weak { color: #8a4b08; font-weight: 700; }
.bits { font-size: 15px; }
.slab {
  background-color: #171512;
  border-radius: 12px;
}
.slab text {
  color: #f6f1e7;
  background-color: #171512;
  font-family: "DejaVu Sans Mono", monospace;
  font-size: 16px;
}
button.mode, button.chip, button.primary, button.secondary {
  background-image: none;
  box-shadow: none;
  text-shadow: none;
  border-radius: 999px;
  border: 1px solid #d9d0c3;
  padding: 8px 14px;
  font-weight: 700;
}
button.mode.off, button.chip.off, button.secondary {
  background-color: #f3efe8;
  color: #6d655c;
  border-color: #d9d0c3;
}
button.mode.off label, button.chip.off label, button.secondary label {
  color: #6d655c;
}
button.mode.on, button.chip.on, button.primary {
  background-color: #0e6b52;
  color: #ffffff;
  border-color: #0e6b52;
}
button.mode.on label, button.chip.on label, button.primary label {
  color: #ffffff;
}
button.note-danger {
  color: #8d2c2c;
}
.danger { color: #8d2c2c; }
progressbar trough {
  min-height: 10px;
  background-color: #e4ddd2;
  border-radius: 999px;
  border: none;
}
progressbar progress {
  background-image: none;
  background-color: #0e6b52;
  border-radius: 999px;
  border: none;
}
progressbar.weak progress {
  background-color: #8a4b08;
}
window.app.dark {
  background-color: #141210;
  color: #f3efe6;
}
window.app.dark .card {
  background-color: #221f1b;
  border-color: #3a342c;
}
window.app.dark .title,
window.app.dark .saved-name,
window.app.dark .recovery-key,
window.app.dark .bits {
  color: #f3efe6;
}
window.app.dark .lede,
window.app.dark .hint,
window.app.dark .footer,
window.app.dark .caption {
  color: #b7aea0;
}
window.app.dark .eyebrow,
window.app.dark .strength.strong {
  color: #7dcea0;
}
window.app.dark .strength.weak,
window.app.dark .danger,
window.app.dark button.note-danger {
  color: #f0a8a0;
}
window.app.dark button.mode.off,
window.app.dark button.chip.off,
window.app.dark button.secondary {
  background-color: #2c2823;
  color: #b7aea0;
  border-color: #3a342c;
}
window.app.dark button.mode.off label,
window.app.dark button.chip.off label,
window.app.dark button.secondary label {
  color: #b7aea0;
}
window.app.dark entry {
  background-color: #141210;
  color: #f3efe6;
  border-color: #3a342c;
}
window.app.dark entry selection {
  background-color: #0e6b52;
  color: #ffffff;
}
window.app.dark progressbar trough {
  background-color: #3a342c;
}
window.app.dark textview {
  background-color: #141210;
  color: #f3efe6;
}
window.app.dark textview text {
  background-color: #141210;
  color: #f3efe6;
}
window.app.dark .slab,
window.app.dark .slab text {
  background-color: #0c0b0a;
  color: #f6f1e7;
}
window.app.dark spinbutton,
window.app.dark spinbutton entry {
  background-color: #141210;
  color: #f3efe6;
}
window.app.dark spinbutton button {
  background-image: none;
  background-color: #2c2823;
  color: #f3efe6;
  border-color: #3a342c;
}
window.app.dark spinbutton button label {
  color: #f3efe6;
}
window.app.dark scrollbar trough {
  background-color: #1c1916;
}
window.app.dark scrollbar slider {
  background-color: #4a433a;
}
window.app.dark checkbutton label {
  color: #f3efe6;
}
window.app.dark progressbar.weak progress {
  background-color: #e0a15a;
}
"""


@dataclass(frozen=True)
class Generated:
    text: str
    label: str
    bits_label: str
    fraction: float
    note: str


def chip_label(name: str, active: bool) -> str:
    state = "On" if active else "Off"
    return f"{name}    {state}"


def _flag(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be true or false.")
    return value


def _count(count: object) -> int:
    if isinstance(count, bool) or not isinstance(count, int):
        raise ValueError("Count must be an integer.")
    if count < 1 or count > generator.MAX_PASSWORD_COUNT:
        raise ValueError(f"Count must be between 1 and {generator.MAX_PASSWORD_COUNT}.")
    return count


def character_pool(*, digits: bool, letters: bool, symbols: bool) -> str:
    """Build the alphabet. Symbols include quotes, backticks, and backslashes."""
    digits = _flag(digits, "Digits")
    letters = _flag(letters, "Letters")
    symbols = _flag(symbols, "Symbols")
    if not (digits or letters or symbols):
        raise ValueError("Choose at least one character type.")
    parts: list[str] = []
    if digits:
        parts.append(string.digits)
    if letters:
        parts.append(string.ascii_letters)
    if symbols:
        parts.append(generator.special_characters(all_special=True))
    return "".join(parts)


def generate(
    *,
    mode: str,
    length: int,
    words: int,
    count: int,
    digits: bool,
    letters: bool,
    symbols: bool,
) -> Generated:
    """Generate passwords in memory. This function does not write a file."""
    count = _count(count)
    if mode == "passphrase":
        word_count = generator.require_word_count(words)
        wordlist = generator.load_wordlist()
        passwords = [
            generator.generate_passphrase(word_count, wordlist=wordlist) for _ in range(count)
        ]
        exact = generator.passphrase_entropy_bits(word_count, len(wordlist))
        note = ""
        if exact < generator.STRONG_ENTROPY_BITS:
            note = (
                f"These options stay under {generator.STRONG_ENTROPY_BITS} bits. "
                "Add words to reach a strong passphrase."
            )
    elif mode == "characters":
        pool = character_pool(digits=digits, letters=letters, symbols=symbols)
        length = generator.require_password_length(length)
        passwords = [generator.generate_password(length, pool) for _ in range(count)]
        exact = generator.password_entropy_bits(length, len(generator.unique_characters(pool)))
        note = "" if generator.can_be_strong(length, pool) else generator.strong_line_message()
    else:
        raise ValueError("Mode must be characters or passphrase.")

    bits = round(exact)
    strong = exact >= generator.STRONG_ENTROPY_BITS
    each = "" if count == 1 else " each"
    return Generated(
        text="\n".join(passwords),
        label="Strong" if strong else "Weak",
        bits_label=f"about {bits} bits{each}",
        fraction=min(exact / METER_CAP_BITS, 1.0),
        note=note,
    )


@dataclass(frozen=True)
class SavedPassword:
    name: str
    password: str


def data_directory() -> Path:
    """Per-user folder for saved passwords. Windows uses Local AppData."""
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        return Path(data_home)
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local)
        return Path.home() / "AppData" / "Local"
    return Path.home() / ".local" / "share"


def saved_passwords_path() -> Path:
    """Per-user file for passwords the person chose to keep."""
    return data_directory() / "local-password" / "saved.txt"


def appearance_path() -> Path:
    """This computer's light or dark choice. It holds no passwords."""
    return data_directory() / "local-password" / "appearance"


def load_dark_mode(path: Path | None = None) -> bool:
    path = appearance_path() if path is None else path
    if path.is_symlink() or not path.is_file():
        return False
    return path.read_text(encoding="utf-8").strip() == "dark"


def store_appearance(dark: bool, path: Path | None = None) -> None:
    """Remember Dark on this computer. The file is readable only by this user."""
    path = appearance_path() if path is None else path
    if path.is_symlink():
        raise ValueError("The appearance file is a link.")
    directory = path.parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    payload = b"dark\n" if dark else b"light\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, payload)
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600)


_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _svg_section(name: str) -> bool:
    folded = name.lower()
    return "scalable" in folded or "symbolic" in folded


def scrub_icon_themes(root: Path) -> tuple[int, int]:
    """Remove SVG theme icons under root so GTK does not abort on Windows.

    The Windows SVG loader fails to open, and GTK then aborts on Adwaita's
    image-missing.svg. PNG icons stay. A one-pixel PNG fills that fallback.
    """
    if not root.is_dir():
        raise FileNotFoundError(f"Icon root is not a directory: {root}")
    icon_dirs: list[Path] = []
    for dirpath, _dirnames, _filenames in os.walk(root, followlinks=True):
        current = Path(dirpath)
        if current.name.lower() == "icons":
            icon_dirs.append(current)
    if not icon_dirs:
        raise FileNotFoundError(f"No icons directory under {root}")

    themes = 0
    removed = 0
    for icons in icon_dirs:
        for theme in icons.rglob("index.theme"):
            if not theme.is_file():
                continue
            themes += 1
            lines = theme.read_text(encoding="utf-8", errors="replace").splitlines()
            kept: list[str] = []
            skip = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    skip = _svg_section(stripped[1:-1])
                if skip:
                    continue
                if stripped.lower().startswith("directories="):
                    parts = [
                        part.strip()
                        for part in stripped.split("=", 1)[1].split(",")
                        if part.strip() and not _svg_section(part)
                    ]
                    line = "Directories=" + ",".join(parts)
                kept.append(line)
            theme.write_text("\n".join(kept) + "\n", encoding="utf-8")
        for cache in list(icons.rglob("icon-theme.cache")):
            if cache.is_file() and not cache.is_symlink():
                cache.unlink()
        for status in icons.rglob("status"):
            if status.is_dir():
                (status / "image-missing.png").write_bytes(_PNG_1PX)
        for svg in list(icons.rglob("*.svg")):
            if svg.is_file() or svg.is_symlink():
                svg.unlink()
                removed += 1
    remaining = [svg for icons in icon_dirs for svg in icons.rglob("*.svg")]
    if themes == 0:
        raise FileNotFoundError(f"No index.theme under {root}")
    if remaining:
        raise RuntimeError(f"SVG icons remain: {remaining[0]}")
    return themes, removed


def repair_bundled_icons() -> None:
    """Drop bundled SVG theme icons before GTK starts. Source checkouts are left alone."""
    if not getattr(sys, "frozen", False):
        return
    roots: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))
    roots.append(Path(sys.executable).resolve().parent)
    seen: set[Path] = set()
    for root in roots:
        try:
            resolved = root.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            scrub_icon_themes(root)
        except (FileNotFoundError, RuntimeError, OSError):
            continue


def clean_name(name: str) -> str:
    """Collapse a purpose label to one short line."""
    if "\n" in name or "\r" in name:
        raise ValueError("The name must be a single line.")
    cleaned = " ".join(name.split())
    if not cleaned:
        raise ValueError("Name this password so you can recognize it later.")
    if len(cleaned) > MAX_NAME_LENGTH:
        raise ValueError(f"The name must be {MAX_NAME_LENGTH} characters or fewer.")
    return cleaned


def _password_line(password: str) -> str:
    if not password or "\n" in password or "\r" in password:
        raise ValueError("A saved password must be a single line.")
    return password


def _legacy_name(used: set[str]) -> str:
    name = "Untitled"
    number = 2
    while name in used:
        name = f"Untitled {number}"
        number += 1
    return name


def _record_from_line(line: str, used: set[str]) -> SavedPassword:
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict) and isinstance(parsed.get("name"), str) and isinstance(parsed.get("password"), str):
        item = SavedPassword(clean_name(parsed["name"]), _password_line(parsed["password"]))
    else:
        item = SavedPassword(_legacy_name(used), _password_line(line))
    return item


def load_saved_passwords(path: Path | None = None) -> list[SavedPassword]:
    """Read named passwords. A missing file means none are saved.

    Older files stored one password per line. Those load with the name Untitled.
    """
    path = saved_passwords_path() if path is None else path
    if path.is_symlink():
        raise ValueError("The saved password file is a symbolic link.")
    if not path.exists():
        return []
    if not path.is_file():
        raise ValueError("The saved password file is not a regular file.")
    used: set[str] = set()
    saved: list[SavedPassword] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        item = _record_from_line(line, used)
        if item.name in used:
            continue
        used.add(item.name)
        saved.append(item)
    return saved


def remember_named(
    existing: list[SavedPassword],
    name: str,
    passwords: list[str],
) -> list[SavedPassword]:
    """Save these passwords under a name. The same name replaces the previous one."""
    label = clean_name(name)
    if not passwords:
        raise ValueError("There is no password to save.")
    if len(passwords) == 1:
        fresh = [SavedPassword(label, _password_line(passwords[0]))]
    else:
        extra = len(str(len(passwords))) + 1
        if len(label) + extra > MAX_NAME_LENGTH:
            raise ValueError(f"The name must be {MAX_NAME_LENGTH - extra} characters or fewer for this many passwords.")
        fresh = [
            SavedPassword(f"{label} {index}", _password_line(password))
            for index, password in enumerate(passwords, start=1)
        ]
    replaced = {item.name for item in fresh}
    replaced.add(label)
    kept = [item for item in existing if item.name not in replaced]
    return fresh + kept


def units_for_bits(pool_size: int, bits: int = METER_CAP_BITS) -> int:
    """How many independent choices it takes to reach this many bits."""
    if pool_size < 2:
        raise ValueError("Choose at least one character type.")
    return math.ceil(bits / math.log2(pool_size))


def length_for_bits(character_list: str, bits: int = METER_CAP_BITS) -> int:
    needed = units_for_bits(len(generator.unique_characters(character_list)), bits)
    if needed > generator.MAX_PASSWORD_LENGTH:
        raise ValueError("These characters cannot reach 256 bits at the allowed length.")
    return needed


def words_for_bits(bits: int = METER_CAP_BITS) -> int:
    needed = units_for_bits(len(generator.load_wordlist()), bits)
    if needed > generator.MAX_WORD_COUNT:
        raise ValueError("That many bits needs more words than the limit allows.")
    return needed


def saved_display(items: list[SavedPassword]) -> str:
    """Show each name above its password."""
    return "\n\n".join(f"{item.name}\n{item.password}" for item in items)


def store_saved_passwords(passwords: list[SavedPassword], path: Path | None = None) -> Path:
    """Write named passwords so only the current user can read the file."""
    path = saved_passwords_path() if path is None else path
    lines = [
        json.dumps(
            {"name": clean_name(item.name), "password": _password_line(item.password)},
            ensure_ascii=False,
        )
        for item in passwords
    ]
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass
    if path.is_symlink():
        raise ValueError("The saved password file is a symbolic link.")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        payload = "".join(f"{line}\n" for line in lines).encode("utf-8")
        os.write(descriptor, payload)
    finally:
        os.close(descriptor)
    return path


@dataclass(frozen=True)
class VaultKey:
    key: bytes
    salt: bytes
    n: int
    r: int
    p: int
    recovery_salt: bytes = b""
    passphrase_wrap: bytes = b""
    recovery_wrap: bytes = b""


def vault_path() -> Path:
    """Encrypted file that holds saved passwords."""
    return saved_passwords_path().with_name("saved.vault")


def require_passphrase(passphrase: str) -> str:
    if len(passphrase) < MIN_PASSPHRASE_LENGTH:
        raise ValueError(
            f"Use at least {MIN_PASSPHRASE_LENGTH} characters for the passphrase."
        )
    return passphrase


def normalize_recovery_key(recovery_key: str) -> str:
    """Ignore case and extra spaces so a written key still matches."""
    return " ".join(recovery_key.casefold().split())


def new_recovery_key() -> str:
    """Eight random words. This key is shown once and is not stored."""
    words = generator.load_wordlist()
    return " ".join(secrets.choice(words) for _ in range(RECOVERY_WORD_COUNT))


def require_recovery_key(recovery_key: str) -> str:
    normalized = normalize_recovery_key(recovery_key)
    if len(normalized.split()) != RECOVERY_WORD_COUNT:
        raise ValueError("The recovery key is not complete.")
    return normalized


def new_vault_key(passphrase: str, recovery_key: str | None = None, *, n: int = SCRYPT_N) -> VaultKey:
    """Derive a key. The passphrase and recovery key are not kept."""
    require_passphrase(passphrase)
    salt = os.urandom(16)
    if recovery_key is None:
        return VaultKey(_derive_key(passphrase, salt, n, SCRYPT_R, SCRYPT_P), salt, n, SCRYPT_R, SCRYPT_P)
    normalized = require_recovery_key(recovery_key)
    recovery_salt = os.urandom(16)
    header = _v2_header(n, SCRYPT_R, SCRYPT_P, salt, recovery_salt)
    dek = os.urandom(32)
    passphrase_wrap = _wrap_dek(_derive_key(passphrase, salt, n, SCRYPT_R, SCRYPT_P), dek, header)
    recovery_wrap = _wrap_dek(
        _derive_key(normalized, recovery_salt, n, SCRYPT_R, SCRYPT_P),
        dek,
        header,
    )
    return VaultKey(dek, salt, n, SCRYPT_R, SCRYPT_P, recovery_salt, passphrase_wrap, recovery_wrap)


def _derive_key(passphrase: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    if r != SCRYPT_R or p != SCRYPT_P or n < 2**14 or n > 2**16 or n & (n - 1):
        raise ValueError("The saved password file is damaged.")
    kdf = Scrypt(salt=salt, length=32, n=n, r=r, p=p)
    return kdf.derive(passphrase.encode("utf-8"))


def _encode_saved(items: list[SavedPassword]) -> bytes:
    payload = [
        {"name": clean_name(item.name), "password": _password_line(item.password)}
        for item in items
    ]
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _decode_saved(raw: bytes) -> list[SavedPassword]:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("The saved password file is damaged.") from exc
    if not isinstance(parsed, list):
        raise ValueError("The saved password file is damaged.")
    saved: list[SavedPassword] = []
    used: set[str] = set()
    for entry in parsed:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not isinstance(entry.get("password"), str):
            raise ValueError("The saved password file is damaged.")
        try:
            item = SavedPassword(clean_name(entry["name"]), _password_line(entry["password"]))
        except ValueError as exc:
            raise ValueError("The saved password file is damaged.") from exc
        if item.name in used:
            continue
        used.add(item.name)
        saved.append(item)
    return saved


def _v2_header(n: int, r: int, p: int, passphrase_salt: bytes, recovery_salt: bytes) -> bytes:
    return (
        VAULT_MAGIC_V2
        + n.to_bytes(4, "big")
        + r.to_bytes(4, "big")
        + p.to_bytes(4, "big")
        + passphrase_salt
        + recovery_salt
    )


def _wrap_dek(kek: bytes, dek: bytes, header: bytes) -> bytes:
    nonce = os.urandom(12)
    return nonce + AESGCM(kek).encrypt(nonce, dek, header)


def _unwrap_dek(kek: bytes, wrapped: bytes, header: bytes) -> bytes:
    if len(wrapped) != WRAP_LEN:
        raise ValueError("The saved password file is damaged.")
    nonce, ciphertext = wrapped[:12], wrapped[12:]
    return AESGCM(kek).decrypt(nonce, ciphertext, header)


def write_vault(material: VaultKey, items: list[SavedPassword], path: Path | None = None) -> Path:
    """Encrypt saved passwords. A later read needs the passphrase or the recovery key."""
    path = vault_path() if path is None else path
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass
    if path.is_symlink():
        raise ValueError("The saved password file is a symbolic link.")
    if material.recovery_wrap:
        header = _v2_header(material.n, material.r, material.p, material.salt, material.recovery_salt)
        associated = header + material.passphrase_wrap + material.recovery_wrap
        body = material.passphrase_wrap + material.recovery_wrap
    else:
        header = (
            VAULT_MAGIC
            + material.n.to_bytes(4, "big")
            + material.r.to_bytes(4, "big")
            + material.p.to_bytes(4, "big")
            + material.salt
        )
        associated = header
        body = b""
    nonce = os.urandom(12)
    ciphertext = AESGCM(material.key).encrypt(nonce, _encode_saved(items), associated)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        os.write(descriptor, header + body + nonce + ciphertext)
    finally:
        os.close(descriptor)
    return path


def open_vault(secret: str, path: Path | None = None) -> tuple[VaultKey, list[SavedPassword]]:
    """Unlock saved passwords. A wrong passphrase or recovery key raises ValueError."""
    if len(secret) < MIN_PASSPHRASE_LENGTH:
        raise ValueError("That passphrase or recovery key did not unlock the saved passwords.")
    path = vault_path() if path is None else path
    if path.is_symlink():
        raise ValueError("The saved password file is a symbolic link.")
    if not path.is_file():
        raise ValueError("The saved password file is damaged.")
    blob = path.read_bytes()
    if blob.startswith(VAULT_MAGIC_V2):
        return _open_vault_v2(secret, blob)
    if blob.startswith(VAULT_MAGIC):
        return _open_vault_v1(secret, blob)
    raise ValueError("The saved password file is damaged.")


def _open_vault_v1(passphrase: str, blob: bytes) -> tuple[VaultKey, list[SavedPassword]]:
    if len(blob) < 44 + 16:
        raise ValueError("The saved password file is damaged.")
    n = int.from_bytes(blob[4:8], "big")
    r = int.from_bytes(blob[8:12], "big")
    p = int.from_bytes(blob[12:16], "big")
    salt = blob[16:32]
    nonce = blob[32:44]
    ciphertext = blob[44:]
    header = blob[:32]
    try:
        key = _derive_key(passphrase, salt, n, r, p)
        raw = AESGCM(key).decrypt(nonce, ciphertext, header)
    except InvalidTag as exc:
        raise ValueError("That passphrase did not unlock the saved passwords.") from exc
    except ValueError as exc:
        raise ValueError("The saved password file is damaged.") from exc
    return VaultKey(key, salt, n, r, p), _decode_saved(raw)


def _open_vault_v2(secret: str, blob: bytes) -> tuple[VaultKey, list[SavedPassword]]:
    fixed = 48 + WRAP_LEN + WRAP_LEN + 12
    if len(blob) < fixed + 16:
        raise ValueError("The saved password file is damaged.")
    n = int.from_bytes(blob[4:8], "big")
    r = int.from_bytes(blob[8:12], "big")
    p = int.from_bytes(blob[12:16], "big")
    passphrase_salt = blob[16:32]
    recovery_salt = blob[32:48]
    passphrase_wrap = blob[48:48 + WRAP_LEN]
    recovery_wrap = blob[48 + WRAP_LEN:48 + WRAP_LEN + WRAP_LEN]
    nonce = blob[48 + WRAP_LEN + WRAP_LEN:48 + WRAP_LEN + WRAP_LEN + 12]
    ciphertext = blob[48 + WRAP_LEN + WRAP_LEN + 12:]
    header = blob[:48]
    associated = header + passphrase_wrap + recovery_wrap
    dek = _unlock_dek(secret, passphrase_salt, passphrase_wrap, n, r, p, header)
    if dek is None:
        dek = _unlock_dek(
            normalize_recovery_key(secret),
            recovery_salt,
            recovery_wrap,
            n,
            r,
            p,
            header,
        )
    if dek is None:
        raise ValueError("That passphrase or recovery key did not unlock the saved passwords.")
    try:
        raw = AESGCM(dek).decrypt(nonce, ciphertext, associated)
    except InvalidTag as exc:
        raise ValueError("The saved password file is damaged.") from exc
    material = VaultKey(
        dek,
        passphrase_salt,
        n,
        r,
        p,
        recovery_salt,
        passphrase_wrap,
        recovery_wrap,
    )
    return material, _decode_saved(raw)


def _unlock_dek(
    secret: str,
    salt: bytes,
    wrapped: bytes,
    n: int,
    r: int,
    p: int,
    header: bytes,
) -> bytes | None:
    try:
        kek = _derive_key(secret, salt, n, r, p)
        return _unwrap_dek(kek, wrapped, header)
    except InvalidTag:
        return None
    except ValueError as exc:
        raise ValueError("The saved password file is damaged.") from exc


def erase_saved_file(path: Path) -> None:
    """Overwrite a leftover plaintext file, then delete it."""
    if not path.exists():
        return
    if path.is_symlink() or not path.is_file():
        raise ValueError("The saved password file is a symbolic link.")
    size = path.stat().st_size
    flags = os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        os.write(descriptor, b"\0" * size)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    path.unlink()


def copy_with_xclip(text: str) -> bool:
    """Copy text by piping it to xclip. The password is not a command argument."""
    if shutil.which("xclip") is None:
        return False
    try:
        subprocess.run(
            ["xclip", "-selection", "clipboard", "-in"],
            input=text.encode("utf-8"),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def _icon_candidates() -> list[Path]:
    here = Path(__file__).resolve().parent
    root = generator.app_root()
    return [
        root / "local-password.png",
        here / "local-password.png",
        here / "packaging" / "windows" / "local-password.png",
        root / "local-password.svg",
        here / "local-password.svg",
        here / "packaging" / "local-password.svg",
        Path("/usr/share/icons/hicolor/scalable/apps/local-password.svg"),
    ]


def install_styles(gtk, gdk) -> None:
    provider = gtk.CssProvider()
    provider.load_from_data(STYLES.encode("utf-8"))
    gtk.StyleContext.add_provider_for_screen(
        gdk.Screen.get_default(),
        provider,
        gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


def set_windows_app_id() -> None:
    """Tell Windows this window is its own app, so the taskbar keeps its icon."""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LocalPassword.App")
    except Exception:
        return


def main() -> None:
    set_windows_app_id()
    repair_bundled_icons()
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, Gtk

    if Gdk.Display.get_default() is None:
        print(
            "Local Password needs a graphical session. There is no page to open.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    install_styles(Gtk, Gdk)

    window = PasswordWindow(Gtk, Gdk)
    window.window.connect("destroy", Gtk.main_quit)
    window.window.show_all()
    window.show_section(window.section)
    Gtk.main()


class PasswordWindow:
    """GTK window. Constructed with the Gtk and Gdk modules so import stays light."""

    def __init__(self, gtk, gdk) -> None:
        self.gtk = gtk
        self.gdk = gdk
        self.mode = "characters"
        self.current = ""

        self.window = gtk.Window(title="Local Password")
        self.window.set_default_size(960, 680)
        self.window.set_size_request(720, 560)
        self.window.get_style_context().add_class("app")
        for icon in _icon_candidates():
            if icon.is_file():
                try:
                    self.window.set_icon_from_file(str(icon))
                except Exception:
                    pass
                break

        root = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=16)
        root.set_margin_top(24)
        root.set_margin_bottom(20)
        root.set_margin_start(24)
        root.set_margin_end(24)
        self.window.add(root)

        eyebrow = gtk.Label(label="ON THIS COMPUTER", xalign=0)
        eyebrow.get_style_context().add_class("eyebrow")
        title = gtk.Label(label="Local Password", xalign=0)
        title.set_hexpand(True)
        title.set_xalign(0)
        title.get_style_context().add_class("title")
        self.dark = load_dark_mode()
        self.dark_button = gtk.Button(label=chip_label("Dark", self.dark))
        self.dark_button.get_style_context().add_class("chip")
        self.dark_button.set_valign(gtk.Align.CENTER)
        self.dark_button.connect("clicked", self.on_toggle_dark)
        heading = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=12)
        heading.pack_start(title, True, True, 0)
        heading.pack_start(self.dark_button, False, False, 0)
        lede = gtk.Label(
            label=(
                "Create a password here, or open Saved to use the ones you already kept. A passphrase or a recovery key opens all of them."
            ),
            xalign=0,
        )
        lede.set_line_wrap(True)
        lede.get_style_context().add_class("lede")
        root.pack_start(eyebrow, False, False, 0)
        root.pack_start(heading, False, False, 0)
        root.pack_start(lede, False, False, 0)
        self.apply_dark()

        nav = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        nav.set_homogeneous(True)
        self.create_tab = gtk.Button(label="Create")
        self.saved_tab = gtk.Button(label="Saved")
        for button in (self.create_tab, self.saved_tab):
            button.get_style_context().add_class("mode")
            nav.pack_start(button, True, True, 0)
        self.create_tab.connect("clicked", lambda *_args: self.show_section("create"))
        self.saved_tab.connect("clicked", lambda *_args: self.show_section("saved"))
        root.pack_start(nav, False, False, 0)

        columns = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=16)
        columns.set_vexpand(True)
        self.create_view = columns
        root.pack_start(self.create_view, True, True, 0)

        controls_frame, controls = self._card()
        columns.pack_start(controls_frame, True, True, 0)
        self._build_controls(controls)

        result_frame, result = self._card()
        columns.pack_start(result_frame, True, True, 0)
        self._build_result(result)

        saved_frame, saved_inner = self._card()
        self.saved_view = saved_frame
        self.saved_view.set_vexpand(True)
        self.saved_view.set_no_show_all(True)
        self.saved_view.hide()
        root.pack_start(self.saved_view, True, True, 0)
        self._build_manager(saved_inner)

        footer = gtk.Label(
            label=(
                "Passphrases use the EFF large wordlist, created by Joseph Bonneau "
                "and the Electronic Frontier Foundation, under CC BY 3.0 US. "
                "The EFF does not endorse this project."
            ),
            xalign=0,
        )
        footer.set_line_wrap(True)
        footer.get_style_context().add_class("footer")
        root.pack_start(footer, False, False, 0)

    def on_toggle_dark(self, *_args) -> None:
        self.dark = not self.dark
        self.apply_dark()
        try:
            store_appearance(self.dark)
        except OSError:
            pass

    def apply_dark(self) -> None:
        context = self.window.get_style_context()
        button = self.dark_button.get_style_context()
        if self.dark:
            context.add_class("dark")
            button.remove_class("off")
            button.add_class("on")
        else:
            context.remove_class("dark")
            button.remove_class("on")
            button.add_class("off")
        self.dark_button.set_label(chip_label("Dark", self.dark))

    def _match_dialog(self, dialog) -> None:
        context = dialog.get_style_context()
        context.add_class("app")
        if self.dark:
            context.add_class("dark")

    def _card(self):
        outer = self.gtk.Box(orientation=self.gtk.Orientation.VERTICAL)
        outer.get_style_context().add_class("card")
        outer.set_vexpand(True)
        inner = self.gtk.Box(orientation=self.gtk.Orientation.VERTICAL, spacing=12)
        for setter in (
            inner.set_margin_top,
            inner.set_margin_bottom,
            inner.set_margin_start,
            inner.set_margin_end,
        ):
            setter(16)
        outer.pack_start(inner, True, True, 0)
        return outer, inner

    def _build_controls(self, controls) -> None:
        gtk = self.gtk
        mode_row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        mode_row.set_homogeneous(True)
        self.mode_characters = gtk.Button(label="Characters")
        self.mode_words = gtk.Button(label="Words")
        for button in (self.mode_characters, self.mode_words):
            button.get_style_context().add_class("mode")
            mode_row.pack_start(button, True, True, 0)
        self.mode_characters.connect("clicked", lambda *_: self.set_mode("characters"))
        self.mode_words.connect("clicked", lambda *_: self.set_mode("passphrase"))
        controls.pack_start(mode_row, False, False, 0)

        self.character_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=12)
        controls.pack_start(self.character_box, False, False, 0)
        self.length = gtk.SpinButton.new_with_range(
            generator.MIN_PASSWORD_LENGTH, generator.MAX_PASSWORD_LENGTH, 1
        )
        self.length.set_value(16)
        self.length.set_numeric(True)
        self.character_box.pack_start(self._labeled("Length", self.length), False, False, 0)

        chips = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        chips.set_homogeneous(True)
        self.digits = self._chip("Digits", True)
        self.letters = self._chip("Letters", True)
        self.symbols = self._chip("Symbols", True)
        for chip in (self.digits, self.letters, self.symbols):
            chips.pack_start(chip, True, True, 0)
        self.character_box.pack_start(chips, False, False, 0)
        symbol_hint = gtk.Label(
            label="Symbols include quotes, backticks, and backslashes.",
            xalign=0,
        )
        symbol_hint.set_line_wrap(True)
        symbol_hint.get_style_context().add_class("hint")
        self.character_box.pack_start(symbol_hint, False, False, 0)

        self.word_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=8)
        self.word_box.set_no_show_all(True)
        controls.pack_start(self.word_box, False, False, 0)
        self.words = gtk.SpinButton.new_with_range(
            generator.MIN_WORD_COUNT, generator.MAX_WORD_COUNT, 1
        )
        self.words.set_value(generator.DEFAULT_WORD_COUNT)
        self.words.set_numeric(True)
        self.word_box.pack_start(self._labeled("Words", self.words), False, False, 0)
        word_hint = gtk.Label(
            label="Six words from the EFF list are about 78 bits. Five words fall short of the strong line.",
            xalign=0,
        )
        word_hint.set_line_wrap(True)
        word_hint.get_style_context().add_class("hint")
        self.word_box.pack_start(word_hint, False, False, 0)

        self.count = gtk.SpinButton.new_with_range(1, generator.MAX_PASSWORD_COUNT, 1)
        self.count.set_value(1)
        self.count.set_numeric(True)
        count_box = self._labeled("Number of passwords", self.count)
        count_hint = gtk.Label(
            label="Each password can be named and saved on its own.",
            xalign=0,
        )
        count_hint.get_style_context().add_class("hint")
        count_box.pack_start(count_hint, False, False, 0)
        controls.pack_start(count_box, False, False, 0)

        self.generate_button = gtk.Button(label="Generate")
        self.generate_button.get_style_context().add_class("primary")
        self.generate_button.connect("clicked", self.on_generate)
        controls.pack_start(self.generate_button, False, False, 0)
        self._style_mode_buttons()

    def _build_result(self, result) -> None:
        gtk = self.gtk
        head = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=12)
        self.strength = gtk.Label(label="Result", xalign=0)
        self.strength.get_style_context().add_class("strength")
        self.strength.set_hexpand(True)
        self.bits = gtk.Label(label="Waiting to generate", xalign=1)
        self.bits.get_style_context().add_class("bits")
        head.pack_start(self.strength, True, True, 0)
        head.pack_start(self.bits, False, False, 0)
        result.pack_start(head, False, False, 0)

        self.meter = gtk.ProgressBar()
        self.meter.set_fraction(0)
        result.pack_start(self.meter, False, False, 0)
        caption = gtk.Label(
            label="The bar fills toward 256 bits. Strong starts at 75.",
            xalign=0,
        )
        caption.set_line_wrap(True)
        caption.get_style_context().add_class("caption")
        result.pack_start(caption, False, False, 0)

        self.note = gtk.Label(label="", xalign=0)
        self.note.set_line_wrap(True)
        self.note.get_style_context().add_class("danger")
        self.note.set_no_show_all(True)
        self.note.hide()
        result.pack_start(self.note, False, False, 0)

        self.buffer = gtk.TextBuffer()
        self.view = gtk.TextView.new_with_buffer(self.buffer)
        self.view.set_editable(False)
        self.view.set_cursor_visible(False)
        self.view.set_wrap_mode(gtk.WrapMode.WORD_CHAR)
        self.view.set_left_margin(14)
        self.view.set_right_margin(14)
        self.view.set_top_margin(14)
        self.view.set_bottom_margin(14)
        self.view.get_style_context().add_class("slab")
        self.view.connect("realize", lambda *_: self.view.drag_source_unset())
        scroller = gtk.ScrolledWindow()
        scroller.set_policy(gtk.PolicyType.NEVER, gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_height(160)
        scroller.set_vexpand(True)
        scroller.add(self.view)

        name_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=4)
        name_label = gtk.Label(label="Name", xalign=0)
        self.name_entry = gtk.Entry()
        self.name_entry.set_placeholder_text("Email, bank, router")
        self.name_entry.set_max_length(MAX_NAME_LENGTH)
        self.name_entry.connect("activate", self.on_save)
        name_hint = gtk.Label(label="What this password is for.", xalign=0)
        name_hint.set_line_wrap(True)
        name_hint.get_style_context().add_class("hint")
        name_box.pack_start(name_label, False, False, 0)
        name_box.pack_start(self.name_entry, False, False, 0)
        name_box.pack_start(name_hint, False, False, 0)

        actions = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_homogeneous(True)
        self.copy_button = gtk.Button(label="Copy")
        self.copy_button.get_style_context().add_class("primary")
        self.copy_button.set_sensitive(False)
        self.copy_button.connect("clicked", self.on_copy)
        self.save_button = gtk.Button(label="Save")
        self.save_button.get_style_context().add_class("secondary")
        self.save_button.set_sensitive(False)
        self.save_button.connect("clicked", self.on_save)
        actions.pack_start(self.copy_button, True, True, 0)
        actions.pack_start(self.save_button, True, True, 0)

        self.single_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=12)
        self.single_box.set_vexpand(True)
        self.single_box.pack_start(scroller, True, True, 0)
        self.single_box.pack_start(name_box, False, False, 0)
        self.single_box.pack_start(actions, False, False, 0)
        result.pack_start(self.single_box, True, True, 0)

        self.batch_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=12)
        self.batch_scroll = gtk.ScrolledWindow()
        self.batch_scroll.set_policy(gtk.PolicyType.NEVER, gtk.PolicyType.AUTOMATIC)
        self.batch_scroll.set_vexpand(True)
        self.batch_scroll.set_min_content_height(220)
        self.batch_scroll.set_no_show_all(True)
        self.batch_scroll.hide()
        self.batch_scroll.add(self.batch_box)
        result.pack_start(self.batch_scroll, True, True, 0)
        self.batch: list[str] = []

        recovery = gtk.Label(label=PASSPHRASE_LOSS_WARNING, xalign=0)
        recovery.set_line_wrap(True)
        recovery.get_style_context().add_class("danger")
        result.pack_start(recovery, False, False, 0)

        self.status = gtk.Label(
            label="Generate a password. Name it, then save it.",
            xalign=0,
        )
        self.status.set_line_wrap(True)
        self.status.get_style_context().add_class("hint")
        result.pack_start(self.status, False, False, 0)

    def _build_manager(self, page) -> None:
        gtk = self.gtk
        self.saved_heading = gtk.Label(label="Saved", xalign=0)
        self.saved_heading.get_style_context().add_class("eyebrow")
        page.pack_start(self.saved_heading, False, False, 0)

        self.find_entry = gtk.Entry()
        self.find_entry.set_placeholder_text("Find by name")
        self.find_entry.connect("changed", lambda *_args: self._refresh_saved_rows())
        page.pack_start(self.find_entry, False, False, 0)

        self.manager_message = gtk.Label(label="", xalign=0)
        self.manager_message.set_line_wrap(True)
        self.manager_message.get_style_context().add_class("hint")
        page.pack_start(self.manager_message, False, False, 0)

        self.saved_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=8)
        self.saved_scroll = gtk.ScrolledWindow()
        self.saved_scroll.set_policy(gtk.PolicyType.NEVER, gtk.PolicyType.AUTOMATIC)
        self.saved_scroll.set_vexpand(True)
        self.saved_scroll.set_min_content_height(240)
        self.saved_scroll.add(self.saved_box)
        page.pack_start(self.saved_scroll, True, True, 0)

        self.lock_button = gtk.Button(label="Unlock")
        self.lock_button.get_style_context().add_class("primary")
        self.lock_button.set_no_show_all(True)
        self.lock_button.hide()
        self.lock_button.connect("clicked", self.on_lock_toggle)
        page.pack_start(self.lock_button, False, False, 0)

        self.saved: list[SavedPassword] = []
        self.showing_saved = False
        self.save_ready = False
        self.locked = False
        self.vault_key: VaultKey | None = None
        self.section = "create"
        self._prepare_saved()
        self.show_section("saved" if self.locked else "create")

    def _labeled(self, caption: str, control):
        row = self.gtk.Box(orientation=self.gtk.Orientation.VERTICAL, spacing=4)
        line = self.gtk.Box(orientation=self.gtk.Orientation.HORIZONTAL, spacing=8)
        label = self.gtk.Label(label=caption, xalign=0)
        label.set_hexpand(True)
        line.pack_start(label, True, True, 0)
        line.pack_start(control, False, False, 0)
        row.pack_start(line, False, False, 0)
        return row

    def _chip(self, name: str, active: bool):
        button = self.gtk.ToggleButton(label=chip_label(name, active))
        button.set_active(active)
        button.get_style_context().add_class("chip")
        button.connect("toggled", lambda widget: self._paint_chip(widget, name))
        self._paint_chip(button, name)
        return button

    def _paint_chip(self, button, name: str) -> None:
        button.set_label(chip_label(name, button.get_active()))
        style = button.get_style_context()
        if button.get_active():
            style.add_class("on")
            style.remove_class("off")
        else:
            style.add_class("off")
            style.remove_class("on")

    def _style_mode_buttons(self) -> None:
        characters = self.mode == "characters"
        for button, selected in (
            (self.mode_characters, characters),
            (self.mode_words, not characters),
        ):
            style = button.get_style_context()
            if selected:
                style.add_class("on")
                style.remove_class("off")
            else:
                style.add_class("off")
                style.remove_class("on")

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.apply_mode()

    def apply_mode(self) -> None:
        words = self.mode == "passphrase"
        self.character_box.set_visible(not words)
        if words:
            self.word_box.set_no_show_all(False)
            self.word_box.show_all()
        else:
            self.word_box.hide()
        self._style_mode_buttons()

    def show_section(self, section: str) -> None:
        """Show Create or Saved. The hidden page stays hidden after show_all."""
        self.section = "saved" if section == "saved" else "create"
        saved = self.section == "saved"
        if saved:
            self.create_view.set_no_show_all(True)
            self.create_view.hide()
            self.saved_view.set_no_show_all(False)
            self.saved_view.show_all()
            self._refresh_saved_rows()
            self._update_lock_button()
        else:
            self.saved_view.set_no_show_all(True)
            self.saved_view.hide()
            self.create_view.set_no_show_all(False)
            self.create_view.show_all()
            self.apply_mode()
        for button, selected in (
            (self.create_tab, not saved),
            (self.saved_tab, saved),
        ):
            style = button.get_style_context()
            if selected:
                style.add_class("on")
                style.remove_class("off")
            else:
                style.add_class("off")
                style.remove_class("on")

    def set_note(self, text: str) -> None:
        self.note.set_text(text)
        if text:
            self.note.show()
        else:
            self.note.hide()

    def on_generate(self, _button) -> None:
        try:
            result = generate(
                mode=self.mode,
                length=self.length.get_value_as_int(),
                words=self.words.get_value_as_int(),
                count=self.count.get_value_as_int(),
                digits=self.digits.get_active(),
                letters=self.letters.get_active(),
                symbols=self.symbols.get_active(),
            )
        except ValueError as exc:
            self.set_note(str(exc))
            return
        passwords = [line for line in result.text.splitlines() if line]
        self.batch = passwords
        self.current = result.text
        self.showing_saved = False
        self.save_ready = True
        self.buffer.set_text(result.text)
        if len(passwords) > 1:
            self._show_batch(passwords)
        else:
            self._show_single()
        self.strength.set_text(result.label)
        strength_style = self.strength.get_style_context()
        if result.label == "Strong":
            strength_style.add_class("strong")
            strength_style.remove_class("weak")
            self.meter.get_style_context().remove_class("weak")
        else:
            strength_style.add_class("weak")
            strength_style.remove_class("strong")
            self.meter.get_style_context().add_class("weak")
        self.bits.set_text(result.bits_label)
        self.meter.set_fraction(result.fraction)
        self.set_note(result.note)
        self.copy_button.set_sensitive(True)
        self.save_button.set_sensitive(True)
        if len(passwords) > 1:
            self.status.set_text("Name the ones you want to keep. The rest are gone when you close.")
        else:
            self.status.set_text("Name it, then save it. Otherwise it is gone when you close.")

    def _show_single(self) -> None:
        self.batch_scroll.hide()
        self.batch_scroll.set_no_show_all(True)
        self.single_box.set_no_show_all(False)
        self.single_box.show_all()

    def _show_batch(self, passwords: list[str]) -> None:
        for child in list(self.batch_box.get_children()):
            self.batch_box.remove(child)
        for password in passwords:
            self.batch_box.pack_start(self._batch_row(password), False, False, 0)
        self.single_box.hide()
        self.single_box.set_no_show_all(True)
        self.batch_scroll.set_no_show_all(False)
        self.batch_scroll.show_all()

    def _batch_row(self, password: str):
        gtk = self.gtk
        row = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=6)
        secret = gtk.Label(label=password, xalign=0)
        secret.set_line_wrap(True)
        secret.set_selectable(True)
        secret.set_max_width_chars(42)
        secret.get_style_context().add_class("saved-name")
        name = gtk.Entry()
        name.set_placeholder_text("Name this one")
        name.set_max_length(MAX_NAME_LENGTH)
        note = gtk.Label(label="", xalign=0)
        note.set_line_wrap(True)
        note.get_style_context().add_class("hint")
        actions = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        copy = gtk.Button(label="Copy")
        copy.get_style_context().add_class("primary")
        copy.connect("clicked", lambda *_args, text=password: self.on_copy_text(text))
        save = gtk.Button(label="Save")
        save.get_style_context().add_class("secondary")
        save.connect(
            "clicked",
            lambda *_args, text=password, entry=name, status=note: self.on_save_one(text, entry, status),
        )
        name.connect(
            "activate",
            lambda *_args, text=password, entry=name, status=note: self.on_save_one(text, entry, status),
        )
        actions.pack_start(copy, True, True, 0)
        actions.pack_start(save, True, True, 0)
        row.pack_start(secret, False, False, 0)
        row.pack_start(name, False, False, 0)
        row.pack_start(actions, False, False, 0)
        row.pack_start(note, False, False, 0)
        return row

    def on_save_one(self, password: str, name_entry, row_status) -> None:
        """Save one generated password. The others stay unsaved."""
        try:
            label = clean_name(name_entry.get_text())
        except ValueError as exc:
            row_status.set_text(str(exc))
            self.status.set_text(str(exc))
            return
        if not self._ensure_vault_key():
            return
        try:
            updated = remember_named(self.saved, label, [password])
            write_vault(self.vault_key, updated)
        except ValueError as exc:
            row_status.set_text(str(exc))
            self.status.set_text(str(exc))
            return
        except OSError:
            row_status.set_text("Could not save the password.")
            self.status.set_text("Could not save the password.")
            return
        self.saved = updated
        self.locked = False
        self._update_lock_button()
        row_status.set_text(f"Saved as {label}.")
        self.status.set_text(f"Saved as {label}. The others stay unsaved until you save them.")

    def on_copy(self, _button) -> None:
        if not self.current:
            return
        copied = False
        try:
            clipboard = self.gtk.Clipboard.get(self.gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(self.current, len(self.current))
            clipboard.store()
            copied = True
        except Exception:
            copied = False
        if copy_with_xclip(self.current) or generator.copy_with_windows(self.current):
            copied = True
        if copied:
            self.status.set_text("Copied.")
        else:
            self.status.set_text("Copy failed.")

    def _prepare_saved(self) -> None:
        """Leave saved passwords hidden until the passphrase unlocks them."""
        self.vault_key = None
        self.saved = []
        self.showing_saved = False
        self.locked = False
        vault = vault_path()
        plain = saved_passwords_path()
        try:
            if vault.is_symlink() or (plain.is_symlink() and not vault.exists()):
                raise ValueError("The saved password file is a symbolic link.")
            if vault.exists() or (plain.exists() and plain.is_file()):
                self.locked = True
                self.status.set_text("Saved passwords are locked.")
        except ValueError as exc:
            self.locked = True
            self.status.set_text(str(exc))
        self._refresh_saved_rows()
        self._update_lock_button()

    def _refresh_saved_rows(self) -> None:
        for child in list(self.saved_box.get_children()):
            self.saved_box.remove(child)
        query = self.find_entry.get_text().strip().casefold()
        if self.locked and self.vault_key is None:
            self.find_entry.hide()
            self.saved_scroll.hide()
            self.saved_heading.set_text("Saved")
            self.saved_heading.show()
            self.manager_message.set_text(
                "Saved passwords are locked. The passphrase or the recovery key opens all of them. "
                + PASSPHRASE_LOSS_WARNING
            )
            self.manager_message.show()
            return
        self.find_entry.show()
        if not self.saved:
            self.saved_scroll.hide()
            self.saved_heading.set_text("Saved")
            self.saved_heading.show()
            self.manager_message.set_text(
                "Nothing saved yet. Create a password, name it, and save it."
            )
            self.manager_message.show()
            return
        matches = [
            item
            for item in self.saved
            if not query or query in item.name.casefold()
        ]
        count = len(self.saved)
        self.saved_heading.set_text("1 saved" if count == 1 else f"{count} saved")
        self.saved_heading.show()
        if not matches:
            self.saved_scroll.hide()
            self.manager_message.set_text("No saved password has that name.")
            self.manager_message.show()
            return
        self.manager_message.set_text("")
        self.manager_message.hide()
        self.saved_scroll.show()
        for item in matches:
            self.saved_box.pack_start(self._saved_row(item), False, False, 0)
        self.saved_box.show_all()

    def _saved_row(self, item: SavedPassword):
        gtk = self.gtk
        row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        text = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=2)
        name = gtk.Label(label=item.name, xalign=0)
        name.set_halign(gtk.Align.START)
        name.get_style_context().add_class("saved-name")
        secret = gtk.Label(label=item.password, xalign=0)
        secret.set_line_wrap(True)
        secret.set_selectable(True)
        secret.set_halign(gtk.Align.START)
        secret.get_style_context().add_class("hint")
        text.pack_start(name, False, False, 0)
        text.pack_start(secret, False, False, 0)
        text.set_hexpand(True)
        copy = gtk.Button(label="Copy")
        copy.get_style_context().add_class("primary")
        copy.connect("clicked", lambda *_args, password=item.password: self.on_copy_text(password))
        remove = gtk.Button(label="Remove")
        remove.get_style_context().add_class("secondary")
        remove.connect("clicked", lambda *_args, label=item.name: self.on_remove(label))
        row.pack_start(text, True, True, 0)
        row.pack_start(copy, False, False, 0)
        row.pack_start(remove, False, False, 0)
        return row

    def _update_lock_button(self) -> None:
        style = self.lock_button.get_style_context()
        if self.vault_key is not None:
            self.lock_button.set_label("Lock")
            style.remove_class("primary")
            style.add_class("secondary")
            self.lock_button.show()
            return
        if self.locked:
            self.lock_button.set_label("Unlock")
            style.add_class("primary")
            style.remove_class("secondary")
            self.lock_button.show()
            return
        self.lock_button.hide()

    def _prompt_passphrase(self, *, confirm: bool) -> str | None:
        gtk = self.gtk
        dialog = gtk.Dialog(title="Local Password", transient_for=self.window, modal=True)
        self._match_dialog(dialog)
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        dialog.add_button("Continue", gtk.ResponseType.OK)
        dialog.set_default_response(gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(8)
        if confirm:
            message = (
                "Choose a passphrase to lock saved passwords. It is not stored."
            )
        else:
            message = "Enter the passphrase or the recovery key."
        label = gtk.Label(label=message, xalign=0)
        label.set_line_wrap(True)
        label.set_max_width_chars(42)
        content.pack_start(label, False, False, 0)
        if confirm:
            warning = gtk.Label(label=PASSPHRASE_LOSS_WARNING, xalign=0)
            warning.set_line_wrap(True)
            warning.set_max_width_chars(42)
            warning.get_style_context().add_class("danger")
            content.pack_start(warning, False, False, 0)
        entry = gtk.Entry()
        entry.set_visibility(False)
        entry.set_input_purpose(gtk.InputPurpose.PASSWORD)
        entry.set_placeholder_text("Passphrase" if confirm else "Passphrase or recovery key")
        content.pack_start(entry, False, False, 0)
        confirm_entry = None
        if confirm:
            confirm_entry = gtk.Entry()
            confirm_entry.set_visibility(False)
            confirm_entry.set_input_purpose(gtk.InputPurpose.PASSWORD)
            confirm_entry.set_placeholder_text("Repeat the passphrase")
            content.pack_start(confirm_entry, False, False, 0)
        problem = gtk.Label(label="", xalign=0)
        problem.set_line_wrap(True)
        problem.get_style_context().add_class("danger")
        content.pack_start(problem, False, False, 0)
        dialog.show_all()
        entry.grab_focus()
        entry.connect("activate", lambda *_args: dialog.response(gtk.ResponseType.OK))
        while True:
            response = dialog.run()
            if response != gtk.ResponseType.OK:
                dialog.destroy()
                return None
            first = entry.get_text()
            second = confirm_entry.get_text() if confirm_entry is not None else first
            if len(first) < MIN_PASSPHRASE_LENGTH:
                problem.set_text(
                    f"Use at least {MIN_PASSPHRASE_LENGTH} characters for the passphrase."
                )
                continue
            if first != second:
                problem.set_text("Those passphrases do not match.")
                continue
            dialog.destroy()
            return first

    def _confirm_recovery_key(self, recovery_key: str) -> bool:
        """Show the recovery key once. Saving continues only after it is written down."""
        gtk = self.gtk
        dialog = gtk.Dialog(title="Local Password", transient_for=self.window, modal=True)
        self._match_dialog(dialog)
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        continue_button = dialog.add_button("Continue", gtk.ResponseType.OK)
        continue_button.set_sensitive(False)
        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(8)
        label = gtk.Label(
            label=(
                "Write down this recovery key. It opens your saved passwords if you forget the passphrase. "
                "It will not be shown again."
            ),
            xalign=0,
        )
        label.set_line_wrap(True)
        label.set_max_width_chars(42)
        content.pack_start(label, False, False, 0)
        key = gtk.Label(label=recovery_key, xalign=0)
        key.set_line_wrap(True)
        key.set_selectable(True)
        key.set_max_width_chars(42)
        key.get_style_context().add_class("recovery-key")
        content.pack_start(key, False, False, 0)
        copy = gtk.Button(label="Copy recovery key")
        copy.get_style_context().add_class("secondary")
        copy.connect("clicked", lambda *_args: self.on_copy_text(recovery_key))
        content.pack_start(copy, False, False, 0)
        check = gtk.CheckButton(label="I wrote this down")
        check.connect("toggled", lambda widget: continue_button.set_sensitive(widget.get_active()))
        content.pack_start(check, False, False, 0)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        return response == gtk.ResponseType.OK and check.get_active()

    def _ensure_vault_key(self) -> bool:
        if self.vault_key is not None:
            return True
        vault = vault_path()
        plain = saved_passwords_path()
        try:
            if vault.exists():
                phrase = self._prompt_passphrase(confirm=False)
                if phrase is None:
                    self.status.set_text("Not saved. Saved passwords stay locked.")
                    return False
                material, items = open_vault(phrase)
                if not material.recovery_wrap:
                    recovery = new_recovery_key()
                    if self._confirm_recovery_key(recovery):
                        material = new_vault_key(phrase, recovery, n=material.n)
                        write_vault(material, items)
                self.vault_key = material
                self.saved = items
                self.locked = False
                return True
            phrase = self._prompt_passphrase(confirm=True)
            if phrase is None:
                self.status.set_text("Not saved. A passphrase is what locks it.")
                return False
            recovery = new_recovery_key()
            if not self._confirm_recovery_key(recovery):
                self.status.set_text("Not saved. Write down the recovery key to finish.")
                return False
            items = load_saved_passwords(plain) if plain.exists() and plain.is_file() else []
            material = new_vault_key(phrase, recovery)
            write_vault(material, items)
            if plain.exists():
                erase_saved_file(plain)
            self.vault_key = material
            self.saved = items
            self.locked = False
            return True
        except ValueError as exc:
            self.status.set_text(str(exc))
            return False
        except OSError:
            self.status.set_text("Could not lock the saved passwords.")
            return False

    def on_lock_toggle(self, _button) -> None:
        if self.vault_key is not None:
            self._lock_saved()
            return
        if not self._ensure_vault_key():
            self._update_lock_button()
            return
        self.show_section("saved")

    def _lock_saved(self) -> None:
        self.vault_key = None
        self.saved = []
        self.locked = vault_path().exists() or saved_passwords_path().exists()
        self._refresh_saved_rows()
        if self.showing_saved:
            self.current = ""
            self.buffer.set_text("")
            self.copy_button.set_sensitive(False)
            self.strength.set_text("Result")
            self.bits.set_text("Waiting to generate")
            self.meter.set_fraction(0)
            self.showing_saved = False
            self.save_ready = False
            self.save_button.set_sensitive(False)
        self.status.set_text("Saved passwords are locked.")
        self._update_lock_button()

    def on_copy_text(self, text: str) -> None:
        if not text:
            return
        copied = False
        try:
            clipboard = self.gtk.Clipboard.get(self.gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(text, len(text))
            clipboard.store()
            copied = True
        except Exception:
            copied = False
        if copy_with_xclip(text) or generator.copy_with_windows(text):
            copied = True
        message = "Copied." if copied else "Copy failed."
        self.status.set_text(message)
        if self.section == "saved" and self.vault_key is not None:
            self.manager_message.set_text(message)
            self.manager_message.show()

    def on_save(self, _button) -> None:
        if not self.save_ready or not self.current or self.showing_saved:
            self.status.set_text("Generate a password. Name it, then save it.")
            return
        fresh = [line for line in self.current.splitlines() if line]
        try:
            label = clean_name(self.name_entry.get_text())
        except ValueError as exc:
            self.status.set_text(str(exc))
            return
        if not self._ensure_vault_key():
            return
        try:
            updated = remember_named(self.saved, label, fresh)
            write_vault(self.vault_key, updated)
        except ValueError as exc:
            self.status.set_text(str(exc))
            return
        except OSError:
            self.status.set_text("Could not save the password.")
            return
        self.saved = updated
        self.locked = False
        self.find_entry.set_text("")
        self.status.set_text(f"Saved as {label}.")
        self.show_section("saved")
        self.manager_message.set_text(f"Saved as {label}.")
        self.manager_message.show()

    def on_remove(self, name: str) -> None:
        if self.vault_key is None:
            self.status.set_text("Saved passwords are locked.")
            return
        updated = [item for item in self.saved if item.name != name]
        try:
            write_vault(self.vault_key, updated)
        except ValueError as exc:
            self.status.set_text(str(exc))
            return
        except OSError:
            self.status.set_text("Could not remove the saved password.")
            return
        self.saved = updated
        self.showing_saved = False
        self._refresh_saved_rows()
        self.status.set_text("Removed from this computer.")


if __name__ == "__main__":
    main()
