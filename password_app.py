#!/usr/bin/env python3
"""Local window for the password generator.

The password stays in this process until you close the window.
Copy places it on the clipboard. Save keeps it for the next time you open the app.
Send vault opens a port only while another device on the same network is pulling
the encrypted file. The passphrase is not sent.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import math
import os
import re
import secrets
import shutil
import string
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

import random_password_generator as generator
import vault_sync

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
MAX_USERNAME_LENGTH = 200
MAX_URL_LENGTH = 500
MAX_NOTES_LENGTH = 2000
MAX_CATEGORY_LENGTH = 40
KNOWN_ENTRY_KEYS = frozenset(
    {
        "name",
        "password",
        "username",
        "url",
        "notes",
        "category",
        "favorite",
        "archived",
        "created",
        "modified",
        "history",
        "last_used",
    }
)
MAX_PASSWORD_HISTORY = 5
STALE_PASSWORD_DAYS = 180
SAVED_SORT_NAME = "name"
SAVED_SORT_RECENT = "recent"
SAVED_SORT_CHANGED = "changed"
SAVED_SORT_MODES = (SAVED_SORT_NAME, SAVED_SORT_RECENT, SAVED_SORT_CHANGED)
DEFAULT_CLIPBOARD_CLEAR_SECONDS = 30
DEFAULT_AUTO_LOCK_SECONDS = 300
CLIPBOARD_CLEAR_OPTIONS = (
    (0, "Off"),
    (15, "15 seconds"),
    (30, "30 seconds"),
    (60, "1 minute"),
)
AUTO_LOCK_OPTIONS = (
    (0, "Off"),
    (60, "1 minute"),
    (300, "5 minutes"),
    (900, "15 minutes"),
)
APP_VERSION = "1.31.3"
THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_SYSTEM = "system"
THEME_OPTIONS = (THEME_LIGHT, THEME_DARK, THEME_SYSTEM)
DEFAULT_CATEGORIES = (
    "Personal",
    "Work",
    "Banking",
    "Social Media",
    "Shopping",
    "Entertainment",
    "Other",
)
HIBP_RANGE_URL = "https://api.pwnedpasswords.com/range/{prefix}"
HIBP_TIMEOUT_SECONDS = 15.0

STYLES = """
window.app {
  background-color: #F5F4EF;
  color: #202522;
  font-family: "Source Sans 3", "DejaVu Sans", sans-serif;
}
.header-bar {
  background-color: transparent;
}
.brand {
  font-family: "Source Serif 4", "DejaVu Serif", Palatino, serif;
  font-size: 22px;
  font-weight: 700;
  color: #202522;
}
.section-title {
  font-family: "Source Serif 4", "DejaVu Serif", Palatino, serif;
  font-size: 28px;
  font-weight: 700;
  color: #202522;
}
.card {
  background-color: #FFFFFF;
  background-image: none;
  border: 1px solid #E2E4DF;
  border-radius: 12px;
}
.entry-card {
  background-color: #F8F8F5;
  border: 1px solid #E2E4DF;
  border-radius: 10px;
}
.eyebrow {
  color: #08775B;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.2px;
}
.title {
  font-family: "Source Serif 4", "DejaVu Serif", Palatino, serif;
  font-size: 28px;
  font-weight: 700;
}
.lede, .hint, .footer, .caption {
  color: #737B75;
}
.vault-status {
  font-size: 13px;
  font-weight: 600;
  color: #737B75;
}
.vault-status.unlocked {
  color: #08775B;
}
.vault-status.locked {
  color: #A15C12;
}
.stat-value {
  font-family: "Source Serif 4", "DejaVu Serif", Palatino, serif;
  font-size: 32px;
  font-weight: 700;
  color: #202522;
}
.stat-label {
  color: #737B75;
  font-size: 13px;
}
.saved-name {
  font-weight: 700;
  color: #202522;
}
.recovery-key, .pairing-code {
  font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
  font-size: 16px;
  font-weight: 700;
  color: #202522;
}
.pairing-code {
  font-size: 28px;
}
.strength.strong, .strength.very-strong { color: #08775B; font-weight: 700; }
.strength.fair { color: #8A6A12; font-weight: 700; }
.strength.weak, .strength.very-weak { color: #A15C12; font-weight: 700; }
.bits { font-size: 14px; color: #737B75; }
.slab {
  background-color: #1A1F1D;
  border-radius: 10px;
}
.slab text {
  color: #F5F4EF;
  background-color: #1A1F1D;
  font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
  font-size: 16px;
}
button.mode, button.chip, button.primary, button.secondary, button.nav {
  background-image: none;
  box-shadow: none;
  text-shadow: none;
  border-radius: 10px;
  border: 1px solid #E2E4DF;
  padding: 8px 14px;
  font-weight: 600;
}
button.nav {
  padding: 10px 12px;
}
button.mode.off, button.chip.off, button.secondary, button.nav.off {
  background-color: #F8F8F5;
  color: #737B75;
  border-color: #E2E4DF;
}
button.mode.off label, button.chip.off label, button.secondary label, button.nav.off label {
  color: #737B75;
}
button.mode.on, button.chip.on, button.primary, button.nav.on {
  background-color: #08775B;
  color: #ffffff;
  border-color: #08775B;
}
button.mode.on:hover, button.chip.on:hover, button.primary:hover, button.nav.on:hover {
  background-color: #065B46;
  border-color: #065B46;
}
button.mode.on label, button.chip.on label, button.primary label, button.nav.on label {
  color: #ffffff;
}
button.note-danger {
  color: #9C3B3B;
}
.danger { color: #9C3B3B; }
.settings-block {
  border-top: 1px solid #E2E4DF;
  padding-top: 12px;
  margin-top: 4px;
}
progressbar trough {
  min-height: 8px;
  background-color: #E2E4DF;
  border-radius: 999px;
  border: none;
}
progressbar progress {
  background-image: none;
  background-color: #08775B;
  border-radius: 999px;
  border: none;
}
progressbar.weak progress {
  background-color: #A15C12;
}
entry, spinbutton {
  border-radius: 8px;
  border-color: #E2E4DF;
  min-height: 34px;
}
window.app.dark {
  background-color: #141816;
  color: #E8EBE8;
}
window.app.dark .card {
  background-color: #1E2321;
  border-color: #2F3633;
}
window.app.dark .entry-card {
  background-color: #191E1C;
  border-color: #2F3633;
}
window.app.dark .brand,
window.app.dark .section-title,
window.app.dark .title,
window.app.dark .saved-name,
window.app.dark .recovery-key,
window.app.dark .pairing-code,
window.app.dark .stat-value,
window.app.dark .bits {
  color: #E8EBE8;
}
window.app.dark .lede,
window.app.dark .hint,
window.app.dark .footer,
window.app.dark .caption,
window.app.dark .stat-label,
window.app.dark .vault-status {
  color: #9AA39D;
}
window.app.dark .eyebrow,
window.app.dark .strength.strong,
window.app.dark .strength.very-strong,
window.app.dark .vault-status.unlocked {
  color: #5FBF9A;
}
window.app.dark .strength.fair {
  color: #D0B15A;
}
window.app.dark .strength.weak,
window.app.dark .strength.very-weak,
window.app.dark .danger,
window.app.dark button.note-danger,
window.app.dark .vault-status.locked {
  color: #E0A070;
}
window.app.dark button.mode.off,
window.app.dark button.chip.off,
window.app.dark button.secondary,
window.app.dark button.nav.off {
  background-color: #252B28;
  color: #9AA39D;
  border-color: #2F3633;
}
window.app.dark button.mode.off label,
window.app.dark button.chip.off label,
window.app.dark button.secondary label,
window.app.dark button.nav.off label {
  color: #9AA39D;
}
window.app.dark button.mode.on,
window.app.dark button.chip.on,
window.app.dark button.primary,
window.app.dark button.nav.on {
  background-color: #08775B;
  border-color: #08775B;
}
window.app.dark .settings-block {
  border-top-color: #2F3633;
}
window.app.dark entry {
  background-color: #141816;
  color: #E8EBE8;
  border-color: #2F3633;
}
window.app.dark entry selection {
  background-color: #08775B;
  color: #ffffff;
}
window.app.dark progressbar trough {
  background-color: #2F3633;
}
window.app.dark textview {
  background-color: #141816;
  color: #E8EBE8;
}
window.app.dark textview text {
  background-color: #141816;
  color: #E8EBE8;
}
window.app.dark .slab,
window.app.dark .slab text {
  background-color: #0C0F0E;
  color: #E8EBE8;
}
window.app.dark spinbutton,
window.app.dark spinbutton entry {
  background-color: #141816;
  color: #E8EBE8;
}
window.app.dark spinbutton button {
  background-image: none;
  background-color: #252B28;
  color: #E8EBE8;
  border-color: #2F3633;
}
window.app.dark spinbutton button label {
  color: #E8EBE8;
}
window.app.dark scrollbar trough {
  background-color: #1A1F1D;
}
window.app.dark scrollbar slider {
  background-color: #3A433F;
}
window.app.dark checkbutton label {
  color: #E8EBE8;
}
window.app.dark progressbar.weak progress {
  background-color: #C9843A;
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


def character_pool(
    *,
    digits: bool = False,
    uppercase: bool = False,
    lowercase: bool = False,
    symbols: bool = False,
    exclude_ambiguous: bool = False,
    exclude: str = "",
    letters: bool | None = None,
) -> str:
    """Build the alphabet. Symbols include quotes, backticks, and backslashes.

    ``letters=True`` turns on both uppercase and lowercase for older callers.
    """
    digits = _flag(digits, "Digits")
    symbols = _flag(symbols, "Symbols")
    exclude_ambiguous = _flag(exclude_ambiguous, "Exclude ambiguous")
    exclude = generator.clean_exclude_characters(exclude)
    if letters is not None:
        letters = _flag(letters, "Letters")
        uppercase = letters
        lowercase = letters
    else:
        uppercase = _flag(uppercase, "Uppercase")
        lowercase = _flag(lowercase, "Lowercase")
    if not (digits or uppercase or lowercase or symbols):
        raise ValueError("Choose at least one character type.")
    parts: list[str] = []
    if digits:
        parts.append(string.digits)
    if uppercase:
        parts.append(string.ascii_uppercase)
    if lowercase:
        parts.append(string.ascii_lowercase)
    if symbols:
        parts.append(generator.special_characters(all_special=True))
    return generator.prepare_character_list(
        "".join(parts),
        exclude_ambiguous=exclude_ambiguous,
        exclude=exclude,
    )


def generate(
    *,
    mode: str,
    length: int,
    words: int,
    count: int,
    digits: bool = True,
    uppercase: bool = True,
    lowercase: bool = True,
    symbols: bool = True,
    exclude_ambiguous: bool = False,
    exclude: str = "",
    letters: bool | None = None,
    separator: str = " ",
    capitalize: bool = False,
) -> Generated:
    """Generate passwords in memory. This function does not write a file."""
    count = _count(count)
    if mode == "passphrase":
        word_count = generator.require_word_count(words)
        wordlist = generator.load_wordlist()
        separator = generator.require_separator(separator)
        capitalize = _flag(capitalize, "Capitalize")
        passwords = [
            generator.generate_passphrase(
                word_count,
                wordlist=wordlist,
                separator=separator,
                capitalize=capitalize,
            )
            for _ in range(count)
        ]
        exact = generator.passphrase_entropy_bits(word_count, len(wordlist))
        note = (
            "Word passphrases are easier to type than random characters of similar strength. "
            "Capital letters and a fixed separator do not add search-space bits."
        )
        if exact < generator.STRONG_ENTROPY_BITS:
            note = (
                f"These options stay under {generator.STRONG_ENTROPY_BITS} bits. "
                "Add words to reach a strong passphrase."
            )
    elif mode == "characters":
        exclude = generator.clean_exclude_characters(exclude)
        pool = character_pool(
            digits=digits,
            uppercase=uppercase,
            lowercase=lowercase,
            symbols=symbols,
            exclude_ambiguous=exclude_ambiguous,
            exclude=exclude,
            letters=letters,
        )
        length = generator.require_password_length(length)
        passwords = [generator.generate_password(length, pool) for _ in range(count)]
        exact = generator.password_entropy_bits(length, len(generator.unique_characters(pool)))
        note = "" if generator.can_be_strong(length, pool) else generator.strong_line_message()
        extras: list[str] = []
        if exclude_ambiguous:
            extras.append("ambiguous characters (0, O, o, 1, l, I, |)")
        if exclude:
            extras.append(f"extra characters ({exclude})")
        if extras and note == "":
            note = "Left out " + " and ".join(extras) + "."
    else:
        raise ValueError("Mode must be characters or passphrase.")

    bits = round(exact)
    each = "" if count == 1 else " each"
    return Generated(
        text="\n".join(passwords),
        label=generator.strength_tier(exact),
        bits_label=f"about {bits} bits{each}",
        fraction=min(exact / METER_CAP_BITS, 1.0),
        note=note,
    )


@dataclass(frozen=True)
class PasswordRevision:
    """One previous password kept after a replace or edit."""

    password: str
    replaced_at: str = ""


@dataclass(frozen=True)
class SavedPassword:
    name: str
    password: str
    username: str = ""
    url: str = ""
    notes: str = ""
    category: str = ""
    favorite: bool = False
    archived: bool = False
    created: str = ""
    modified: str = ""
    last_used: str = ""
    history: tuple[PasswordRevision, ...] = ()
    extras: dict[str, object] = field(default_factory=dict)


def utc_now() -> str:
    """UTC timestamp for created/modified fields."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_username(value: str) -> str:
    text = value.strip()
    if len(text) > MAX_USERNAME_LENGTH:
        raise ValueError(f"The username must be {MAX_USERNAME_LENGTH} characters or fewer.")
    return text


def clean_url(value: str) -> str:
    text = value.strip()
    if len(text) > MAX_URL_LENGTH:
        raise ValueError(f"The URL must be {MAX_URL_LENGTH} characters or fewer.")
    return text


def clean_notes(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) > MAX_NOTES_LENGTH:
        raise ValueError(f"Notes must be {MAX_NOTES_LENGTH} characters or fewer.")
    return text


def clean_category(value: str) -> str:
    text = " ".join(value.strip().split())
    if len(text) > MAX_CATEGORY_LENGTH:
        raise ValueError(f"The category must be {MAX_CATEGORY_LENGTH} characters or fewer.")
    return text


def entry_matches(item: SavedPassword, query: str) -> bool:
    """True when the search text hits name, username, URL, notes, or category."""
    needle = query.strip().casefold()
    if not needle:
        return True
    haystacks = (
        item.name,
        item.username,
        item.url,
        item.notes,
        item.category,
    )
    return any(needle in value.casefold() for value in haystacks if value)


def sorted_saved_entries(
    items: list[SavedPassword],
    mode: str,
    *,
    all_items: list[SavedPassword] | None = None,
    breach_counts: dict[str, int] | None = None,
) -> list[SavedPassword]:
    """Order Saved rows by name, last used, or last changed."""
    pool = all_items if all_items is not None else items
    sort_mode = mode if mode in SAVED_SORT_MODES else SAVED_SORT_NAME
    if sort_mode == SAVED_SORT_RECENT:
        used = [item for item in items if item.last_used]
        unused = [item for item in items if not item.last_used]
        used.sort(key=lambda item: (item.last_used, item.name.casefold()), reverse=True)
        unused.sort(key=lambda item: item.name.casefold())
        return used + unused
    if sort_mode == SAVED_SORT_CHANGED:
        stamped = [item for item in items if item.modified]
        plain = [item for item in items if not item.modified]
        stamped.sort(key=lambda item: (item.modified, item.name.casefold()), reverse=True)
        plain.sort(key=lambda item: item.name.casefold())
        return stamped + plain
    return sorted(
        items,
        key=lambda item: (
            not entry_needs_attention(item, pool, breach_counts=breach_counts),
            not item.favorite,
            item.name.casefold(),
        ),
    )


def touch_last_used(
    existing: list[SavedPassword],
    item: SavedPassword,
    *,
    when: str | None = None,
) -> list[SavedPassword]:
    """Stamp last_used without changing the password or modified time."""
    stamp = when or utc_now()
    updated = replace(item, last_used=stamp)
    return [updated if entry.name == item.name else entry for entry in existing]


def stamp_date(stamp: str) -> str:
    """Return YYYY-MM-DD from an ISO timestamp, or empty when missing."""
    text = stamp.strip()
    if len(text) < 10:
        return ""
    return text[:10]


def last_used_label(item: SavedPassword) -> str:
    """Short Saved-row / Dashboard line for when the entry was last copied."""
    day = stamp_date(item.last_used)
    if day:
        return f"Last used {day}"
    return "Not used yet"


def entry_dates_label(item: SavedPassword) -> str:
    """Short Saved-row / Dashboard line for created and last-changed dates."""
    bits: list[str] = []
    created = stamp_date(item.created)
    changed = stamp_date(item.modified)
    if created:
        bits.append(f"Created {created}")
    if changed:
        bits.append(f"Changed {changed}")
    return " · ".join(bits)


def recently_used_entries(items: list[SavedPassword], limit: int = 5) -> list[SavedPassword]:
    """Top entries for the Dashboard: last used first, else last changed."""
    items = active_saved_entries(items)
    if limit <= 0:
        return []
    used = [item for item in items if item.last_used]
    if used:
        used.sort(key=lambda item: (item.last_used, item.name.casefold()), reverse=True)
        return used[:limit]
    stamped = [item for item in items if item.modified]
    plain = [item for item in items if not item.modified]
    stamped.sort(key=lambda item: (item.modified, item.name.casefold()), reverse=True)
    plain.sort(key=lambda item: item.name.casefold())
    return (stamped + plain)[:limit]


def set_entry_favorite(
    existing: list[SavedPassword],
    item: SavedPassword,
    favorite: bool,
) -> list[SavedPassword]:
    """Mark or clear Favorite without changing the password or timestamps."""
    updated = replace(item, favorite=bool(favorite))
    return [updated if entry.name == item.name else entry for entry in existing]


def toggle_entry_favorite(
    existing: list[SavedPassword],
    item: SavedPassword,
) -> list[SavedPassword]:
    """Flip Favorite on one entry without changing the password or timestamps."""
    return set_entry_favorite(existing, item, not item.favorite)


def active_saved_entries(items: list[SavedPassword]) -> list[SavedPassword]:
    """Entries that are not archived."""
    return [item for item in items if not item.archived]


def set_entry_archived(
    existing: list[SavedPassword],
    item: SavedPassword,
    archived: bool,
) -> list[SavedPassword]:
    """Archive or unarchive without changing the password or timestamps."""
    updated = replace(item, archived=bool(archived))
    return [updated if entry.name == item.name else entry for entry in existing]


def toggle_entry_archived(
    existing: list[SavedPassword],
    item: SavedPassword,
) -> list[SavedPassword]:
    """Flip Archive on one entry without changing the password or timestamps."""
    return set_entry_archived(existing, item, not item.archived)


def duplicate_entry(
    existing: list[SavedPassword],
    item: SavedPassword,
    *,
    when: str | None = None,
) -> list[SavedPassword]:
    """Copy a saved entry under a new name. History and last-used stay on the original."""
    taken = {entry.name: index for index, entry in enumerate(existing)}
    if item.name not in taken:
        raise ValueError("That saved password is gone.")
    stamp = when or utc_now()
    label = _unique_entry_name(item.name, taken, " (copy)")
    fresh = SavedPassword(
        label,
        item.password,
        username=item.username,
        url=item.url,
        notes=item.notes,
        category=item.category,
        favorite=item.favorite,
        archived=False,
        created=stamp,
        modified=stamp,
        last_used="",
        history=(),
        extras=dict(item.extras),
    )
    return [fresh] + list(existing)


def rename_entry(
    existing: list[SavedPassword],
    item: SavedPassword,
    new_name: str,
    *,
    when: str | None = None,
) -> list[SavedPassword]:
    """Rename one saved entry. Refuses a name already used by another row."""
    taken = {entry.name for entry in existing}
    if item.name not in taken:
        raise ValueError("That saved password is gone.")
    label = clean_name(new_name)
    if label == item.name:
        return list(existing)
    if label in taken:
        raise ValueError("Another saved password already uses that name.")
    stamp = when or utc_now()
    renamed = replace(item, name=label, modified=stamp)
    return [renamed] + [entry for entry in existing if entry.name != item.name]


def set_entry_category(
    existing: list[SavedPassword],
    item: SavedPassword,
    category: str,
    *,
    when: str | None = None,
) -> list[SavedPassword]:
    """Set or clear category on one entry without opening Edit."""
    if all(entry.name != item.name for entry in existing):
        raise ValueError("That saved password is gone.")
    label = clean_category(category)
    if label == item.category:
        return list(existing)
    stamp = when or utc_now()
    updated = replace(item, category=label, modified=stamp)
    return [updated if entry.name == item.name else entry for entry in existing]


def set_entry_username(
    existing: list[SavedPassword],
    item: SavedPassword,
    username: str,
    *,
    when: str | None = None,
) -> list[SavedPassword]:
    """Set or clear username on one entry without opening Edit."""
    if all(entry.name != item.name for entry in existing):
        raise ValueError("That saved password is gone.")
    label = clean_username(username)
    if label == item.username:
        return list(existing)
    stamp = when or utc_now()
    updated = replace(item, username=label, modified=stamp)
    return [updated if entry.name == item.name else entry for entry in existing]


def set_entry_url(
    existing: list[SavedPassword],
    item: SavedPassword,
    url: str,
    *,
    when: str | None = None,
) -> list[SavedPassword]:
    """Set or clear website URL on one entry without opening Edit."""
    if all(entry.name != item.name for entry in existing):
        raise ValueError("That saved password is gone.")
    label = clean_url(url)
    if label == item.url:
        return list(existing)
    stamp = when or utc_now()
    updated = replace(item, url=label, modified=stamp)
    return [updated if entry.name == item.name else entry for entry in existing]


def set_entry_notes(
    existing: list[SavedPassword],
    item: SavedPassword,
    notes: str,
    *,
    when: str | None = None,
) -> list[SavedPassword]:
    """Set or clear notes on one entry without opening Edit."""
    if all(entry.name != item.name for entry in existing):
        raise ValueError("That saved password is gone.")
    label = clean_notes(notes)
    if label == item.notes:
        return list(existing)
    stamp = when or utc_now()
    updated = replace(item, notes=label, modified=stamp)
    return [updated if entry.name == item.name else entry for entry in existing]


def remove_entry(existing: list[SavedPassword], item: SavedPassword) -> list[SavedPassword]:
    """Drop one saved entry by name."""
    if all(entry.name != item.name for entry in existing):
        raise ValueError("That saved password is gone.")
    return [entry for entry in existing if entry.name != item.name]


def restore_removed_entry(
    existing: list[SavedPassword],
    item: SavedPassword,
) -> list[SavedPassword]:
    """Put a removed entry back. If the name is taken, keep a unique restored name."""
    taken = {entry.name: index for index, entry in enumerate(existing)}
    if item.name in taken:
        label = _unique_entry_name(item.name, taken, " (restored)")
        item = replace(item, name=label)
    return [item] + list(existing)


def reused_password_groups(items: list[SavedPassword]) -> dict[str, list[str]]:
    """Map a password to the entry names that share it, only when reused."""
    groups: dict[str, list[str]] = {}
    for item in items:
        groups.setdefault(item.password, []).append(item.name)
    return {password: names for password, names in groups.items() if len(names) > 1}


def reuse_warning_for(item: SavedPassword, items: list[SavedPassword]) -> str:
    """Short note when this entry's password is also used elsewhere."""
    names = reused_password_groups(items).get(item.password)
    if not names:
        return ""
    others = [name for name in names if name != item.name]
    if not others:
        return ""
    if len(others) == 1:
        return f"Same password as {others[0]}."
    if len(others) == 2:
        return f"Same password as {others[0]} and {others[1]}."
    return f"Same password as {len(others)} other saved entries."


def browseable_url(url: str) -> str | None:
    """Return an http(s) URL to open, or None when the value is empty or unsafe."""
    text = url.strip()
    if not text:
        return None
    lowered = text.casefold()
    if lowered.startswith("https://") or lowered.startswith("http://"):
        return text
    # Reject other schemes (javascript:, file:, data:). Allow host:port.
    if re.match(r"^[a-z][a-z0-9+.-]*:(?!\d)", lowered):
        return None
    return "https://" + text


def login_copy_text(item: SavedPassword) -> str:
    """Username and password joined with a tab for one clipboard paste, or empty."""
    user = item.username.strip()
    if not user:
        return ""
    return f"{user}\t{item.password}"


def optional_copy_fields(item: SavedPassword) -> list[tuple[str, str]]:
    """Copy URL and Copy notes labels with values when those fields are set."""
    fields: list[tuple[str, str]] = []
    url = item.url.strip()
    if url:
        fields.append(("Copy URL", url))
    notes = item.notes.strip()
    if notes:
        fields.append(("Copy notes", item.notes))
    return fields


def open_entry_url(url: str) -> bool:
    """Open a saved entry URL in the default browser."""
    target = browseable_url(url)
    if target is None:
        return False
    return bool(webbrowser.open(target))


def entry_strength_bits(password: str) -> float:
    """Estimate search-space bits for a saved password from its character classes."""
    return generator.password_strength_bits(password)


def entry_is_weak(password: str) -> bool:
    """True when the estimate stays under the strong line (about 75 bits)."""
    return not generator.is_strong_password(password)


def strength_warning_for(item: SavedPassword) -> str:
    """Short note when this entry's password is under the strong line."""
    if not entry_is_weak(item.password):
        return ""
    bits = entry_strength_bits(item.password)
    tier = generator.strength_tier(bits)
    return f"{tier} password (about {round(bits)} bits)."


def weak_password_names(items: list[SavedPassword]) -> list[str]:
    """Names of entries whose passwords stay under the strong line."""
    return [item.name for item in items if entry_is_weak(item.password)]


def _parse_stamp_day(stamp: str) -> date | None:
    """Parse YYYY-MM-DD from an ISO stamp, or None when missing or invalid."""
    day = stamp_date(stamp)
    if not day:
        return None
    try:
        return date.fromisoformat(day)
    except ValueError:
        return None


def entry_changed_day(item: SavedPassword) -> date | None:
    """Day the password was last changed, falling back to created."""
    return _parse_stamp_day(item.modified) or _parse_stamp_day(item.created)


def entry_is_stale(
    item: SavedPassword,
    *,
    days: int = STALE_PASSWORD_DAYS,
    today: date | None = None,
) -> bool:
    """True when the password has not been changed for at least `days`."""
    changed = entry_changed_day(item)
    if changed is None:
        return False
    ref = today or _parse_stamp_day(utc_now()) or date.today()
    return (ref - changed).days >= days


def stale_warning_for(
    item: SavedPassword,
    *,
    days: int = STALE_PASSWORD_DAYS,
    today: date | None = None,
) -> str:
    """Short note when this entry's password has not been changed recently."""
    if not entry_is_stale(item, days=days, today=today):
        return ""
    day = stamp_date(item.modified) or stamp_date(item.created)
    return f"Not changed since {day}."


def stale_password_names(
    items: list[SavedPassword],
    *,
    days: int = STALE_PASSWORD_DAYS,
    today: date | None = None,
) -> list[str]:
    """Names of entries whose passwords are older than the stale window."""
    return [item.name for item in items if entry_is_stale(item, days=days, today=today)]


def entry_needs_attention(
    item: SavedPassword,
    items: list[SavedPassword],
    *,
    today: date | None = None,
    breach_counts: dict[str, int] | None = None,
) -> bool:
    """True when the password is weak, reused, stale, or known-breached this session."""
    if breach_counts and breach_counts.get(password_sha1_hex(item.password), 0) > 0:
        return True
    return (
        entry_is_weak(item.password)
        or bool(reuse_warning_for(item, items))
        or entry_is_stale(item, today=today)
    )


def password_health_summary(
    items: list[SavedPassword],
    *,
    today: date | None = None,
    breach_counts: dict[str, int] | None = None,
) -> tuple[int, int, int, int, int]:
    """Return (weak, reuse, stale, breached, attention) counts for active entries.

    Archived entries are ignored so they do not keep Needs attention lit.
    Breached counts use session results from an optional HIBP check.
    """
    active = active_saved_entries(items)
    weak_count = len(weak_password_names(active))
    reuse_count = len(reused_password_groups(active))
    stale_count = len(stale_password_names(active, today=today))
    breached_count = 0
    if breach_counts:
        breached_count = sum(
            1
            for item in active
            if breach_counts.get(password_sha1_hex(item.password), 0) > 0
        )
    attention_count = sum(
        1
        for item in active
        if entry_needs_attention(item, active, today=today, breach_counts=breach_counts)
    )
    return weak_count, reuse_count, stale_count, breached_count, attention_count


def password_sha1_hex(password: str) -> str:
    """SHA-1 hex digest used only for HIBP k-anonymity range lookups."""
    return hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()


def match_hibp_range(body: str, suffix: str) -> int:
    """Return breach count for a SHA-1 suffix in an HIBP range response, or 0."""
    want = suffix.strip().upper()
    for raw in body.splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        found, count_text = line.split(":", 1)
        if found.strip().upper() != want:
            continue
        try:
            return max(0, int(count_text.strip()))
        except ValueError:
            return 1
    return 0


def fetch_hibp_range(prefix: str, *, timeout: float = HIBP_TIMEOUT_SECONDS) -> str:
    """Fetch one HIBP password-hash range. Only a 5-character prefix is requested."""
    clean = prefix.strip().upper()
    if len(clean) != 5 or any(ch not in "0123456789ABCDEF" for ch in clean):
        raise ValueError("The hash prefix for a breach check is invalid.")
    url = HIBP_RANGE_URL.format(prefix=clean)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"LocalPassword/{APP_VERSION}",
            "Add-Padding": "true",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Breach list request failed ({exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise ValueError("Could not reach the breach list. Check the network and try again.") from exc
    except TimeoutError as exc:
        raise ValueError("The breach list timed out. Try again.") from exc


def check_password_pwned(
    password: str,
    *,
    fetch_range=fetch_hibp_range,
) -> int:
    """How many times this password appears in known breaches (0 means clear).

    Uses Have I Been Pwned k-anonymity: only the first five characters of the
    SHA-1 hash leave this computer. The password and full hash never do.
    """
    digest = password_sha1_hex(password)
    return match_hibp_range(fetch_range(digest[:5]), digest[5:])


def check_passwords_pwned(
    passwords: list[str],
    *,
    fetch_range=fetch_hibp_range,
) -> dict[str, int]:
    """Map password SHA-1 hex → breach count for each distinct password."""
    counts: dict[str, int] = {}
    unique: dict[str, str] = {}
    for password in passwords:
        digest = password_sha1_hex(password)
        unique.setdefault(digest, password)
    # One range request per distinct prefix, then match each suffix locally.
    by_prefix: dict[str, list[str]] = {}
    for digest in unique:
        by_prefix.setdefault(digest[:5], []).append(digest)
    for prefix, digests in by_prefix.items():
        body = fetch_range(prefix)
        for digest in digests:
            counts[digest] = match_hibp_range(body, digest[5:])
    return counts


def breach_warning_for(count: int) -> str:
    """Short note when a password was found in known breaches."""
    if count <= 0:
        return ""
    if count == 1:
        return "Found in 1 known breach. Replace it."
    return f"Found in {count:,} known breaches. Replace it."


def strong_replacement_password() -> str:
    """One strong character password for replacing a saved entry."""
    pool = character_pool(digits=True, uppercase=True, lowercase=True, symbols=True)
    unique = generator.unique_characters(pool)
    length = max(
        16,
        math.ceil(generator.STRONG_ENTROPY_BITS / math.log2(len(unique))),
    )
    length = min(length, generator.MAX_PASSWORD_LENGTH)
    return generator.generate_password(length, pool)


def _history_after_change(
    old_password: str,
    history: tuple[PasswordRevision, ...],
    *,
    replaced_at: str | None = None,
) -> tuple[PasswordRevision, ...]:
    """Push the old password onto history, newest first, capped."""
    secret = _password_line(old_password)
    when = replaced_at or utc_now()
    revisions: list[PasswordRevision] = [PasswordRevision(secret, when)]
    for item in history:
        try:
            previous = _password_line(item.password)
        except ValueError:
            continue
        if previous == secret:
            continue
        if any(previous == kept.password for kept in revisions):
            continue
        revisions.append(PasswordRevision(previous, item.replaced_at))
        if len(revisions) >= MAX_PASSWORD_HISTORY:
            break
    return tuple(revisions[:MAX_PASSWORD_HISTORY])


def with_changed_password(item: SavedPassword, new_password: str) -> SavedPassword:
    """Swap the password and keep the old one in history."""
    secret = _password_line(new_password)
    if secret == item.password:
        return item
    return replace(
        item,
        password=secret,
        modified=utc_now(),
        history=_history_after_change(item.password, item.history),
    )


def replace_entry_password(
    existing: list[SavedPassword],
    item: SavedPassword,
    new_password: str,
) -> list[SavedPassword]:
    """Keep the entry fields, swap the password, and remember the previous one."""
    return upsert_entry(existing, with_changed_password(item, new_password), previous_name=item.name)


def restore_entry_password(
    existing: list[SavedPassword],
    item: SavedPassword,
    index: int,
) -> list[SavedPassword]:
    """Put a previous password back and keep the current one in history."""
    if index < 0 or index >= len(item.history):
        raise ValueError("That previous password is gone.")
    revision = item.history[index]
    secret = _password_line(revision.password)
    if secret == item.password:
        raise ValueError("That is already the current password.")
    stamped = with_changed_password(item, secret)
    # Drop the restored revision from history so it is not listed twice.
    trimmed = tuple(
        entry
        for entry in stamped.history
        if entry.password != secret
    )
    stamped = replace(stamped, history=trimmed)
    return upsert_entry(existing, stamped, previous_name=item.name)


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
    """This computer's light, dark, or system theme choice. It holds no passwords."""
    return data_directory() / "local-password" / "appearance"


def onboarding_path() -> Path:
    """Marks that the short first-run tour was finished or skipped."""
    return data_directory() / "local-password" / "onboarding"


def load_onboarding_done(path: Path | None = None) -> bool:
    path = onboarding_path() if path is None else path
    if path.is_symlink() or not path.is_file():
        return False
    return path.read_text(encoding="utf-8").strip().casefold() == "done"


def store_onboarding_done(path: Path | None = None) -> None:
    path = onboarding_path() if path is None else path
    if path.is_symlink():
        raise ValueError("The onboarding file is a link.")
    directory = path.parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, b"done\n")
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600)


def system_prefers_dark() -> bool:
    """Best-effort read of the desktop or Windows app theme."""
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(value) == 0
        except Exception:
            return False
    try:
        scheme = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1,
        )
        if scheme.returncode == 0 and "dark" in scheme.stdout.casefold():
            return True
        theme = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1,
        )
        if theme.returncode == 0 and "dark" in theme.stdout.casefold():
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    return False


def load_appearance_mode(path: Path | None = None) -> str:
    path = appearance_path() if path is None else path
    if path.is_symlink() or not path.is_file():
        return THEME_LIGHT
    text = path.read_text(encoding="utf-8").strip().casefold()
    if text in THEME_OPTIONS:
        return text
    return THEME_LIGHT


def resolve_dark_mode(mode: str | None = None) -> bool:
    chosen = load_appearance_mode() if mode is None else mode
    if chosen == THEME_DARK:
        return True
    if chosen == THEME_SYSTEM:
        return system_prefers_dark()
    return False


def load_dark_mode(path: Path | None = None) -> bool:
    """True when the resolved theme is dark. Kept for older call sites and tests."""
    return resolve_dark_mode(load_appearance_mode(path))


def store_appearance_mode(mode: str, path: Path | None = None) -> None:
    """Remember light, dark, or system on this computer. The file holds no passwords."""
    chosen = mode.casefold().strip()
    if chosen not in THEME_OPTIONS:
        raise ValueError("Choose light, dark, or system.")
    path = appearance_path() if path is None else path
    if path.is_symlink():
        raise ValueError("The appearance file is a link.")
    directory = path.parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    payload = f"{chosen}\n".encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, payload)
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600)


def store_appearance(dark: bool, path: Path | None = None) -> None:
    """Remember Dark on this computer. The file is readable only by this user."""
    store_appearance_mode(THEME_DARK if dark else THEME_LIGHT, path=path)


@dataclass(frozen=True)
class Preferences:
    """Security choices that stay on this computer. They hold no passwords."""

    clipboard_clear_seconds: int = DEFAULT_CLIPBOARD_CLEAR_SECONDS
    auto_lock_seconds: int = DEFAULT_AUTO_LOCK_SECONDS
    confirm_before_reveal: bool = False
    lock_on_open: bool = False


def preferences_path() -> Path:
    return data_directory() / "local-password" / "preferences"


def _normalize_choice(value: int, options: tuple[tuple[int, str], ...], default: int) -> int:
    allowed = {item[0] for item in options}
    return value if value in allowed else default


def _preference_flag(text: str) -> bool:
    return text.casefold() in ("1", "true", "yes", "on")


def load_preferences(path: Path | None = None) -> Preferences:
    path = preferences_path() if path is None else path
    if path.is_symlink() or not path.is_file():
        return Preferences()
    clipboard = DEFAULT_CLIPBOARD_CLEAR_SECONDS
    auto_lock = DEFAULT_AUTO_LOCK_SECONDS
    confirm_reveal = False
    lock_on_open = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, text = line.split("=", 1)
        key = key.strip()
        text = text.strip()
        if key == "confirm_before_reveal":
            confirm_reveal = _preference_flag(text)
            continue
        if key == "lock_on_open":
            lock_on_open = _preference_flag(text)
            continue
        try:
            number = int(text)
        except ValueError:
            continue
        if key == "clipboard_clear_seconds":
            clipboard = number
        elif key == "auto_lock_seconds":
            auto_lock = number
    return Preferences(
        clipboard_clear_seconds=_normalize_choice(
            clipboard, CLIPBOARD_CLEAR_OPTIONS, DEFAULT_CLIPBOARD_CLEAR_SECONDS
        ),
        auto_lock_seconds=_normalize_choice(
            auto_lock, AUTO_LOCK_OPTIONS, DEFAULT_AUTO_LOCK_SECONDS
        ),
        confirm_before_reveal=confirm_reveal,
        lock_on_open=lock_on_open,
    )


def store_preferences(prefs: Preferences, path: Path | None = None) -> None:
    """Remember clipboard, auto-lock, and security toggles. Holds no passwords."""
    path = preferences_path() if path is None else path
    if path.is_symlink():
        raise ValueError("The preferences file is a link.")
    directory = path.parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    payload = (
        f"clipboard_clear_seconds={prefs.clipboard_clear_seconds}\n"
        f"auto_lock_seconds={prefs.auto_lock_seconds}\n"
        f"confirm_before_reveal={'1' if prefs.confirm_before_reveal else '0'}\n"
        f"lock_on_open={'1' if prefs.lock_on_open else '0'}\n"
    ).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, payload)
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600)


def category_choices(existing: list[SavedPassword] | None = None) -> list[str]:
    """Default categories plus any custom labels already in the vault."""
    labels = list(DEFAULT_CATEGORIES)
    if existing:
        for item in existing:
            if item.category and item.category not in labels:
                labels.append(item.category)
    return labels


def is_vault_blob(blob: bytes) -> bool:
    return len(blob) >= 48 and blob.startswith((VAULT_MAGIC, VAULT_MAGIC_V2))


def read_vault_blob(path: Path | None = None) -> bytes:
    path = vault_path() if path is None else path
    if path.is_symlink():
        raise ValueError("The saved password file is a symbolic link.")
    if not path.is_file():
        raise ValueError("There is no vault on this computer yet.")
    blob = path.read_bytes()
    if not is_vault_blob(blob):
        raise ValueError("The saved password file is damaged.")
    return blob


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
    now = utc_now()
    by_name = {item.name: item for item in existing}

    def _fresh(entry_name: str, password: str) -> SavedPassword:
        previous = by_name.get(entry_name)
        secret = _password_line(password)
        if previous is None:
            return SavedPassword(entry_name, secret, created=now, modified=now)
        base = SavedPassword(
            entry_name,
            previous.password,
            username=previous.username,
            url=previous.url,
            notes=previous.notes,
            category=previous.category,
            favorite=previous.favorite,
            archived=previous.archived,
            created=previous.created if previous.created else now,
            modified=now,
            last_used=previous.last_used,
            history=previous.history,
            extras=dict(previous.extras),
        )
        if secret == previous.password:
            return base
        return with_changed_password(base, secret)

    if len(passwords) == 1:
        fresh = [_fresh(label, passwords[0])]
    else:
        extra = len(str(len(passwords))) + 1
        if len(label) + extra > MAX_NAME_LENGTH:
            raise ValueError(f"The name must be {MAX_NAME_LENGTH - extra} characters or fewer for this many passwords.")
        fresh = [
            _fresh(f"{label} {index}", password)
            for index, password in enumerate(passwords, start=1)
        ]
    replaced = {item.name for item in fresh}
    replaced.add(label)
    kept = [item for item in existing if item.name not in replaced]
    return fresh + kept


def upsert_entry(existing: list[SavedPassword], item: SavedPassword, *, previous_name: str | None = None) -> list[SavedPassword]:
    """Insert or replace one vault entry. Renames drop the old name."""
    label = clean_name(item.name)
    now = utc_now()
    drop = {label}
    if previous_name:
        drop.add(clean_name(previous_name))
    prior = next((entry for entry in existing if entry.name in drop), None)
    stamped = replace(
        item,
        name=label,
        password=_password_line(item.password),
        username=clean_username(item.username),
        url=clean_url(item.url),
        notes=clean_notes(item.notes),
        category=clean_category(item.category),
        created=prior.created if prior and prior.created else (item.created or now),
        modified=now,
        last_used=item.last_used or (prior.last_used if prior else ""),
        history=tuple(item.history),
        extras=dict(item.extras),
    )
    kept = [entry for entry in existing if entry.name not in drop]
    return [stamped] + kept


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


def _entry_to_json(item: SavedPassword) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": clean_name(item.name),
        "password": _password_line(item.password),
    }
    if item.username:
        payload["username"] = clean_username(item.username)
    if item.url:
        payload["url"] = clean_url(item.url)
    if item.notes:
        payload["notes"] = clean_notes(item.notes)
    if item.category:
        payload["category"] = clean_category(item.category)
    if item.favorite:
        payload["favorite"] = True
    if item.archived:
        payload["archived"] = True
    if item.created:
        payload["created"] = item.created
    if item.modified:
        payload["modified"] = item.modified
    if item.last_used:
        payload["last_used"] = item.last_used
    if item.history:
        payload["history"] = [
            (
                {"password": revision.password, "replaced_at": revision.replaced_at}
                if revision.replaced_at
                else {"password": revision.password}
            )
            for revision in item.history
        ]
    for key, value in item.extras.items():
        if key not in KNOWN_ENTRY_KEYS:
            payload[key] = value
    return payload


def _history_from_json(value: object) -> tuple[PasswordRevision, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("The saved password file is damaged.")
    revisions: list[PasswordRevision] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError("The saved password file is damaged.")
        password = entry.get("password")
        replaced_at = entry.get("replaced_at", "")
        if not isinstance(password, str):
            raise ValueError("The saved password file is damaged.")
        if replaced_at is None:
            replaced_at = ""
        if not isinstance(replaced_at, str):
            raise ValueError("The saved password file is damaged.")
        try:
            secret = _password_line(password)
        except ValueError as exc:
            raise ValueError("The saved password file is damaged.") from exc
        if any(secret == kept.password for kept in revisions):
            continue
        revisions.append(PasswordRevision(secret, replaced_at.strip()))
        if len(revisions) >= MAX_PASSWORD_HISTORY:
            break
    return tuple(revisions)


def _entry_from_json(entry: dict) -> SavedPassword:
    if not isinstance(entry.get("name"), str) or not isinstance(entry.get("password"), str):
        raise ValueError("The saved password file is damaged.")
    username = entry.get("username", "")
    url = entry.get("url", "")
    notes = entry.get("notes", "")
    category = entry.get("category", "")
    favorite = entry.get("favorite", False)
    archived = entry.get("archived", False)
    created = entry.get("created", "")
    modified = entry.get("modified", "")
    last_used = entry.get("last_used", "")
    if username is None:
        username = ""
    if url is None:
        url = ""
    if notes is None:
        notes = ""
    if category is None:
        category = ""
    if created is None:
        created = ""
    if modified is None:
        modified = ""
    if last_used is None:
        last_used = ""
    if not isinstance(username, str) or not isinstance(url, str) or not isinstance(notes, str):
        raise ValueError("The saved password file is damaged.")
    if not isinstance(category, str) or not isinstance(created, str) or not isinstance(modified, str):
        raise ValueError("The saved password file is damaged.")
    if not isinstance(last_used, str):
        raise ValueError("The saved password file is damaged.")
    if not isinstance(favorite, bool) or not isinstance(archived, bool):
        raise ValueError("The saved password file is damaged.")
    history = _history_from_json(entry.get("history"))
    extras = {
        key: value
        for key, value in entry.items()
        if key not in KNOWN_ENTRY_KEYS
    }
    return SavedPassword(
        clean_name(entry["name"]),
        _password_line(entry["password"]),
        username=clean_username(username),
        url=clean_url(url),
        notes=clean_notes(notes),
        category=clean_category(category),
        favorite=favorite,
        archived=archived,
        created=created.strip(),
        modified=modified.strip(),
        last_used=last_used.strip(),
        history=history,
        extras=extras,
    )


def _encode_saved(items: list[SavedPassword]) -> bytes:
    payload = [_entry_to_json(item) for item in items]
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
        if not isinstance(entry, dict):
            raise ValueError("The saved password file is damaged.")
        try:
            item = _entry_from_json(entry)
        except ValueError as exc:
            raise ValueError("The saved password file is damaged.") from exc
        if item.name in used:
            continue
        used.add(item.name)
        saved.append(item)
    return saved


def _prefer_text(left: str, right: str) -> str:
    return left if left.strip() else right


def _merge_histories(
    left: tuple[PasswordRevision, ...],
    right: tuple[PasswordRevision, ...],
    *,
    current_password: str,
) -> tuple[PasswordRevision, ...]:
    merged: list[PasswordRevision] = []
    for revision in (*left, *right):
        try:
            secret = _password_line(revision.password)
        except ValueError:
            continue
        if secret == current_password:
            continue
        if any(secret == kept.password for kept in merged):
            continue
        merged.append(PasswordRevision(secret, revision.replaced_at))
        if len(merged) >= MAX_PASSWORD_HISTORY:
            break
    return tuple(merged)


def _merge_matching_entry(local: SavedPassword, incoming: SavedPassword) -> SavedPassword:
    """Same password: keep one row and fill empty optional fields from the other copy."""
    favorites = local.favorite or incoming.favorite
    archived = local.archived and incoming.archived
    extras = dict(local.extras)
    for key, value in incoming.extras.items():
        extras.setdefault(key, value)
    created = local.created or incoming.created
    modified = max(local.modified, incoming.modified) if local.modified and incoming.modified else (
        local.modified or incoming.modified
    )
    last_used = max(local.last_used, incoming.last_used) if local.last_used and incoming.last_used else (
        local.last_used or incoming.last_used
    )
    return SavedPassword(
        local.name,
        local.password,
        username=_prefer_text(local.username, incoming.username),
        url=_prefer_text(local.url, incoming.url),
        notes=_prefer_text(local.notes, incoming.notes),
        category=_prefer_text(local.category, incoming.category),
        favorite=favorites,
        archived=archived,
        created=created,
        modified=modified,
        last_used=last_used,
        history=_merge_histories(local.history, incoming.history, current_password=local.password),
        extras=extras,
    )


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


def change_vault_credentials(
    items: list[SavedPassword],
    new_passphrase: str,
    *,
    recovery_key: str | None = None,
    path: Path | None = None,
    n: int = SCRYPT_N,
) -> tuple[VaultKey, str]:
    """Seal the vault under a new passphrase and recovery key.

    The previous passphrase and recovery key stop opening the file.
    Returns the new key material and the recovery key to show once.
    """
    recovery = new_recovery_key() if recovery_key is None else require_recovery_key(recovery_key)
    material = new_vault_key(new_passphrase, recovery, n=n)
    write_vault(material, items, path)
    return material, recovery


def open_vault(secret: str, path: Path | None = None) -> tuple[VaultKey, list[SavedPassword]]:
    """Unlock saved passwords. A wrong passphrase or recovery key raises ValueError."""
    path = vault_path() if path is None else path
    if path.is_symlink():
        raise ValueError("The saved password file is a symbolic link.")
    if not path.is_file():
        raise ValueError("The saved password file is damaged.")
    return open_vault_bytes(secret, path.read_bytes())


def open_vault_bytes(secret: str, blob: bytes) -> tuple[VaultKey, list[SavedPassword]]:
    """Unlock a vault that is already in memory."""
    if len(secret) < MIN_PASSPHRASE_LENGTH:
        raise ValueError("That passphrase or recovery key did not unlock the saved passwords.")
    if blob.startswith(VAULT_MAGIC_V2):
        return _open_vault_v2(secret, blob)
    if blob.startswith(VAULT_MAGIC):
        return _open_vault_v1(secret, blob)
    raise ValueError("The saved password file is damaged.")


def items_from_same_vault(blob: bytes, material: VaultKey) -> list[SavedPassword] | None:
    """Read a vault sealed with this same key. A different vault returns None."""
    if not material.recovery_wrap or not blob.startswith(VAULT_MAGIC_V2):
        return None
    header = _v2_header(material.n, material.r, material.p, material.salt, material.recovery_salt)
    prefix = header + material.passphrase_wrap + material.recovery_wrap
    if not blob.startswith(prefix) or len(blob) < len(prefix) + 12 + 16:
        return None
    nonce = blob[len(prefix) : len(prefix) + 12]
    ciphertext = blob[len(prefix) + 12 :]
    try:
        raw = AESGCM(material.key).decrypt(nonce, ciphertext, prefix)
    except InvalidTag:
        return None
    return _decode_saved(raw)


def merge_saved(
    local: list[SavedPassword], incoming: list[SavedPassword]
) -> tuple[list[SavedPassword], int]:
    """Keep every name. A different password for the same name is stored beside it."""
    return merge_entries(local, incoming, conflict_suffix=" (other device)")


def merge_entries(
    local: list[SavedPassword],
    incoming: list[SavedPassword],
    *,
    conflict_suffix: str = " (imported)",
) -> tuple[list[SavedPassword], int]:
    """Merge incoming entries. Same password fills empty fields; a clash gets a new name."""
    merged: list[SavedPassword] = []
    taken: dict[str, int] = {}
    splits = 0
    for item in local:
        taken[item.name] = len(merged)
        merged.append(item)
    for item in incoming:
        slot = taken.get(item.name)
        if slot is None:
            taken[item.name] = len(merged)
            merged.append(item)
            continue
        if merged[slot].password == item.password:
            merged[slot] = _merge_matching_entry(merged[slot], item)
            continue
        splits += 1
        name = _unique_entry_name(item.name, taken, conflict_suffix)
        taken[name] = len(merged)
        merged.append(replace(item, name=name))
    return merged, splits


def _unique_entry_name(name: str, taken: dict[str, int], suffix: str) -> str:
    room = MAX_NAME_LENGTH - len(suffix)
    base = name[:room].rstrip() if len(name) + len(suffix) > MAX_NAME_LENGTH else name
    candidate = f"{base}{suffix}"
    number = 2
    while candidate in taken:
        if suffix.endswith(")"):
            numbered = f"{suffix[:-1]} {number})"
        else:
            numbered = f"{suffix} {number}"
        room = MAX_NAME_LENGTH - len(numbered)
        base = name[:room].rstrip()
        candidate = f"{base}{numbered}"
        number += 1
    return candidate


def _other_device_name(name: str, taken: dict[str, int]) -> str:
    return _unique_entry_name(name, taken, " (other device)")


CSV_NAME_KEYS = ("name", "title", "account", "entry")
CSV_USERNAME_KEYS = ("username", "user", "login", "login_username", "email")
CSV_PASSWORD_KEYS = ("password", "pass", "passwd", "login_password")
CSV_URL_KEYS = ("url", "website", "web site", "login_uri", "uri", "href")
CSV_NOTES_KEYS = ("notes", "note", "comments", "extra")
CSV_CATEGORY_KEYS = ("category", "folder", "group", "grouping")


def _csv_cell(row: dict[str, str], keys: tuple[str, ...]) -> str:
    lowered = {str(key).strip().casefold(): value for key, value in row.items() if key is not None}
    for key in keys:
        value = lowered.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def parse_password_csv(text: str) -> list[SavedPassword]:
    """Read common password-manager CSV exports into vault entries."""
    raw = text.lstrip("\ufeff")
    if not raw.strip():
        raise ValueError("That CSV file is empty.")
    reader = csv.DictReader(io.StringIO(raw))
    if reader.fieldnames is None:
        raise ValueError("That CSV file has no header row.")
    headers = {str(name).strip().casefold() for name in reader.fieldnames if name}
    if not headers:
        raise ValueError("That CSV file has no header row.")
    if not any(key in headers for key in CSV_PASSWORD_KEYS):
        raise ValueError("That CSV file needs a password column.")
    now = utc_now()
    items: list[SavedPassword] = []
    used: set[str] = set()
    unnamed = 0
    for row in reader:
        if row is None:
            continue
        password = _csv_cell(row, CSV_PASSWORD_KEYS)
        if not password:
            continue
        try:
            secret = _password_line(password)
        except ValueError:
            continue
        name = _csv_cell(row, CSV_NAME_KEYS)
        if not name:
            url = _csv_cell(row, CSV_URL_KEYS)
            unnamed += 1
            name = url if url else f"Imported {unnamed}"
        try:
            label = clean_name(name)
        except ValueError:
            unnamed += 1
            label = clean_name(f"Imported {unnamed}")
        if label in used:
            label = _unique_entry_name(label, {label: 0, **{n: 0 for n in used}}, " (imported)")
        used.add(label)
        try:
            items.append(
                SavedPassword(
                    label,
                    secret,
                    username=clean_username(_csv_cell(row, CSV_USERNAME_KEYS)),
                    url=clean_url(_csv_cell(row, CSV_URL_KEYS)),
                    notes=clean_notes(_csv_cell(row, CSV_NOTES_KEYS)),
                    category=clean_category(_csv_cell(row, CSV_CATEGORY_KEYS)),
                    created=now,
                    modified=now,
                )
            )
        except ValueError:
            continue
    if not items:
        raise ValueError("No password rows were found in that CSV file.")
    return items


def format_password_csv(items: list[SavedPassword]) -> str:
    """Write vault entries as a portable plaintext CSV other managers can import."""
    if not items:
        raise ValueError("There are no saved passwords to export.")
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["name", "username", "password", "url", "notes", "category"])
    for item in items:
        writer.writerow(
            [item.name, item.username, item.password, item.url, item.notes, item.category]
        )
    return buffer.getvalue()


def store_vault_blob(blob: bytes, path: Path | None = None) -> Path:
    """Write a vault received from another device without changing its bytes."""
    if not blob.startswith((VAULT_MAGIC, VAULT_MAGIC_V2)):
        raise ValueError("The saved password file is damaged.")
    path = vault_path() if path is None else path
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("The saved password file is a symbolic link.")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        os.write(descriptor, blob)
    finally:
        os.close(descriptor)
    return path


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

    from gi.repository import GLib

    window = PasswordWindow(Gtk, Gdk)
    window.window.connect("destroy", Gtk.main_quit)
    window.window.show_all()
    window.show_section(window.section)
    GLib.idle_add(window.maybe_show_onboarding)
    GLib.idle_add(window.maybe_prompt_lock_on_open)
    Gtk.main()


class PasswordWindow:
    """GTK window. Constructed with the Gtk and Gdk modules so import stays light."""

    def __init__(self, gtk, gdk) -> None:
        self.gtk = gtk
        self.gdk = gdk
        self.mode = "characters"
        self.current = ""

        self.window = gtk.Window(title="Local Password")
        self.window.set_default_size(1040, 720)
        self.window.set_size_request(760, 580)
        self.window.get_style_context().add_class("app")
        for icon in _icon_candidates():
            if icon.is_file():
                try:
                    self.window.set_icon_from_file(str(icon))
                except Exception:
                    pass
                break

        root = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=14)
        root.set_margin_top(20)
        root.set_margin_bottom(16)
        root.set_margin_start(20)
        root.set_margin_end(20)
        self.window.add(root)

        self.theme_mode = load_appearance_mode()
        self.dark = resolve_dark_mode(self.theme_mode)
        self.preferences = load_preferences()
        self.revealed_names: set[str] = set()
        self.breach_counts: dict[str, int] = {}
        self._breach_check_running = False
        self._clipboard_generation = 0
        self._clipboard_value = ""
        self._clipboard_clear_source = 0
        self._last_activity = time.monotonic()
        self._auto_lock_source = 0
        self._onboarding_scheduled = False

        header = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=6)
        header.get_style_context().add_class("header-bar")
        top = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=12)
        brand_row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=10)
        logo = self._brand_logo()
        if logo is not None:
            brand_row.pack_start(logo, False, False, 0)
        brand = gtk.Label(label="Local Password", xalign=0)
        brand.get_style_context().add_class("brand")
        brand_row.pack_start(brand, False, False, 0)
        brand_row.set_hexpand(True)
        top.pack_start(brand_row, True, True, 0)

        status_box = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        self.vault_status = gtk.Label(label="No vault yet", xalign=1)
        self.vault_status.get_style_context().add_class("vault-status")
        self.header_lock_button = gtk.Button(label="Unlock")
        self.header_lock_button.get_style_context().add_class("secondary")
        self.header_lock_button.set_no_show_all(True)
        self.header_lock_button.hide()
        self.header_lock_button.connect("clicked", self.on_lock_toggle)
        status_box.pack_start(self.vault_status, False, False, 0)
        status_box.pack_start(self.header_lock_button, False, False, 0)
        top.pack_start(status_box, False, False, 0)
        header.pack_start(top, False, False, 0)

        self.page_title = gtk.Label(label="Dashboard", xalign=0)
        self.page_title.get_style_context().add_class("section-title")
        header.pack_start(self.page_title, False, False, 0)
        root.pack_start(header, False, False, 0)

        nav = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=6)
        nav.set_homogeneous(True)
        self.dashboard_tab = gtk.Button(label="Dashboard")
        self.create_tab = gtk.Button(label="Generate")
        self.saved_tab = gtk.Button(label="Saved")
        self.settings_tab = gtk.Button(label="Settings")
        for button in (
            self.dashboard_tab,
            self.create_tab,
            self.saved_tab,
            self.settings_tab,
        ):
            button.get_style_context().add_class("nav")
            nav.pack_start(button, True, True, 0)
        self.dashboard_tab.connect("clicked", lambda *_args: self.show_section("dashboard"))
        self.create_tab.connect("clicked", lambda *_args: self.show_section("generate"))
        self.saved_tab.connect("clicked", lambda *_args: self.show_section("saved"))
        self.settings_tab.connect("clicked", lambda *_args: self.show_section("settings"))
        root.pack_start(nav, False, False, 0)

        dashboard_frame, dashboard_shell = self._card()
        self.dashboard_view = dashboard_frame
        self.dashboard_view.set_vexpand(True)
        self.dashboard_view.set_no_show_all(True)
        self.dashboard_view.hide()
        root.pack_start(self.dashboard_view, True, True, 0)
        self._build_dashboard(self._scroll_page(dashboard_shell))

        columns = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=14)
        columns.set_vexpand(True)
        self.create_view = columns
        root.pack_start(self.create_view, True, True, 0)

        controls_frame, controls_shell = self._card()
        columns.pack_start(controls_frame, True, True, 0)
        self._build_controls(self._scroll_page(controls_shell))

        result_frame, result = self._card()
        columns.pack_start(result_frame, True, True, 0)
        self._build_result(result)

        saved_frame, saved_inner = self._card()
        self.saved_view = saved_frame
        self.saved_view.set_vexpand(True)
        self.saved_view.set_no_show_all(True)
        self.saved_view.hide()
        root.pack_start(self.saved_view, True, True, 0)

        settings_frame, settings_shell = self._card()
        self.settings_view = settings_frame
        self.settings_view.set_vexpand(True)
        self.settings_view.set_no_show_all(True)
        self.settings_view.hide()
        root.pack_start(self.settings_view, True, True, 0)
        self._build_settings(self._scroll_page(settings_shell))
        self.apply_dark()
        self._build_manager(saved_inner)
        self.window.connect("key-press-event", self._note_activity)
        self.window.connect("button-press-event", self._note_activity)
        self._arm_auto_lock_timer()

    def set_theme_mode(self, mode: str) -> None:
        chosen = mode.casefold().strip()
        if chosen not in THEME_OPTIONS:
            return
        self.theme_mode = chosen
        self.dark = resolve_dark_mode(chosen)
        self.apply_dark()
        self._style_theme_buttons()
        try:
            store_appearance_mode(chosen)
        except OSError:
            pass

    def on_toggle_dark(self, *_args) -> None:
        """Legacy toggle: flips between light and dark (clears system)."""
        self.set_theme_mode(THEME_LIGHT if self.dark else THEME_DARK)

    def _style_theme_buttons(self) -> None:
        buttons = getattr(self, "theme_buttons", None)
        if not buttons:
            return
        for mode, button in buttons.items():
            style = button.get_style_context()
            if mode == self.theme_mode:
                style.add_class("on")
                style.remove_class("off")
            else:
                style.add_class("off")
                style.remove_class("on")

    def _persist_preferences(self) -> None:
        try:
            store_preferences(self.preferences)
        except OSError:
            self._sync_note("Could not save that setting on this computer.")

    def _on_clipboard_clear_changed(self, *_args) -> None:
        active = self.clipboard_clear_combo.get_active_id()
        if active is None:
            return
        seconds = _normalize_choice(
            int(active), CLIPBOARD_CLEAR_OPTIONS, DEFAULT_CLIPBOARD_CLEAR_SECONDS
        )
        self.preferences = replace(self.preferences, clipboard_clear_seconds=seconds)
        self._persist_preferences()

    def _on_auto_lock_changed(self, *_args) -> None:
        active = self.auto_lock_combo.get_active_id()
        if active is None:
            return
        seconds = _normalize_choice(int(active), AUTO_LOCK_OPTIONS, DEFAULT_AUTO_LOCK_SECONDS)
        self.preferences = replace(self.preferences, auto_lock_seconds=seconds)
        self._persist_preferences()
        self._note_activity()
        self._arm_auto_lock_timer()

    def _on_confirm_reveal_toggled(self, button) -> None:
        self.preferences = replace(
            self.preferences, confirm_before_reveal=bool(button.get_active())
        )
        self._persist_preferences()

    def _on_lock_on_open_toggled(self, button) -> None:
        self.preferences = replace(
            self.preferences, lock_on_open=bool(button.get_active())
        )
        self._persist_preferences()

    def on_lock_now(self, *_args) -> None:
        """Lock the vault immediately from Settings when it is unlocked."""
        self._note_activity()
        if self.vault_key is None:
            self._sync_note("The vault is already locked, or there is no vault yet.")
            return
        self._lock_saved()
        self._sync_note("Vault locked.")

    def on_clear_search(self, *_args) -> None:
        self.find_entry.set_text("")
        self._refresh_saved_rows()

    def _show_clear_search(self) -> None:
        self.clear_search_button.set_no_show_all(False)
        self.clear_search_button.show()

    def _hide_clear_search(self) -> None:
        self.clear_search_button.hide()
        self.clear_search_button.set_no_show_all(True)

    def maybe_show_onboarding(self) -> bool:
        if self._onboarding_scheduled or load_onboarding_done():
            return False
        self._onboarding_scheduled = True
        self._show_onboarding()
        return False

    def maybe_prompt_lock_on_open(self) -> bool:
        """When Lock on open is on, ask for the passphrase as soon as the window appears."""
        if not self.preferences.lock_on_open:
            return False
        if self.vault_key is not None or not self.locked:
            return False
        if not self._ensure_vault_key():
            self._update_lock_button()
            return False
        self.revealed_names.clear()
        self._clear_stale_lock_status()
        self._update_lock_button()
        if self.section == "dashboard":
            self._refresh_dashboard()
        else:
            self._refresh_saved_rows()
        return False

    def _show_onboarding(self) -> None:
        gtk = self.gtk
        dialog = gtk.Dialog(title="Welcome to Local Password", transient_for=self.window, modal=True)
        self._match_dialog(dialog)
        skip = dialog.add_button("Skip", gtk.ResponseType.CANCEL)
        skip.get_style_context().add_class("secondary")
        start = dialog.add_button("Get started", gtk.ResponseType.OK)
        start.get_style_context().add_class("primary")
        dialog.set_default_response(gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_spacing(10)
        for setter in (
            content.set_margin_top,
            content.set_margin_bottom,
            content.set_margin_start,
            content.set_margin_end,
        ):
            setter(18)
        title = gtk.Label(label="Passwords stay on this computer", xalign=0)
        title.get_style_context().add_class("section-title")
        content.pack_start(title, False, False, 0)
        for line in (
            "Generate a strong password or word passphrase, then save it under a name.",
            "The first save asks for a passphrase and shows a recovery key once. Write that key down.",
            "Saved passwords stay encrypted. Unlock with the passphrase or recovery key.",
            "Use Dashboard for shortcuts, Saved to search and manage, and Settings for backups.",
        ):
            label = gtk.Label(label=line, xalign=0)
            label.set_line_wrap(True)
            label.get_style_context().add_class("hint")
            content.pack_start(label, False, False, 0)
        dialog.show_all()
        dialog.run()
        dialog.destroy()
        try:
            store_onboarding_done()
        except OSError:
            pass

    def _note_activity(self, *_args) -> bool:
        self._last_activity = time.monotonic()
        return False

    def _arm_auto_lock_timer(self) -> None:
        from gi.repository import GLib

        if self._auto_lock_source:
            GLib.source_remove(self._auto_lock_source)
            self._auto_lock_source = 0
        if self.preferences.auto_lock_seconds <= 0:
            return
        self._auto_lock_source = GLib.timeout_add_seconds(15, self._check_auto_lock)

    def _check_auto_lock(self) -> bool:
        seconds = self.preferences.auto_lock_seconds
        if seconds <= 0 or self.vault_key is None:
            return True
        if time.monotonic() - self._last_activity >= seconds:
            self._lock_saved()
            self.status.set_text("Saved passwords locked after sitting idle.")
        return True

    def _schedule_clipboard_clear(self, text: str) -> None:
        from gi.repository import GLib

        seconds = self.preferences.clipboard_clear_seconds
        if seconds <= 0 or not text:
            return
        self._clipboard_generation += 1
        generation = self._clipboard_generation
        self._clipboard_value = text
        if self._clipboard_clear_source:
            GLib.source_remove(self._clipboard_clear_source)
        self._clipboard_clear_source = GLib.timeout_add_seconds(
            seconds, self._clear_clipboard_if_unchanged, generation
        )

    def _clear_clipboard_if_unchanged(self, generation: int) -> bool:
        self._clipboard_clear_source = 0
        if generation != self._clipboard_generation:
            return False
        expected = self._clipboard_value
        self._clipboard_value = ""
        if not expected:
            return False
        # Windows: GTK's clipboard is often not the system clipboard. Clear Win32 first.
        if sys.platform == "win32":
            current = generator.read_windows_clipboard_text()
            if current == expected:
                generator.clear_windows_clipboard()
        try:
            clipboard = self.gtk.Clipboard.get(self.gdk.SELECTION_CLIPBOARD)
            current = clipboard.wait_for_text()
            if current == expected:
                clipboard.set_text("", -1)
                clipboard.store()
        except Exception:
            pass
        if shutil.which("xclip") is not None:
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard", "-in"],
                    input=b"",
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError:
                pass
        return False

    def on_change_passphrase(self, *_args) -> None:
        """Replace the vault passphrase and show a fresh recovery key once."""
        self._note_activity()
        if not vault_path().is_file():
            self._sync_note("Save a password first. There is no vault to re-lock yet.")
            return
        current = self._prompt_passphrase(
            confirm=False,
            message="Enter the current passphrase or recovery key.",
        )
        if current is None:
            return
        try:
            _material, items = open_vault(current)
        except ValueError as exc:
            self._sync_note(str(exc))
            return
        except OSError:
            self._sync_note("Could not read the vault on this computer.")
            return
        new_phrase = self._prompt_passphrase(
            confirm=True,
            message="Choose a new passphrase to lock saved passwords. It is not stored.",
        )
        if new_phrase is None:
            return
        recovery = new_recovery_key()
        if not self._confirm_recovery_key(recovery):
            self._sync_note("Passphrase not changed. Write down the recovery key to finish.")
            return
        try:
            material, _shown = change_vault_credentials(
                items,
                new_phrase,
                recovery_key=recovery,
            )
        except ValueError as exc:
            self._sync_note(str(exc))
            return
        except OSError:
            self._sync_note("Could not rewrite the vault with the new passphrase.")
            return
        self.vault_key = material
        self.saved = items
        self.locked = False
        self.revealed_names.clear()
        self._update_lock_button()
        self._refresh_saved_rows()
        if self.section == "dashboard":
            self._refresh_dashboard()
        self._sync_note(
            "Passphrase changed. The old passphrase and recovery key no longer open this vault."
        )

    def on_export_vault(self, *_args) -> None:
        gtk = self.gtk
        try:
            blob = read_vault_blob()
        except ValueError as exc:
            self._sync_note(str(exc))
            return
        except OSError:
            self._sync_note("Could not read the vault on this computer.")
            return
        dialog = gtk.FileChooserDialog(
            title="Export vault",
            transient_for=self.window,
            action=gtk.FileChooserAction.SAVE,
        )
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        dialog.add_button("Export", gtk.ResponseType.OK)
        dialog.set_current_name("saved.vault")
        dialog.set_do_overwrite_confirmation(True)
        response = dialog.run()
        target = dialog.get_filename()
        dialog.destroy()
        if response != gtk.ResponseType.OK or not target:
            return
        path = Path(target)
        try:
            path.write_bytes(blob)
            if hasattr(os, "chmod"):
                try:
                    os.chmod(path, 0o600)
                except OSError:
                    pass
        except OSError:
            self._sync_note("Could not write that export file.")
            return
        self._sync_note(f"Exported the encrypted vault to {path.name}.")

    def on_import_vault(self, *_args) -> None:
        gtk = self.gtk
        if vault_path().is_file():
            confirm = gtk.MessageDialog(
                transient_for=self.window,
                modal=True,
                message_type=gtk.MessageType.WARNING,
                buttons=gtk.ButtonsType.OK_CANCEL,
                text="Replace the vault on this computer?",
            )
            confirm.format_secondary_text(
                "Import copies an encrypted vault file onto this computer and locks Saved. "
                "The current vault file is replaced."
            )
            answer = confirm.run()
            confirm.destroy()
            if answer != gtk.ResponseType.OK:
                return
        dialog = gtk.FileChooserDialog(
            title="Import vault",
            transient_for=self.window,
            action=gtk.FileChooserAction.OPEN,
        )
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        dialog.add_button("Import", gtk.ResponseType.OK)
        response = dialog.run()
        source = dialog.get_filename()
        dialog.destroy()
        if response != gtk.ResponseType.OK or not source:
            return
        try:
            blob = Path(source).read_bytes()
        except OSError:
            self._sync_note("Could not read that vault file.")
            return
        if not is_vault_blob(blob):
            self._sync_note("That file is not a Local Password vault.")
            return
        try:
            store_vault_blob(blob)
        except (OSError, ValueError) as exc:
            self._sync_note(str(exc) if isinstance(exc, ValueError) else "Could not import that vault.")
            return
        self._prepare_saved()
        self.show_section("saved")
        self._sync_note("Vault imported. Unlock with the same passphrase or recovery key.")

    def on_import_csv(self, *_args) -> None:
        gtk = self.gtk
        if self.vault_key is None:
            if not self._ensure_vault_key():
                self._sync_note("Unlock the vault before importing a CSV.")
                return
        dialog = gtk.FileChooserDialog(
            title="Import CSV",
            transient_for=self.window,
            action=gtk.FileChooserAction.OPEN,
        )
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        dialog.add_button("Import", gtk.ResponseType.OK)
        filt = gtk.FileFilter()
        filt.set_name("CSV files")
        filt.add_pattern("*.csv")
        filt.add_pattern("*.txt")
        dialog.add_filter(filt)
        response = dialog.run()
        source = dialog.get_filename()
        dialog.destroy()
        if response != gtk.ResponseType.OK or not source:
            return
        try:
            text = Path(source).read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = Path(source).read_text(encoding="latin-1")
            except OSError:
                self._sync_note("Could not read that CSV file.")
                return
        except OSError:
            self._sync_note("Could not read that CSV file.")
            return
        try:
            incoming = parse_password_csv(text)
            before = len(self.saved)
            updated, splits = merge_entries(self.saved, incoming, conflict_suffix=" (imported)")
            write_vault(self.vault_key, updated)
        except ValueError as exc:
            self._sync_note(str(exc))
            return
        except OSError:
            self._sync_note("Could not save the imported passwords.")
            return
        self.saved = updated
        self.locked = False
        added = len(updated) - before
        self._refresh_saved_rows()
        self._refresh_dashboard()
        self.show_section("saved")
        if splits:
            note = f"Imported {added} new entr{'y' if added == 1 else 'ies'} ({splits} renamed to avoid clashes)."
        else:
            note = f"Imported {added} new entr{'y' if added == 1 else 'ies'} from the CSV."
        self._sync_note(note)
        self.manager_message.set_text(note)
        self.manager_message.show()

    def on_export_csv(self, *_args) -> None:
        gtk = self.gtk
        if self.vault_key is None:
            if not self._ensure_vault_key():
                self._sync_note("Unlock the vault before exporting a CSV.")
                return
        if not self.saved:
            self._sync_note("There are no saved passwords to export.")
            return
        confirm = gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=gtk.MessageType.WARNING,
            buttons=gtk.ButtonsType.OK_CANCEL,
            text="Export passwords as plaintext CSV?",
        )
        confirm.format_secondary_text(
            "The CSV file is not encrypted. Anyone who can open that file can read every password. "
            "Delete it when you are done moving the entries."
        )
        answer = confirm.run()
        confirm.destroy()
        if answer != gtk.ResponseType.OK:
            return
        dialog = gtk.FileChooserDialog(
            title="Export CSV",
            transient_for=self.window,
            action=gtk.FileChooserAction.SAVE,
        )
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        dialog.add_button("Export", gtk.ResponseType.OK)
        dialog.set_current_name("local-password.csv")
        dialog.set_do_overwrite_confirmation(True)
        filt = gtk.FileFilter()
        filt.set_name("CSV files")
        filt.add_pattern("*.csv")
        dialog.add_filter(filt)
        response = dialog.run()
        target = dialog.get_filename()
        dialog.destroy()
        if response != gtk.ResponseType.OK or not target:
            return
        path = Path(target)
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        try:
            text = format_password_csv(self.saved)
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            if hasattr(os, "chmod"):
                try:
                    os.chmod(path, 0o600)
                except OSError:
                    pass
        except ValueError as exc:
            self._sync_note(str(exc))
            return
        except OSError:
            self._sync_note("Could not write that CSV file.")
            return
        note = f"Exported {len(self.saved)} entr{'y' if len(self.saved) == 1 else 'ies'} to {path.name}."
        self._sync_note(note)

    def apply_dark(self) -> None:
        context = self.window.get_style_context()
        if self.dark:
            context.add_class("dark")
        else:
            context.remove_class("dark")
        self._style_theme_buttons()

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
            setter(18)
        outer.pack_start(inner, True, True, 0)
        return outer, inner

    def _scroll_page(self, page):
        """Wrap page content so short windows can scroll to the bottom."""
        gtk = self.gtk
        scroller = gtk.ScrolledWindow()
        scroller.set_policy(gtk.PolicyType.NEVER, gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_hexpand(True)
        # Keep the scrollbar from covering labels on narrow widths.
        try:
            scroller.set_overlay_scrolling(True)
        except AttributeError:
            pass
        inner = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=12)
        scroller.add(inner)
        page.pack_start(scroller, True, True, 0)
        return inner

    def _brand_logo(self):
        gtk = self.gtk
        try:
            from gi.repository import GdkPixbuf
        except Exception:
            return None
        for path in _icon_candidates():
            if not path.is_file() or path.suffix.lower() != ".png":
                continue
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), 28, 28, True)
            except Exception:
                continue
            return gtk.Image.new_from_pixbuf(pixbuf)
        return None

    def _build_dashboard(self, page) -> None:
        gtk = self.gtk
        eyebrow = gtk.Label(label="ON THIS COMPUTER", xalign=0)
        eyebrow.get_style_context().add_class("eyebrow")
        page.pack_start(eyebrow, False, False, 0)

        self.dashboard_welcome = gtk.Label(label="Welcome to Local Password", xalign=0)
        self.dashboard_welcome.get_style_context().add_class("section-title")
        page.pack_start(self.dashboard_welcome, False, False, 0)

        self.dashboard_lede = gtk.Label(
            label=(
                "Generate a strong password, save it under a name, and keep the vault locked "
                "when you step away. Everything stays on this computer."
            ),
            xalign=0,
        )
        self.dashboard_lede.set_line_wrap(True)
        self.dashboard_lede.get_style_context().add_class("lede")
        page.pack_start(self.dashboard_lede, False, False, 0)

        stats = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=12)
        stats.set_homogeneous(True)
        saved_card, saved_inner = self._card()
        saved_card.get_style_context().remove_class("card")
        saved_card.get_style_context().add_class("entry-card")
        self.dashboard_count = gtk.Label(label="0", xalign=0)
        self.dashboard_count.get_style_context().add_class("stat-value")
        saved_caption = gtk.Label(label="Saved passwords", xalign=0)
        saved_caption.get_style_context().add_class("stat-label")
        saved_inner.pack_start(self.dashboard_count, False, False, 0)
        saved_inner.pack_start(saved_caption, False, False, 0)
        stats.pack_start(saved_card, True, True, 0)

        favorite_card, favorite_inner = self._card()
        favorite_card.get_style_context().remove_class("card")
        favorite_card.get_style_context().add_class("entry-card")
        self.dashboard_favorites = gtk.Label(label="0", xalign=0)
        self.dashboard_favorites.get_style_context().add_class("stat-value")
        favorite_caption = gtk.Label(label="Favorites", xalign=0)
        favorite_caption.get_style_context().add_class("stat-label")
        favorite_inner.pack_start(self.dashboard_favorites, False, False, 0)
        favorite_inner.pack_start(favorite_caption, False, False, 0)
        stats.pack_start(favorite_card, True, True, 0)

        status_card, status_inner = self._card()
        status_card.get_style_context().remove_class("card")
        status_card.get_style_context().add_class("entry-card")
        self.dashboard_lock_value = gtk.Label(label="No vault", xalign=0)
        self.dashboard_lock_value.get_style_context().add_class("stat-value")
        lock_caption = gtk.Label(label="Vault status", xalign=0)
        lock_caption.get_style_context().add_class("stat-label")
        status_inner.pack_start(self.dashboard_lock_value, False, False, 0)
        status_inner.pack_start(lock_caption, False, False, 0)
        stats.pack_start(status_card, True, True, 0)
        self.dashboard_stats = stats
        page.pack_start(stats, False, False, 0)

        actions = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        self.dashboard_generate = gtk.Button(label="Generate password")
        self.dashboard_generate.get_style_context().add_class("primary")
        self.dashboard_generate.connect("clicked", lambda *_: self.show_section("generate"))
        self.dashboard_add = gtk.Button(label="Add password")
        self.dashboard_add.get_style_context().add_class("secondary")
        self.dashboard_add.connect("clicked", self.on_add_password)
        self.dashboard_open_saved = gtk.Button(label="Open Saved")
        self.dashboard_open_saved.get_style_context().add_class("secondary")
        self.dashboard_open_saved.connect("clicked", lambda *_: self.show_section("saved"))
        actions.pack_start(self.dashboard_generate, False, False, 0)
        actions.pack_start(self.dashboard_add, False, False, 0)
        actions.pack_start(self.dashboard_open_saved, False, False, 0)
        page.pack_start(actions, False, False, 0)

        self.dashboard_recent_label = gtk.Label(label="Recently used", xalign=0)
        self.dashboard_recent_label.get_style_context().add_class("eyebrow")
        page.pack_start(self.dashboard_recent_label, False, False, 0)
        self.dashboard_recent = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=8)
        page.pack_start(self.dashboard_recent, False, False, 0)
        self.dashboard_empty = gtk.Label(
            label=(
                "No passwords are saved yet. Open Generate, create one, give it a name, "
                "then Save. A passphrase will lock the vault."
            ),
            xalign=0,
        )
        self.dashboard_empty.set_line_wrap(True)
        self.dashboard_empty.get_style_context().add_class("hint")
        page.pack_start(self.dashboard_empty, False, False, 0)

    def _refresh_dashboard(self) -> None:
        gtk = self.gtk
        for child in list(self.dashboard_recent.get_children()):
            self.dashboard_recent.remove(child)
        if self.locked and self.vault_key is None:
            self.dashboard_welcome.set_text("Your vault is locked")
            self.dashboard_lede.set_text(
                "Unlock from the header. Generate still works while the vault stays locked."
            )
            # One unlock path (header). Hide empty stats and the extra unlock CTA.
            self.dashboard_stats.hide()
            self.dashboard_open_saved.hide()
            self.dashboard_recent_label.hide()
            self.dashboard_empty.hide()
            self.dashboard_recent.hide()
            return
        self.dashboard_stats.show()
        self.dashboard_open_saved.show()
        active = active_saved_entries(self.saved)
        count = len(active)
        favorites = sum(1 for item in active if item.favorite)
        self.dashboard_count.set_text(str(count))
        self.dashboard_favorites.set_text(str(favorites))
        if count == 0:
            self.dashboard_welcome.set_text("Welcome to Local Password")
            self.dashboard_lede.set_text(
                "Generate a strong password, save it under a name, and keep the vault locked "
                "when you step away. Everything stays on this computer."
            )
            self.dashboard_lock_value.set_text("No vault" if not vault_path().is_file() else "Empty")
            self.dashboard_empty.set_text(
                "No passwords are saved yet. Generate one, or Add password for an account "
                "you already have. A passphrase will lock the vault."
            )
            self.dashboard_empty.show()
            self.dashboard_recent_label.hide()
            self.dashboard_recent.hide()
            return
        weak_count, reuse_count, stale_count, breached_count, attention_count = (
            password_health_summary(self.saved, breach_counts=self.breach_counts)
        )
        self.dashboard_welcome.set_text("Ready when you are")
        if attention_count:
            parts = []
            if weak_count:
                parts.append(
                    f"{weak_count} weak password{'s' if weak_count != 1 else ''}"
                )
            if reuse_count:
                parts.append(
                    f"{reuse_count} reused password{'s' if reuse_count != 1 else ''}"
                )
            if stale_count:
                parts.append(
                    f"{stale_count} stale password{'s' if stale_count != 1 else ''}"
                )
            if breached_count:
                parts.append(
                    f"{breached_count} found in known breaches"
                )
            detail = " and ".join(parts) if parts else f"{attention_count} needing attention"
            verb = "needs" if attention_count == 1 else "need"
            self.dashboard_lede.set_text(
                f"Open Saved to review health. {detail} {verb} attention."
            )
        else:
            self.dashboard_lede.set_text(
                "Open Saved to copy a password or username, or Generate to make another. "
                "Saved passwords look strong, unique, and recently changed."
            )
        self.dashboard_lock_value.set_text("Unlocked")
        self.dashboard_empty.hide()
        self.dashboard_recent_label.show()
        self.dashboard_recent.show()
        if any(item.last_used for item in self.saved):
            self.dashboard_recent_label.set_text("Recently used")
        else:
            self.dashboard_recent_label.set_text("Recently changed")
        for item in recently_used_entries(self.saved, 5):
            row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
            row.get_style_context().add_class("entry-card")
            for setter in (
                row.set_margin_top,
                row.set_margin_bottom,
                row.set_margin_start,
                row.set_margin_end,
            ):
                setter(10)
            text = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=2)
            text.set_hexpand(True)
            name = gtk.Label(label=item.name, xalign=0)
            name.get_style_context().add_class("saved-name")
            text.pack_start(name, False, False, 0)
            dates = entry_dates_label(item)
            if dates:
                when = gtk.Label(label=dates, xalign=0)
                when.get_style_context().add_class("hint")
                text.pack_start(when, False, False, 0)
            used = gtk.Label(label=last_used_label(item), xalign=0)
            used.get_style_context().add_class("hint")
            text.pack_start(used, False, False, 0)
            breach_count = self.breach_counts.get(password_sha1_hex(item.password), 0)
            if breach_count > 0:
                badge = gtk.Label(label="Breached", xalign=1)
                badge.get_style_context().add_class("danger")
            elif entry_is_weak(item.password):
                badge = gtk.Label(label="Weak", xalign=1)
                badge.get_style_context().add_class("danger")
            elif reuse_warning_for(item, self.saved):
                badge = gtk.Label(label="Reused", xalign=1)
                badge.get_style_context().add_class("danger")
            elif entry_is_stale(item):
                badge = gtk.Label(label="Stale", xalign=1)
                badge.get_style_context().add_class("danger")
            else:
                badge = gtk.Label(label="••••••••", xalign=1)
                badge.get_style_context().add_class("hint")
            row.pack_start(text, True, True, 0)
            row.pack_start(badge, False, False, 0)
            self.dashboard_recent.pack_start(row, False, False, 0)
        self.dashboard_recent.show_all()

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
        self.uppercase = self._chip("Uppercase", True)
        self.lowercase = self._chip("Lowercase", True)
        self.digits = self._chip("Digits", True)
        self.symbols = self._chip("Symbols", True)
        for chip in (self.uppercase, self.lowercase, self.digits, self.symbols):
            chips.pack_start(chip, True, True, 0)
        self.character_box.pack_start(chips, False, False, 0)
        self.ambiguous = self._chip("Exclude ambiguous", False)
        self.ambiguous.set_halign(gtk.Align.START)
        self.character_box.pack_start(self.ambiguous, False, False, 0)
        exclude_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=4)
        exclude_label = gtk.Label(label="Also exclude", xalign=0)
        self.exclude_entry = gtk.Entry()
        self.exclude_entry.set_placeholder_text("e.g. $!@")
        self.exclude_entry.set_max_length(generator.MAX_EXCLUDE_LENGTH)
        exclude_hint = gtk.Label(
            label="Characters a site rejects. Exclude ambiguous drops 0/O/1/l lookalikes.",
            xalign=0,
        )
        exclude_hint.set_line_wrap(True)
        exclude_hint.get_style_context().add_class("hint")
        exclude_box.pack_start(exclude_label, False, False, 0)
        exclude_box.pack_start(self.exclude_entry, False, False, 0)
        exclude_box.pack_start(exclude_hint, False, False, 0)
        self.character_box.pack_start(exclude_box, False, False, 0)

        self.word_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=8)
        self.word_box.set_no_show_all(True)
        controls.pack_start(self.word_box, False, False, 0)
        self.words = gtk.SpinButton.new_with_range(
            generator.MIN_WORD_COUNT, generator.MAX_WORD_COUNT, 1
        )
        self.words.set_value(generator.DEFAULT_WORD_COUNT)
        self.words.set_numeric(True)
        self.word_box.pack_start(self._labeled("Words", self.words), False, False, 0)
        sep_row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        sep_row.set_homogeneous(True)
        self.separator_buttons: dict[str, object] = {}
        for label, value in (
            ("Space", " "),
            ("Hyphen", "-"),
            ("Underscore", "_"),
            ("Period", "."),
        ):
            button = gtk.Button(label=label)
            button.get_style_context().add_class("mode")
            button.connect(
                "clicked",
                lambda *_args, chosen=value: self.set_separator(chosen),
            )
            sep_row.pack_start(button, True, True, 0)
            self.separator_buttons[value] = button
        self.separator = " "
        self.word_box.pack_start(sep_row, False, False, 0)
        self.capitalize = self._chip("Capitalize words", False)
        self.capitalize.set_halign(gtk.Align.START)
        self.word_box.pack_start(self.capitalize, False, False, 0)
        word_hint = gtk.Label(
            label="Six words are about 78 bits; five stay under the strong line.",
            xalign=0,
        )
        word_hint.set_line_wrap(True)
        word_hint.get_style_context().add_class("hint")
        self.word_box.pack_start(word_hint, False, False, 0)
        self._style_separator_buttons()

        self.count = gtk.SpinButton.new_with_range(1, generator.MAX_PASSWORD_COUNT, 1)
        self.count.set_value(1)
        self.count.set_numeric(True)
        controls.pack_start(self._labeled("Number of passwords", self.count), False, False, 0)

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
            label="Search-space estimate. Strong starts at about 75 bits.",
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
        name_box.pack_start(name_label, False, False, 0)
        name_box.pack_start(self.name_entry, False, False, 0)

        actions = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_homogeneous(True)
        self.reveal_button = gtk.Button(label="Hide")
        self.reveal_button.get_style_context().add_class("secondary")
        self.reveal_button.set_sensitive(False)
        self.reveal_button.connect("clicked", self.on_toggle_result_reveal)
        self.copy_button = gtk.Button(label="Copy")
        self.copy_button.get_style_context().add_class("primary")
        self.copy_button.set_sensitive(False)
        self.copy_button.connect("clicked", self.on_copy)
        self.regenerate_button = gtk.Button(label="Regenerate")
        self.regenerate_button.get_style_context().add_class("secondary")
        self.regenerate_button.set_sensitive(False)
        self.regenerate_button.connect("clicked", self.on_regenerate)
        self.save_button = gtk.Button(label="Save")
        self.save_button.get_style_context().add_class("secondary")
        self.save_button.set_sensitive(False)
        self.save_button.connect("clicked", self.on_save)
        for button in (
            self.reveal_button,
            self.copy_button,
            self.regenerate_button,
            self.save_button,
        ):
            actions.pack_start(button, True, True, 0)

        self.result_revealed = True
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

        self.status = gtk.Label(
            label="Generate a password. Name it, then save it.",
            xalign=0,
        )
        self.status.set_line_wrap(True)
        self.status.get_style_context().add_class("hint")
        result.pack_start(self.status, False, False, 0)

    def _build_settings(self, page) -> None:
        gtk = self.gtk
        heading = gtk.Label(label="Settings", xalign=0)
        heading.get_style_context().add_class("section-title")
        page.pack_start(heading, False, False, 0)
        appearance = gtk.Label(label="APPEARANCE", xalign=0)
        appearance.get_style_context().add_class("eyebrow")
        page.pack_start(appearance, False, False, 0)
        theme_row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        self.theme_buttons: dict[str, object] = {}
        for mode, label in (
            (THEME_LIGHT, "Light"),
            (THEME_DARK, "Dark"),
            (THEME_SYSTEM, "System"),
        ):
            button = gtk.Button(label=label)
            button.get_style_context().add_class("mode")
            button.connect("clicked", lambda *_args, chosen=mode: self.set_theme_mode(chosen))
            theme_row.pack_start(button, False, False, 0)
            self.theme_buttons[mode] = button
        # Keep a dark_button alias for older tests that flip Dark.
        self.dark_button = self.theme_buttons[THEME_DARK]
        page.pack_start(theme_row, False, False, 0)
        self._style_theme_buttons()

        security = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=10)
        security.get_style_context().add_class("settings-block")
        security_label = gtk.Label(label="SECURITY", xalign=0)
        security_label.get_style_context().add_class("eyebrow")
        security.pack_start(security_label, False, False, 0)
        security_hint = gtk.Label(
            label="Clipboard clear is best-effort. Breach checks are on Saved.",
            xalign=0,
        )
        security_hint.set_line_wrap(True)
        security_hint.get_style_context().add_class("hint")
        security.pack_start(security_hint, False, False, 0)

        clear_row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        clear_caption = gtk.Label(label="Clear clipboard", xalign=0)
        clear_caption.set_hexpand(True)
        clear_row.pack_start(clear_caption, True, True, 0)
        self.clipboard_clear_combo = gtk.ComboBoxText()
        for seconds, label in CLIPBOARD_CLEAR_OPTIONS:
            self.clipboard_clear_combo.append(str(seconds), label)
        self.clipboard_clear_combo.set_active_id(str(self.preferences.clipboard_clear_seconds))
        self.clipboard_clear_combo.connect("changed", self._on_clipboard_clear_changed)
        clear_row.pack_start(self.clipboard_clear_combo, False, False, 0)
        security.pack_start(clear_row, False, False, 0)

        lock_row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        lock_caption = gtk.Label(label="Auto-lock", xalign=0)
        lock_caption.set_hexpand(True)
        lock_row.pack_start(lock_caption, True, True, 0)
        self.auto_lock_combo = gtk.ComboBoxText()
        for seconds, label in AUTO_LOCK_OPTIONS:
            self.auto_lock_combo.append(str(seconds), label)
        self.auto_lock_combo.set_active_id(str(self.preferences.auto_lock_seconds))
        self.auto_lock_combo.connect("changed", self._on_auto_lock_changed)
        lock_row.pack_start(self.auto_lock_combo, False, False, 0)
        security.pack_start(lock_row, False, False, 0)

        self.confirm_reveal_button = self._chip(
            "Confirm before reveal", self.preferences.confirm_before_reveal
        )
        self.confirm_reveal_button.set_halign(gtk.Align.START)
        self.confirm_reveal_button.connect("toggled", self._on_confirm_reveal_toggled)
        security.pack_start(self.confirm_reveal_button, False, False, 0)

        self.lock_on_open_button = self._chip(
            "Lock on open", self.preferences.lock_on_open
        )
        self.lock_on_open_button.set_halign(gtk.Align.START)
        self.lock_on_open_button.connect("toggled", self._on_lock_on_open_toggled)
        security.pack_start(self.lock_on_open_button, False, False, 0)

        self.lock_now_button = gtk.Button(label="Lock vault now")
        self.lock_now_button.get_style_context().add_class("secondary")
        self.lock_now_button.set_halign(gtk.Align.START)
        self.lock_now_button.connect("clicked", self.on_lock_now)
        security.pack_start(self.lock_now_button, False, False, 0)

        self.change_passphrase_button = gtk.Button(label="Change passphrase")
        self.change_passphrase_button.get_style_context().add_class("secondary")
        self.change_passphrase_button.set_halign(gtk.Align.START)
        self.change_passphrase_button.connect("clicked", self.on_change_passphrase)
        security.pack_start(self.change_passphrase_button, False, False, 0)
        page.pack_start(security, False, False, 0)

        files = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=10)
        files.get_style_context().add_class("settings-block")
        files_label = gtk.Label(label="VAULT FILE", xalign=0)
        files_label.get_style_context().add_class("eyebrow")
        files.pack_start(files_label, False, False, 0)
        files_hint = gtk.Label(
            label="Vault exports stay encrypted. CSV export is plaintext — keep it private.",
            xalign=0,
        )
        files_hint.set_line_wrap(True)
        files_hint.get_style_context().add_class("hint")
        files.pack_start(files_hint, False, False, 0)
        file_row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        self.export_button = gtk.Button(label="Export vault")
        self.import_button = gtk.Button(label="Import vault")
        for button in (self.export_button, self.import_button):
            button.get_style_context().add_class("secondary")
            file_row.pack_start(button, True, True, 0)
        self.export_button.connect("clicked", self.on_export_vault)
        self.import_button.connect("clicked", self.on_import_vault)
        files.pack_start(file_row, False, False, 0)
        csv_row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        self.import_csv_button = gtk.Button(label="Import CSV")
        self.export_csv_button = gtk.Button(label="Export CSV")
        for button in (self.import_csv_button, self.export_csv_button):
            button.get_style_context().add_class("secondary")
            csv_row.pack_start(button, True, True, 0)
        self.import_csv_button.connect("clicked", self.on_import_csv)
        self.export_csv_button.connect("clicked", self.on_export_csv)
        files.pack_start(csv_row, False, False, 0)
        page.pack_start(files, False, False, 0)

        transfer = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=10)
        transfer.get_style_context().add_class("settings-block")
        transfer_label = gtk.Label(label="VAULT TRANSFER", xalign=0)
        transfer_label.get_style_context().add_class("eyebrow")
        transfer.pack_start(transfer_label, False, False, 0)
        sync_hint = gtk.Label(
            label="Moves the encrypted vault on the same Wi-Fi. The passphrase stays here.",
            xalign=0,
        )
        sync_hint.set_line_wrap(True)
        sync_hint.get_style_context().add_class("hint")
        transfer.pack_start(sync_hint, False, False, 0)
        sync_row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        self.send_button = gtk.Button(label="Send vault")
        self.receive_button = gtk.Button(label="Receive vault")
        for button in (self.send_button, self.receive_button):
            button.get_style_context().add_class("secondary")
            sync_row.pack_start(button, True, True, 0)
        self.send_button.connect("clicked", self.on_send_vault)
        self.receive_button.connect("clicked", self.on_receive_vault)
        transfer.pack_start(sync_row, False, False, 0)
        self.sync_status = gtk.Label(label="", xalign=0)
        self.sync_status.set_line_wrap(True)
        self.sync_status.get_style_context().add_class("hint")
        transfer.pack_start(self.sync_status, False, False, 0)
        page.pack_start(transfer, False, False, 0)

        about = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=10)
        about.get_style_context().add_class("settings-block")
        about_label = gtk.Label(label="ABOUT", xalign=0)
        about_label.get_style_context().add_class("eyebrow")
        about.pack_start(about_label, False, False, 0)
        about_title = gtk.Label(label=f"Local Password {APP_VERSION}", xalign=0)
        about_title.get_style_context().add_class("saved-name")
        about.pack_start(about_title, False, False, 0)
        about_body = gtk.Label(
            label=(
                "A local password manager and generator for this computer. "
                "Passwords stay in an encrypted vault you unlock with a passphrase "
                "or recovery key. No account, analytics, or advertising telemetry."
            ),
            xalign=0,
        )
        about_body.set_line_wrap(True)
        about_body.get_style_context().add_class("hint")
        about.pack_start(about_body, False, False, 0)
        about_privacy = gtk.Label(
            label=(
                "Privacy: the vault stays on this device. Optional breach checks send "
                "only a short password-hash prefix to Have I Been Pwned — never the "
                "password or vault. Full text: PRIVACY.md. Limits: SECURITY.md."
            ),
            xalign=0,
        )
        about_privacy.set_line_wrap(True)
        about_privacy.get_style_context().add_class("hint")
        about.pack_start(about_privacy, False, False, 0)
        about_credit = gtk.Label(
            label=(
                "Passphrases use the EFF large wordlist, created by Joseph Bonneau "
                "and the Electronic Frontier Foundation, under CC BY 3.0 US. "
                "The EFF does not endorse this project."
            ),
            xalign=0,
        )
        about_credit.set_line_wrap(True)
        about_credit.get_style_context().add_class("hint")
        about.pack_start(about_credit, False, False, 0)
        page.pack_start(about, False, False, 0)

    def _build_manager(self, page) -> None:
        gtk = self.gtk
        self.saved_heading = gtk.Label(label="Saved", xalign=0)
        self.saved_heading.get_style_context().add_class("section-title")
        page.pack_start(self.saved_heading, False, False, 0)
        saved_lede = gtk.Label(
            label=(
                "Passwords stay masked until you show them. "
                "Flags mark weak, reused, stale, or breached ones."
            ),
            xalign=0,
        )
        saved_lede.set_line_wrap(True)
        saved_lede.get_style_context().add_class("hint")
        page.pack_start(saved_lede, False, False, 0)

        saved_actions = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        self.add_password_button = gtk.Button(label="Add password")
        self.add_password_button.get_style_context().add_class("secondary")
        self.add_password_button.connect("clicked", self.on_add_password)
        self.saved_generate_button = gtk.Button(label="Generate password")
        self.saved_generate_button.get_style_context().add_class("primary")
        self.saved_generate_button.connect("clicked", lambda *_: self.show_section("generate"))
        self.check_breaches_button = gtk.Button(label="Check breaches")
        self.check_breaches_button.get_style_context().add_class("secondary")
        self.check_breaches_button.connect("clicked", self.on_check_breaches)
        saved_actions.pack_start(self.saved_generate_button, False, False, 0)
        saved_actions.pack_start(self.add_password_button, False, False, 0)
        saved_actions.pack_start(self.check_breaches_button, False, False, 0)
        page.pack_start(saved_actions, False, False, 0)
        self.saved_actions_row = saved_actions

        self.find_entry = gtk.Entry()
        self.find_entry.set_placeholder_text("Search name, username, URL, notes, category")
        self.find_entry.connect("changed", lambda *_args: self._refresh_saved_rows())
        page.pack_start(self.find_entry, False, False, 0)

        filter_row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        self.needs_attention_only = self._chip("Needs attention", False)
        self.needs_attention_only.connect("toggled", lambda *_args: self._refresh_saved_rows())
        filter_row.pack_start(self.needs_attention_only, False, False, 0)
        self.saved_view_combo = gtk.ComboBoxText()
        self.saved_view_combo.append("all", "All")
        self.saved_view_combo.append("favorites", "Favorites")
        self.saved_view_combo.append("archived", "Archived")
        self.saved_view_combo.set_active_id("all")
        self.saved_view_combo.connect("changed", lambda *_args: self._refresh_saved_rows())
        filter_row.pack_start(self.saved_view_combo, False, False, 0)
        self.category_combo = gtk.ComboBoxText()
        self.category_combo.append("all", "All categories")
        self.category_combo.set_active_id("all")
        self._suppress_category_change = False
        self.category_combo.connect("changed", self._on_category_filter_changed)
        self.category_combo.set_hexpand(True)
        filter_row.pack_start(self.category_combo, True, True, 0)
        self.sort_combo = gtk.ComboBoxText()
        self.sort_combo.append(SAVED_SORT_NAME, "Sort: Name")
        self.sort_combo.append(SAVED_SORT_RECENT, "Sort: Recent")
        self.sort_combo.append(SAVED_SORT_CHANGED, "Sort: Changed")
        self.sort_combo.set_active_id(SAVED_SORT_NAME)
        self.saved_sort_mode = SAVED_SORT_NAME
        self._suppress_sort_change = False
        self.sort_combo.connect("changed", self._on_sort_combo_changed)
        filter_row.pack_start(self.sort_combo, False, False, 0)
        page.pack_start(filter_row, False, False, 0)
        self.filter_row = filter_row
        # One filter strip now; keep sort_row for lock/refresh show-hide paths.
        self.sort_row = filter_row

        message_row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        self.manager_message = gtk.Label(label="", xalign=0)
        self.manager_message.set_line_wrap(True)
        self.manager_message.set_hexpand(True)
        self.manager_message.get_style_context().add_class("hint")
        message_row.pack_start(self.manager_message, True, True, 0)
        self.clear_search_button = gtk.Button(label="Clear search")
        self.clear_search_button.get_style_context().add_class("secondary")
        self.clear_search_button.set_no_show_all(True)
        self.clear_search_button.hide()
        self.clear_search_button.connect("clicked", self.on_clear_search)
        message_row.pack_start(self.clear_search_button, False, False, 0)
        self.undo_remove_button = gtk.Button(label="Undo")
        self.undo_remove_button.get_style_context().add_class("secondary")
        self.undo_remove_button.set_no_show_all(True)
        self.undo_remove_button.hide()
        self.undo_remove_button.connect("clicked", self.on_undo_remove)
        message_row.pack_start(self.undo_remove_button, False, False, 0)
        page.pack_start(message_row, False, False, 0)

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
        self.removed_entry: SavedPassword | None = None
        self.showing_saved = False
        self.save_ready = False
        self.locked = False
        self.vault_key: VaultKey | None = None
        self.section = "dashboard"
        self._prepare_saved()
        self.show_section("dashboard")

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

    def set_separator(self, separator: str) -> None:
        self.separator = separator
        self._style_separator_buttons()

    def _style_separator_buttons(self) -> None:
        for value, button in self.separator_buttons.items():
            style = button.get_style_context()
            if value == self.separator:
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
            self._style_separator_buttons()
        else:
            self.word_box.hide()
        self._style_mode_buttons()

    def _generate_kwargs(self) -> dict:
        return {
            "mode": self.mode,
            "length": self.length.get_value_as_int(),
            "words": self.words.get_value_as_int(),
            "count": self.count.get_value_as_int(),
            "digits": self.digits.get_active(),
            "uppercase": self.uppercase.get_active(),
            "lowercase": self.lowercase.get_active(),
            "symbols": self.symbols.get_active(),
            "exclude_ambiguous": self.ambiguous.get_active(),
            "exclude": self.exclude_entry.get_text(),
            "separator": self.separator,
            "capitalize": self.capitalize.get_active(),
        }

    def _paint_strength(self, label: str) -> None:
        strength_style = self.strength.get_style_context()
        for name in ("very-weak", "weak", "fair", "strong", "very-strong"):
            strength_style.remove_class(name)
        key = label.casefold().replace(" ", "-")
        strength_style.add_class(key)
        meter_style = self.meter.get_style_context()
        if label in ("Strong", "Very strong"):
            meter_style.remove_class("weak")
        else:
            meter_style.add_class("weak")

    def show_section(self, section: str) -> None:
        """Show Dashboard, Generate, Saved, or Settings. Hidden pages stay hidden after show_all."""
        self._note_activity()
        if section == "create":
            section = "generate"
        if section not in ("dashboard", "generate", "saved", "settings"):
            section = "dashboard"
        self.section = section
        views = {
            "dashboard": self.dashboard_view,
            "generate": self.create_view,
            "saved": self.saved_view,
            "settings": self.settings_view,
        }
        titles = {
            "dashboard": "Dashboard",
            "generate": "Generate",
            "saved": "Saved",
            "settings": "Settings",
        }
        for name, view in views.items():
            if name == section:
                view.set_no_show_all(False)
                view.show_all()
            else:
                view.set_no_show_all(True)
                view.hide()
        self.page_title.set_text(titles[section])
        if section == "saved":
            self._refresh_saved_rows()
            self._update_lock_button()
        elif section == "generate":
            self.apply_mode()
        elif section == "dashboard":
            self._refresh_dashboard()
            self._update_lock_button()
        for button, name in (
            (self.dashboard_tab, "dashboard"),
            (self.create_tab, "generate"),
            (self.saved_tab, "saved"),
            (self.settings_tab, "settings"),
        ):
            style = button.get_style_context()
            if name == section:
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
            result = generate(**self._generate_kwargs())
        except ValueError as exc:
            self.set_note(str(exc))
            return
        self._apply_generated(result)

    def on_regenerate(self, *_args) -> None:
        if not self.current:
            return
        kwargs = self._generate_kwargs()
        kwargs["count"] = 1
        try:
            result = generate(**kwargs)
        except ValueError as exc:
            self.set_note(str(exc))
            return
        if len(self.batch) > 1:
            # Keep the batch list; replace only when single result is showing.
            pass
        self._apply_generated(result)

    def _apply_generated(self, result: Generated) -> None:
        passwords = [line for line in result.text.splitlines() if line]
        self.batch = passwords
        self.current = result.text
        self.showing_saved = False
        self.save_ready = True
        self.result_revealed = True
        self._refresh_result_display()
        if len(passwords) > 1:
            self._show_batch(passwords)
        else:
            self._show_single()
        self.strength.set_text(result.label)
        self._paint_strength(result.label)
        self.bits.set_text(result.bits_label)
        self.meter.set_fraction(result.fraction)
        self.set_note(result.note)
        self.copy_button.set_sensitive(True)
        self.save_button.set_sensitive(True)
        self.reveal_button.set_sensitive(True)
        self.regenerate_button.set_sensitive(True)
        if len(passwords) > 1:
            self.status.set_text("Name the ones you want to keep. The rest are gone when you close.")
        else:
            self.status.set_text("Name it, then save it. Otherwise it is gone when you close.")

    def _masked_text(self, text: str) -> str:
        return "\n".join("•" * max(len(line), 8) for line in text.splitlines())

    def _refresh_result_display(self) -> None:
        if not self.current:
            self.buffer.set_text("")
            self.reveal_button.set_label("Hide")
            return
        if self.result_revealed:
            self.buffer.set_text(self.current)
            self.reveal_button.set_label("Hide")
        else:
            self.buffer.set_text(self._masked_text(self.current))
            self.reveal_button.set_label("Show")

    def on_toggle_result_reveal(self, *_args) -> None:
        if not self.current:
            return
        self.result_revealed = not self.result_revealed
        self._refresh_result_display()

    def _show_single(self) -> None:
        self.batch_scroll.hide()
        self.batch_scroll.set_no_show_all(True)
        self.single_box.set_no_show_all(False)
        self.single_box.show_all()

    def _show_batch(self, passwords: list[str]) -> None:
        for child in list(self.batch_box.get_children()):
            self.batch_box.remove(child)
        for index, password in enumerate(passwords):
            self.batch_box.pack_start(self._batch_row(index, password), False, False, 0)
        self.single_box.hide()
        self.single_box.set_no_show_all(True)
        self.batch_scroll.set_no_show_all(False)
        self.batch_scroll.show_all()

    def _batch_row(self, index: int, password: str):
        gtk = self.gtk
        row = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=6)
        row.get_style_context().add_class("entry-card")
        for setter in (
            row.set_margin_top,
            row.set_margin_bottom,
            row.set_margin_start,
            row.set_margin_end,
        ):
            setter(10)
        state = {"revealed": False, "password": password}
        secret = gtk.Label(label=self._masked_text(password), xalign=0)
        secret.set_line_wrap(True)
        secret.set_selectable(False)
        secret.set_max_width_chars(42)
        secret.get_style_context().add_class("saved-name")
        bits = entry_strength_bits(password)
        tier = generator.strength_tier(bits)
        strength = gtk.Label(label=f"{tier} · about {round(bits)} bits", xalign=0)
        strength.get_style_context().add_class("strength")
        key = tier.casefold().replace(" ", "-")
        strength.get_style_context().add_class(key)
        name = gtk.Entry()
        name.set_placeholder_text("Name this one")
        name.set_max_length(MAX_NAME_LENGTH)
        note = gtk.Label(label="", xalign=0)
        note.set_line_wrap(True)
        note.get_style_context().add_class("hint")
        actions = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)

        def current_password() -> str:
            return state["password"]

        def paint_strength() -> None:
            value = entry_strength_bits(state["password"])
            label = generator.strength_tier(value)
            strength.set_text(f"{label} · about {round(value)} bits")
            style = strength.get_style_context()
            for old in (
                "very-weak",
                "weak",
                "fair",
                "strong",
                "very-strong",
            ):
                style.remove_class(old)
            style.add_class(label.casefold().replace(" ", "-"))

        def paint_secret() -> None:
            if state["revealed"]:
                secret.set_text(state["password"])
                secret.set_selectable(True)
                show.set_label("Hide")
            else:
                secret.set_text(self._masked_text(state["password"]))
                secret.set_selectable(False)
                show.set_label("Show")

        def toggle_show(*_args) -> None:
            state["revealed"] = not state["revealed"]
            paint_secret()

        def regenerate_one(*_args) -> None:
            kwargs = self._generate_kwargs()
            kwargs["count"] = 1
            try:
                result = generate(**kwargs)
            except ValueError as exc:
                note.set_text(str(exc))
                return
            fresh = result.text.splitlines()[0] if result.text else ""
            if not fresh:
                return
            state["password"] = fresh
            self.batch[index] = fresh
            self.current = "\n".join(self.batch)
            paint_secret()
            paint_strength()
            note.set_text("Regenerated.")
            self.status.set_text("Regenerated one password. Name and save the ones you want.")

        show = gtk.Button(label="Show")
        show.get_style_context().add_class("secondary")
        show.connect("clicked", toggle_show)
        copy = gtk.Button(label="Copy")
        copy.get_style_context().add_class("primary")
        copy.connect("clicked", lambda *_args: self.on_copy_text(current_password()))
        again = gtk.Button(label="Regenerate")
        again.get_style_context().add_class("secondary")
        again.connect("clicked", regenerate_one)
        save = gtk.Button(label="Save")
        save.get_style_context().add_class("secondary")
        save.connect(
            "clicked",
            lambda *_args: self.on_save_one(current_password(), name, note),
        )
        name.connect(
            "activate",
            lambda *_args: self.on_save_one(current_password(), name, note),
        )
        for button in (show, copy, again, save):
            actions.pack_start(button, True, True, 0)
        row.pack_start(secret, False, False, 0)
        row.pack_start(strength, False, False, 0)
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
        self.on_copy_text(self.current)

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

    def _on_category_filter_changed(self, *_args) -> None:
        if self._suppress_category_change:
            return
        self._refresh_saved_rows()

    def _on_sort_combo_changed(self, *_args) -> None:
        if self._suppress_sort_change:
            return
        active = self.sort_combo.get_active_id()
        if active is None or active not in SAVED_SORT_MODES:
            return
        self.saved_sort_mode = active
        self._refresh_saved_rows()

    def _refresh_category_filter(self) -> None:
        current = self.category_combo.get_active_id() or "all"
        categories = sorted(
            {item.category for item in self.saved if item.category},
            key=str.casefold,
        )
        self._suppress_category_change = True
        try:
            self.category_combo.remove_all()
            self.category_combo.append("all", "All categories")
            for category in categories:
                self.category_combo.append(category, category)
            if current != "all" and current in categories:
                self.category_combo.set_active_id(current)
            else:
                self.category_combo.set_active_id("all")
        finally:
            self._suppress_category_change = False

    def _refresh_saved_rows(self) -> None:
        for child in list(self.saved_box.get_children()):
            self.saved_box.remove(child)
        query = self.find_entry.get_text()
        if self.locked and self.vault_key is None:
            self.find_entry.hide()
            self.filter_row.hide()
            self.sort_row.hide()
            self.saved_actions_row.hide()
            self.saved_scroll.hide()
            self._hide_clear_search()
            self.saved_heading.set_text("Saved")
            self.saved_heading.show()
            self.manager_message.set_text(
                "Saved passwords are locked. The passphrase or the recovery key opens all of them. "
                + PASSPHRASE_LOSS_WARNING
            )
            self.manager_message.show()
            return
        self.find_entry.show()
        self.filter_row.show()
        self.sort_row.show()
        self.saved_actions_row.show()
        if not self.saved:
            self.saved_scroll.hide()
            self._hide_clear_search()
            self.saved_heading.set_text("Saved")
            self.saved_heading.show()
            self.manager_message.set_text(
                "Nothing saved yet. Generate a password, or Add password for an account you already use."
            )
            self.manager_message.show()
            return
        self._refresh_category_filter()
        category = self.category_combo.get_active_id() or "all"
        view = self.saved_view_combo.get_active_id() or "all"
        favorites_only = view == "favorites"
        archived_only = view == "archived"
        attention_only = self.needs_attention_only.get_active()
        pool = [item for item in self.saved if item.archived] if archived_only else active_saved_entries(self.saved)
        matches = [
            item
            for item in pool
            if entry_matches(item, query)
            and (not favorites_only or item.favorite)
            and (
                not attention_only
                or entry_needs_attention(item, pool, breach_counts=self.breach_counts)
            )
            and (category == "all" or item.category == category)
        ]
        matches = sorted_saved_entries(
            matches,
            self.saved_sort_mode,
            all_items=pool,
            breach_counts=self.breach_counts,
        )
        active = active_saved_entries(self.saved)
        archived_count = len(self.saved) - len(active)
        weak_count, reuse_count, stale_count, breached_count, _attention = password_health_summary(
            self.saved, breach_counts=self.breach_counts
        )
        if archived_only:
            count = archived_count
            heading = "1 archived" if count == 1 else f"{count} archived"
        else:
            count = len(active)
            heading = "1 saved" if count == 1 else f"{count} saved"
            if weak_count:
                heading += f" · {weak_count} weak"
            if reuse_count:
                heading += f" · {reuse_count} reused"
            if stale_count:
                heading += f" · {stale_count} stale"
            if breached_count:
                heading += f" · {breached_count} breached"
            if archived_count:
                heading += f" · {archived_count} archived"
        self.saved_heading.set_text(heading)
        self.saved_heading.show()
        if not matches:
            self.saved_scroll.hide()
            if archived_only:
                self.manager_message.set_text("No archived password matches that search.")
            elif attention_only:
                self.manager_message.set_text("No saved password needs attention for that filter.")
            else:
                self.manager_message.set_text("No saved password matches that search.")
            self.manager_message.show()
            if query.strip():
                self._show_clear_search()
            else:
                self._hide_clear_search()
            return
        self.manager_message.set_text("")
        self.manager_message.hide()
        self._hide_clear_search()
        self.saved_scroll.show()
        for item in matches:
            self.saved_box.pack_start(self._saved_row(item), False, False, 0)
        self.saved_box.show_all()

    def _menu_action(self, menu, label: str, callback) -> None:
        item = self.gtk.MenuItem(label=label)
        item.connect("activate", callback)
        menu.append(item)

    def _saved_row_more_menu(self, item: SavedPassword):
        gtk = self.gtk
        menu = gtk.Menu()
        login_text = login_copy_text(item)
        if login_text:
            self._menu_action(
                menu,
                "Copy login",
                lambda *_args, entry=item, text=login_text: self.on_copy_saved_secret(
                    entry, text
                ),
            )
            self._menu_action(
                menu,
                "Copy username",
                lambda *_args, entry=item: self.on_copy_saved_secret(entry, entry.username),
            )
        for label, value in optional_copy_fields(item):
            self._menu_action(
                menu,
                label,
                lambda *_args, entry=item, text=value: self.on_copy_saved_secret(entry, text),
            )
            if label == "Copy URL" and browseable_url(item.url):
                self._menu_action(
                    menu,
                    "Open URL",
                    lambda *_args, entry=item: self.on_open_url(entry),
                )
        self._menu_action(
            menu,
            "Check breach",
            lambda *_args, entry=item: self.on_check_breach_one(entry),
        )
        if item.history:
            self._menu_action(
                menu,
                f"Previous ({len(item.history)})",
                lambda *_args, entry=item: self.on_previous_passwords(entry),
            )
        self._menu_action(
            menu,
            "Unfavorite" if item.favorite else "Favorite",
            lambda *_args, entry=item: self.on_toggle_favorite(entry),
        )
        self._menu_action(
            menu,
            "Unarchive" if item.archived else "Archive",
            lambda *_args, entry=item: self.on_toggle_archived(entry),
        )
        self._menu_action(
            menu,
            "Duplicate",
            lambda *_args, entry=item: self.on_duplicate_entry(entry),
        )
        self._menu_action(
            menu,
            "Rename",
            lambda *_args, entry=item: self.on_rename_entry(entry),
        )
        self._menu_action(
            menu,
            "Category",
            lambda *_args, entry=item: self.on_set_category(entry),
        )
        self._menu_action(
            menu,
            "Username",
            lambda *_args, entry=item: self.on_set_username(entry),
        )
        self._menu_action(
            menu,
            "URL",
            lambda *_args, entry=item: self.on_set_url(entry),
        )
        self._menu_action(
            menu,
            "Notes",
            lambda *_args, entry=item: self.on_set_notes(entry),
        )
        self._menu_action(
            menu,
            "Edit",
            lambda *_args, entry=item: self.on_edit_entry(entry),
        )
        self._menu_action(
            menu,
            "Remove",
            lambda *_args, label=item.name: self.on_remove(label),
        )
        menu.show_all()
        return menu

    def _saved_row(self, item: SavedPassword):
        gtk = self.gtk
        shell = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=0)
        shell.get_style_context().add_class("entry-card")
        row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        for setter in (
            row.set_margin_top,
            row.set_margin_bottom,
            row.set_margin_start,
            row.set_margin_end,
        ):
            setter(10)
        text = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=2)
        title = item.name
        if item.favorite:
            title = f"★ {title}"
        if item.archived:
            title = f"{title} (archived)"
        name = gtk.Label(label=title, xalign=0)
        name.set_halign(gtk.Align.START)
        name.get_style_context().add_class("saved-name")
        meta_bits = [part for part in (item.username, item.category, item.url) if part]
        text.pack_start(name, False, False, 0)
        if meta_bits:
            meta = gtk.Label(label=" · ".join(meta_bits), xalign=0)
            meta.set_line_wrap(True)
            meta.set_halign(gtk.Align.START)
            meta.get_style_context().add_class("hint")
            text.pack_start(meta, False, False, 0)
        dates = entry_dates_label(item)
        if dates:
            when = gtk.Label(label=dates, xalign=0)
            when.set_halign(gtk.Align.START)
            when.get_style_context().add_class("hint")
            text.pack_start(when, False, False, 0)
        used = gtk.Label(label=last_used_label(item), xalign=0)
        used.set_halign(gtk.Align.START)
        used.get_style_context().add_class("hint")
        text.pack_start(used, False, False, 0)
        for warning in (
            breach_warning_for(
                self.breach_counts.get(password_sha1_hex(item.password), 0)
            ),
            strength_warning_for(item),
            reuse_warning_for(item, self.saved),
            stale_warning_for(item),
        ):
            if not warning:
                continue
            warn = gtk.Label(label=warning, xalign=0)
            warn.set_line_wrap(True)
            warn.set_halign(gtk.Align.START)
            warn.get_style_context().add_class("danger")
            text.pack_start(warn, False, False, 0)
        shown = item.name in self.revealed_names
        secret = gtk.Label(label=item.password if shown else "••••••••••••", xalign=0)
        secret.set_line_wrap(True)
        secret.set_selectable(shown)
        secret.set_halign(gtk.Align.START)
        secret.get_style_context().add_class("hint")
        text.pack_start(secret, False, False, 0)
        if item.notes.strip():
            notes = gtk.Label(label=item.notes, xalign=0)
            notes.set_line_wrap(True)
            notes.set_halign(gtk.Align.START)
            notes.get_style_context().add_class("hint")
            text.pack_start(notes, False, False, 0)
        text.set_hexpand(True)
        actions = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=6)
        show = gtk.Button(label="Hide" if shown else "Show")
        show.get_style_context().add_class("secondary")
        show.connect("clicked", lambda *_args, label=item.name: self.on_toggle_reveal(label))
        copy = gtk.Button(label="Copy password")
        copy.get_style_context().add_class("primary")
        copy.connect(
            "clicked",
            lambda *_args, entry=item: self.on_copy_saved_secret(entry, entry.password),
        )
        replace_btn = gtk.Button(label="Replace")
        if entry_needs_attention(item, self.saved, breach_counts=self.breach_counts):
            replace_btn.get_style_context().add_class("primary")
            copy.get_style_context().remove_class("primary")
            copy.get_style_context().add_class("secondary")
        else:
            replace_btn.get_style_context().add_class("secondary")
        replace_btn.connect("clicked", lambda *_args, entry=item: self.on_replace_password(entry))
        more = gtk.MenuButton(label="More")
        more.get_style_context().add_class("secondary")
        more.set_popup(self._saved_row_more_menu(item))
        actions.pack_start(show, False, False, 0)
        actions.pack_start(copy, False, False, 0)
        actions.pack_start(replace_btn, False, False, 0)
        actions.pack_start(more, False, False, 0)
        row.pack_start(text, True, True, 0)
        row.pack_start(actions, False, False, 0)
        shell.pack_start(row, False, False, 0)
        return shell

    def on_open_url(self, item: SavedPassword) -> None:
        self._note_activity()
        if open_entry_url(item.url):
            message = f"Opening {item.url.strip()}."
        else:
            message = "That URL could not be opened."
        self.status.set_text(message)
        if self.section == "saved":
            self.manager_message.set_text(message)
            self.manager_message.show()

    def on_toggle_favorite(self, item: SavedPassword) -> None:
        """Star or clear Favorite on a Saved row without opening Edit."""
        self._note_activity()
        if self.vault_key is None:
            self.status.set_text("Saved passwords are locked.")
            return
        current = next((entry for entry in self.saved if entry.name == item.name), None)
        if current is None:
            self.status.set_text("That saved password is gone.")
            return
        try:
            updated = toggle_entry_favorite(self.saved, current)
            write_vault(self.vault_key, updated)
        except (OSError, ValueError) as exc:
            self.status.set_text(str(exc) or "Could not update Favorite.")
            return
        self.saved = updated
        stamped = next(entry for entry in updated if entry.name == current.name)
        message = f"Favorited {stamped.name}." if stamped.favorite else f"Cleared favorite on {stamped.name}."
        self.status.set_text(message)
        if self.section == "saved":
            self.manager_message.set_text(message)
            self.manager_message.show()
            self._refresh_saved_rows()
        elif self.section == "dashboard":
            self._refresh_dashboard()

    def on_toggle_archived(self, item: SavedPassword) -> None:
        """Archive or unarchive a Saved row without opening Edit."""
        self._note_activity()
        if self.vault_key is None:
            self.status.set_text("Saved passwords are locked.")
            return
        current = next((entry for entry in self.saved if entry.name == item.name), None)
        if current is None:
            self.status.set_text("That saved password is gone.")
            return
        try:
            updated = toggle_entry_archived(self.saved, current)
            write_vault(self.vault_key, updated)
        except (OSError, ValueError) as exc:
            self.status.set_text(str(exc) or "Could not update Archive.")
            return
        self.saved = updated
        stamped = next(entry for entry in updated if entry.name == current.name)
        message = f"Archived {stamped.name}." if stamped.archived else f"Unarchived {stamped.name}."
        self.status.set_text(message)
        if self.section == "saved":
            self.manager_message.set_text(message)
            self.manager_message.show()
            self._refresh_saved_rows()
        elif self.section == "dashboard":
            self._refresh_dashboard()

    def on_duplicate_entry(self, item: SavedPassword) -> None:
        """Copy a Saved row under a new name ending in (copy)."""
        self._note_activity()
        if self.vault_key is None:
            self.status.set_text("Saved passwords are locked.")
            return
        current = next((entry for entry in self.saved if entry.name == item.name), None)
        if current is None:
            self.status.set_text("That saved password is gone.")
            return
        try:
            updated = duplicate_entry(self.saved, current)
            write_vault(self.vault_key, updated)
        except (OSError, ValueError) as exc:
            self.status.set_text(str(exc) or "Could not duplicate that entry.")
            return
        self.saved = updated
        fresh = updated[0]
        message = f"Duplicated as {fresh.name}."
        self.status.set_text(message)
        if self.section == "saved":
            self.manager_message.set_text(message)
            self.manager_message.show()
            self._refresh_saved_rows()
        elif self.section == "dashboard":
            self._refresh_dashboard()

    def on_rename_entry(self, item: SavedPassword) -> None:
        """Change only the name on a Saved row without opening Edit."""
        self._note_activity()
        if self.vault_key is None:
            self.status.set_text("Saved passwords are locked.")
            return
        current = next((entry for entry in self.saved if entry.name == item.name), None)
        if current is None:
            self.status.set_text("That saved password is gone.")
            return
        new_name = self._rename_entry_dialog(current)
        if new_name is None:
            return
        if new_name == current.name:
            message = f"{current.name} already uses that name."
            self.status.set_text(message)
            if self.section == "saved":
                self.manager_message.set_text(message)
                self.manager_message.show()
            return
        try:
            updated = rename_entry(self.saved, current, new_name)
            write_vault(self.vault_key, updated)
        except ValueError as exc:
            self.status.set_text(str(exc))
            if self.section == "saved":
                self.manager_message.set_text(str(exc))
                self.manager_message.show()
            return
        except OSError:
            message = "Could not rename that entry."
            self.status.set_text(message)
            if self.section == "saved":
                self.manager_message.set_text(message)
                self.manager_message.show()
            return
        stamped = next(entry for entry in updated if entry.name == new_name)
        if current.name in self.revealed_names and stamped.name != current.name:
            self.revealed_names.discard(current.name)
            self.revealed_names.add(stamped.name)
        self.saved = updated
        message = f"Renamed to {stamped.name}."
        self.status.set_text(message)
        if self.section == "saved":
            self.manager_message.set_text(message)
            self.manager_message.show()
            self._refresh_saved_rows()
        elif self.section == "dashboard":
            self._refresh_dashboard()

    def _rename_entry_dialog(self, item: SavedPassword) -> str | None:
        gtk = self.gtk
        dialog = gtk.Dialog(title="Rename saved password", transient_for=self.window, modal=True)
        self._match_dialog(dialog)
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        save = dialog.add_button("Rename", gtk.ResponseType.OK)
        save.get_style_context().add_class("primary")
        dialog.set_default_response(gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_spacing(8)
        for setter in (
            content.set_margin_top,
            content.set_margin_bottom,
            content.set_margin_start,
            content.set_margin_end,
        ):
            setter(16)
        hint = gtk.Label(label=f'Rename "{item.name}". Other fields stay the same.', xalign=0)
        hint.set_line_wrap(True)
        hint.get_style_context().add_class("hint")
        content.pack_start(hint, False, False, 0)
        caption = gtk.Label(label="Name", xalign=0)
        content.pack_start(caption, False, False, 0)
        name_entry = gtk.Entry()
        name_entry.set_text(item.name)
        name_entry.set_activates_default(True)
        content.pack_start(name_entry, False, False, 0)
        problem = gtk.Label(label="", xalign=0)
        problem.set_line_wrap(True)
        problem.get_style_context().add_class("danger")
        content.pack_start(problem, False, False, 0)
        dialog.show_all()
        name_entry.grab_focus()
        name_entry.select_region(0, -1)
        while True:
            response = dialog.run()
            if response != gtk.ResponseType.OK:
                dialog.destroy()
                return None
            try:
                label = clean_name(name_entry.get_text())
            except ValueError as exc:
                problem.set_text(str(exc))
                problem.show()
                continue
            dialog.destroy()
            return label

    def on_set_category(self, item: SavedPassword) -> None:
        """Set or clear category on a Saved row without opening Edit."""
        self._note_activity()
        if self.vault_key is None:
            self.status.set_text("Saved passwords are locked.")
            return
        current = next((entry for entry in self.saved if entry.name == item.name), None)
        if current is None:
            self.status.set_text("That saved password is gone.")
            return
        new_category = self._category_entry_dialog(current)
        if new_category is None:
            return
        if new_category == current.category:
            if current.category:
                message = f"{current.name} already uses that category."
            else:
                message = f"{current.name} has no category."
            self.status.set_text(message)
            if self.section == "saved":
                self.manager_message.set_text(message)
                self.manager_message.show()
            return
        try:
            updated = set_entry_category(self.saved, current, new_category)
            write_vault(self.vault_key, updated)
        except ValueError as exc:
            self.status.set_text(str(exc))
            if self.section == "saved":
                self.manager_message.set_text(str(exc))
                self.manager_message.show()
            return
        except OSError:
            message = "Could not update that category."
            self.status.set_text(message)
            if self.section == "saved":
                self.manager_message.set_text(message)
                self.manager_message.show()
            return
        self.saved = updated
        stamped = next(entry for entry in updated if entry.name == current.name)
        if stamped.category:
            message = f"Set category on {stamped.name} to {stamped.category}."
        else:
            message = f"Cleared category on {stamped.name}."
        self.status.set_text(message)
        if self.section == "saved":
            self.manager_message.set_text(message)
            self.manager_message.show()
            self._refresh_saved_rows()
        elif self.section == "dashboard":
            self._refresh_dashboard()

    def _category_entry_dialog(self, item: SavedPassword) -> str | None:
        gtk = self.gtk
        dialog = gtk.Dialog(title="Category", transient_for=self.window, modal=True)
        self._match_dialog(dialog)
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        save = dialog.add_button("Save", gtk.ResponseType.OK)
        save.get_style_context().add_class("primary")
        dialog.set_default_response(gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_spacing(8)
        for setter in (
            content.set_margin_top,
            content.set_margin_bottom,
            content.set_margin_start,
            content.set_margin_end,
        ):
            setter(16)
        hint = gtk.Label(
            label=(
                f'Category for "{item.name}". Pick a preset or type your own. '
                "Leave blank to clear. Other fields stay the same."
            ),
            xalign=0,
        )
        hint.set_line_wrap(True)
        hint.get_style_context().add_class("hint")
        content.pack_start(hint, False, False, 0)
        caption = gtk.Label(label="Category", xalign=0)
        content.pack_start(caption, False, False, 0)
        category_entry = gtk.Entry()
        category_entry.set_text(item.category)
        category_entry.set_activates_default(True)
        content.pack_start(category_entry, False, False, 0)
        presets = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=6)
        presets.set_homogeneous(False)
        for label in category_choices(self.saved):
            chip = gtk.Button(label=label)
            chip.get_style_context().add_class("secondary")
            chip.connect(
                "clicked",
                lambda *_args, chosen=label: category_entry.set_text(chosen),
            )
            presets.pack_start(chip, False, False, 0)
        scroller = gtk.ScrolledWindow()
        scroller.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.NEVER)
        scroller.add(presets)
        content.pack_start(scroller, False, False, 0)
        problem = gtk.Label(label="", xalign=0)
        problem.set_line_wrap(True)
        problem.get_style_context().add_class("danger")
        content.pack_start(problem, False, False, 0)
        dialog.show_all()
        category_entry.grab_focus()
        category_entry.select_region(0, -1)
        while True:
            response = dialog.run()
            if response != gtk.ResponseType.OK:
                dialog.destroy()
                return None
            try:
                label = clean_category(category_entry.get_text())
            except ValueError as exc:
                problem.set_text(str(exc))
                problem.show()
                continue
            dialog.destroy()
            return label

    def on_set_username(self, item: SavedPassword) -> None:
        """Set or clear username on a Saved row without opening Edit."""
        self._note_activity()
        if self.vault_key is None:
            self.status.set_text("Saved passwords are locked.")
            return
        current = next((entry for entry in self.saved if entry.name == item.name), None)
        if current is None:
            self.status.set_text("That saved password is gone.")
            return
        new_username = self._username_entry_dialog(current)
        if new_username is None:
            return
        if new_username == current.username:
            if current.username:
                message = f"{current.name} already uses that username."
            else:
                message = f"{current.name} has no username."
            self.status.set_text(message)
            if self.section == "saved":
                self.manager_message.set_text(message)
                self.manager_message.show()
            return
        try:
            updated = set_entry_username(self.saved, current, new_username)
            write_vault(self.vault_key, updated)
        except ValueError as exc:
            self.status.set_text(str(exc))
            if self.section == "saved":
                self.manager_message.set_text(str(exc))
                self.manager_message.show()
            return
        except OSError:
            message = "Could not update that username."
            self.status.set_text(message)
            if self.section == "saved":
                self.manager_message.set_text(message)
                self.manager_message.show()
            return
        self.saved = updated
        stamped = next(entry for entry in updated if entry.name == current.name)
        if stamped.username:
            message = f"Set username on {stamped.name} to {stamped.username}."
        else:
            message = f"Cleared username on {stamped.name}."
        self.status.set_text(message)
        if self.section == "saved":
            self.manager_message.set_text(message)
            self.manager_message.show()
            self._refresh_saved_rows()
        elif self.section == "dashboard":
            self._refresh_dashboard()

    def _username_entry_dialog(self, item: SavedPassword) -> str | None:
        gtk = self.gtk
        dialog = gtk.Dialog(title="Username", transient_for=self.window, modal=True)
        self._match_dialog(dialog)
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        save = dialog.add_button("Save", gtk.ResponseType.OK)
        save.get_style_context().add_class("primary")
        dialog.set_default_response(gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_spacing(8)
        for setter in (
            content.set_margin_top,
            content.set_margin_bottom,
            content.set_margin_start,
            content.set_margin_end,
        ):
            setter(16)
        hint = gtk.Label(
            label=f'Username for "{item.name}". Leave blank to clear. Other fields stay the same.',
            xalign=0,
        )
        hint.set_line_wrap(True)
        hint.get_style_context().add_class("hint")
        content.pack_start(hint, False, False, 0)
        caption = gtk.Label(label="Username", xalign=0)
        content.pack_start(caption, False, False, 0)
        username_entry = gtk.Entry()
        username_entry.set_text(item.username)
        username_entry.set_activates_default(True)
        content.pack_start(username_entry, False, False, 0)
        problem = gtk.Label(label="", xalign=0)
        problem.set_line_wrap(True)
        problem.get_style_context().add_class("danger")
        content.pack_start(problem, False, False, 0)
        dialog.show_all()
        username_entry.grab_focus()
        username_entry.select_region(0, -1)
        while True:
            response = dialog.run()
            if response != gtk.ResponseType.OK:
                dialog.destroy()
                return None
            try:
                label = clean_username(username_entry.get_text())
            except ValueError as exc:
                problem.set_text(str(exc))
                problem.show()
                continue
            dialog.destroy()
            return label

    def on_set_url(self, item: SavedPassword) -> None:
        """Set or clear website URL on a Saved row without opening Edit."""
        self._note_activity()
        if self.vault_key is None:
            self.status.set_text("Saved passwords are locked.")
            return
        current = next((entry for entry in self.saved if entry.name == item.name), None)
        if current is None:
            self.status.set_text("That saved password is gone.")
            return
        new_url = self._url_entry_dialog(current)
        if new_url is None:
            return
        if new_url == current.url:
            if current.url:
                message = f"{current.name} already uses that URL."
            else:
                message = f"{current.name} has no URL."
            self.status.set_text(message)
            if self.section == "saved":
                self.manager_message.set_text(message)
                self.manager_message.show()
            return
        try:
            updated = set_entry_url(self.saved, current, new_url)
            write_vault(self.vault_key, updated)
        except ValueError as exc:
            self.status.set_text(str(exc))
            if self.section == "saved":
                self.manager_message.set_text(str(exc))
                self.manager_message.show()
            return
        except OSError:
            message = "Could not update that URL."
            self.status.set_text(message)
            if self.section == "saved":
                self.manager_message.set_text(message)
                self.manager_message.show()
            return
        self.saved = updated
        stamped = next(entry for entry in updated if entry.name == current.name)
        if stamped.url:
            message = f"Set URL on {stamped.name}."
        else:
            message = f"Cleared URL on {stamped.name}."
        self.status.set_text(message)
        if self.section == "saved":
            self.manager_message.set_text(message)
            self.manager_message.show()
            self._refresh_saved_rows()
        elif self.section == "dashboard":
            self._refresh_dashboard()

    def _url_entry_dialog(self, item: SavedPassword) -> str | None:
        gtk = self.gtk
        dialog = gtk.Dialog(title="Website URL", transient_for=self.window, modal=True)
        self._match_dialog(dialog)
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        save = dialog.add_button("Save", gtk.ResponseType.OK)
        save.get_style_context().add_class("primary")
        dialog.set_default_response(gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_spacing(8)
        for setter in (
            content.set_margin_top,
            content.set_margin_bottom,
            content.set_margin_start,
            content.set_margin_end,
        ):
            setter(16)
        hint = gtk.Label(
            label=f'Website for "{item.name}". Leave blank to clear. Other fields stay the same.',
            xalign=0,
        )
        hint.set_line_wrap(True)
        hint.get_style_context().add_class("hint")
        content.pack_start(hint, False, False, 0)
        caption = gtk.Label(label="URL", xalign=0)
        content.pack_start(caption, False, False, 0)
        url_entry = gtk.Entry()
        url_entry.set_text(item.url)
        url_entry.set_activates_default(True)
        url_entry.set_placeholder_text("https://example.com")
        content.pack_start(url_entry, False, False, 0)
        problem = gtk.Label(label="", xalign=0)
        problem.set_line_wrap(True)
        problem.get_style_context().add_class("danger")
        content.pack_start(problem, False, False, 0)
        dialog.show_all()
        url_entry.grab_focus()
        url_entry.select_region(0, -1)
        while True:
            response = dialog.run()
            if response != gtk.ResponseType.OK:
                dialog.destroy()
                return None
            try:
                label = clean_url(url_entry.get_text())
            except ValueError as exc:
                problem.set_text(str(exc))
                problem.show()
                continue
            dialog.destroy()
            return label

    def on_set_notes(self, item: SavedPassword) -> None:
        """Set or clear notes on a Saved row without opening Edit."""
        self._note_activity()
        if self.vault_key is None:
            self.status.set_text("Saved passwords are locked.")
            return
        current = next((entry for entry in self.saved if entry.name == item.name), None)
        if current is None:
            self.status.set_text("That saved password is gone.")
            return
        new_notes = self._notes_entry_dialog(current)
        if new_notes is None:
            return
        if new_notes == current.notes:
            if current.notes:
                message = f"{current.name} already uses those notes."
            else:
                message = f"{current.name} has no notes."
            self.status.set_text(message)
            if self.section == "saved":
                self.manager_message.set_text(message)
                self.manager_message.show()
            return
        try:
            updated = set_entry_notes(self.saved, current, new_notes)
            write_vault(self.vault_key, updated)
        except ValueError as exc:
            self.status.set_text(str(exc))
            if self.section == "saved":
                self.manager_message.set_text(str(exc))
                self.manager_message.show()
            return
        except OSError:
            message = "Could not update those notes."
            self.status.set_text(message)
            if self.section == "saved":
                self.manager_message.set_text(message)
                self.manager_message.show()
            return
        self.saved = updated
        stamped = next(entry for entry in updated if entry.name == current.name)
        if stamped.notes:
            message = f"Updated notes on {stamped.name}."
        else:
            message = f"Cleared notes on {stamped.name}."
        self.status.set_text(message)
        if self.section == "saved":
            self.manager_message.set_text(message)
            self.manager_message.show()
            self._refresh_saved_rows()
        elif self.section == "dashboard":
            self._refresh_dashboard()

    def _notes_entry_dialog(self, item: SavedPassword) -> str | None:
        gtk = self.gtk
        dialog = gtk.Dialog(title="Notes", transient_for=self.window, modal=True)
        self._match_dialog(dialog)
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        save = dialog.add_button("Save", gtk.ResponseType.OK)
        save.get_style_context().add_class("primary")
        dialog.set_default_response(gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_spacing(8)
        for setter in (
            content.set_margin_top,
            content.set_margin_bottom,
            content.set_margin_start,
            content.set_margin_end,
        ):
            setter(16)
        hint = gtk.Label(
            label=(
                f'Notes for "{item.name}". Leave blank to clear. '
                "Notes do not reveal the password. Other fields stay the same."
            ),
            xalign=0,
        )
        hint.set_line_wrap(True)
        hint.get_style_context().add_class("hint")
        content.pack_start(hint, False, False, 0)
        caption = gtk.Label(label="Notes", xalign=0)
        content.pack_start(caption, False, False, 0)
        view = gtk.TextView()
        view.set_wrap_mode(gtk.WrapMode.WORD_CHAR)
        view.get_buffer().set_text(item.notes)
        view.set_size_request(-1, 96)
        content.pack_start(view, False, False, 0)
        problem = gtk.Label(label="", xalign=0)
        problem.set_line_wrap(True)
        problem.get_style_context().add_class("danger")
        content.pack_start(problem, False, False, 0)
        dialog.show_all()
        view.grab_focus()
        while True:
            response = dialog.run()
            if response != gtk.ResponseType.OK:
                dialog.destroy()
                return None
            buffer = view.get_buffer()
            text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
            try:
                label = clean_notes(text)
            except ValueError as exc:
                problem.set_text(str(exc))
                problem.show()
                continue
            dialog.destroy()
            return label

    def _confirm_breach_check(self, *, one: bool) -> bool:
        gtk = self.gtk
        title = "Check one password for breaches?" if one else "Check saved passwords for breaches?"
        dialog = gtk.Dialog(title=title, transient_for=self.window, modal=True)
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        dialog.add_button("Check", gtk.ResponseType.OK)
        dialog.set_default_response(gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_spacing(10)
        for setter in (
            content.set_margin_top,
            content.set_margin_bottom,
            content.set_margin_start,
            content.set_margin_end,
        ):
            setter(16)
        body = gtk.Label(
            label=(
                "This asks Have I Been Pwned whether a password appears in known leaks. "
                "Only the first five characters of a SHA-1 hash leave this computer — "
                "never the password, the full hash, or your vault. "
                "Results stay in this session until you lock or check again."
            ),
            xalign=0,
        )
        body.set_line_wrap(True)
        body.set_max_width_chars(52)
        content.pack_start(body, False, False, 0)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        return response == gtk.ResponseType.OK

    def on_check_breaches(self, *_args) -> None:
        self._note_activity()
        if self.vault_key is None:
            self.status.set_text("Unlock saved passwords before checking for breaches.")
            return
        if self._breach_check_running:
            self.status.set_text("A breach check is already running.")
            return
        active = active_saved_entries(self.saved)
        if not active:
            self.status.set_text("Nothing saved to check yet.")
            return
        if not self._confirm_breach_check(one=False):
            return
        passwords = [item.password for item in active]
        self._start_breach_check(passwords)

    def on_check_breach_one(self, item: SavedPassword) -> None:
        self._note_activity()
        if self.vault_key is None:
            self.status.set_text("Unlock saved passwords before checking for breaches.")
            return
        if self._breach_check_running:
            self.status.set_text("A breach check is already running.")
            return
        if not self._confirm_breach_check(one=True):
            return
        self._start_breach_check([item.password], focus_name=item.name)

    def _start_breach_check(
        self, passwords: list[str], *, focus_name: str | None = None
    ) -> None:
        self._breach_check_running = True
        self.check_breaches_button.set_sensitive(False)
        self.status.set_text("Checking for breaches…")
        if self.section == "saved":
            self.manager_message.set_text("Checking for breaches…")
            self.manager_message.show()

        def worker() -> None:
            from gi.repository import GLib

            try:
                results = check_passwords_pwned(passwords)
                GLib.idle_add(self._breach_check_finished, results, None, focus_name)
            except ValueError as exc:
                GLib.idle_add(self._breach_check_finished, None, str(exc), focus_name)
            except Exception:
                GLib.idle_add(
                    self._breach_check_finished,
                    None,
                    "Could not finish the breach check.",
                    focus_name,
                )

        threading.Thread(target=worker, daemon=True).start()

    def _breach_check_finished(
        self,
        results: dict[str, int] | None,
        error: str | None,
        focus_name: str | None,
    ) -> bool:
        self._breach_check_running = False
        self.check_breaches_button.set_sensitive(True)
        if error:
            self.status.set_text(error)
            if self.section == "saved":
                self.manager_message.set_text(error)
                self.manager_message.show()
            return False
        assert results is not None
        self.breach_counts.update(results)
        hit_names = [
            item.name
            for item in active_saved_entries(self.saved)
            if self.breach_counts.get(password_sha1_hex(item.password), 0) > 0
        ]
        checked = len(results)
        hits = sum(1 for count in results.values() if count > 0)
        if focus_name is not None:
            digest = next(iter(results))
            count = results[digest]
            if count > 0:
                message = f"{focus_name}: {breach_warning_for(count)}"
            else:
                message = f"{focus_name}: not found in known breaches."
        elif hits == 0:
            message = (
                f"Checked {checked} distinct password{'s' if checked != 1 else ''}. "
                "None were found in known breaches."
            )
        else:
            sample = ", ".join(hit_names[:5])
            if len(hit_names) > 5:
                sample += "…"
            named = f" ({sample})" if hit_names else ""
            message = (
                f"Checked {checked} distinct password{'s' if checked != 1 else ''}. "
                f"{hits} found in known breaches{named}. Replace those passwords."
            )
        self.status.set_text(message)
        self._refresh_saved_rows()
        if self.section == "dashboard":
            self._refresh_dashboard()
        if self.section == "saved":
            self.manager_message.set_text(message)
            self.manager_message.show()
        return False

    def on_replace_password(self, item: SavedPassword) -> None:
        self._note_activity()
        if self.vault_key is None:
            self.status.set_text("Saved passwords are locked.")
            return
        if not self._confirm_replace_password(item):
            return
        old_digest = password_sha1_hex(item.password)
        fresh = strong_replacement_password()
        try:
            updated = replace_entry_password(self.saved, item, fresh)
            write_vault(self.vault_key, updated)
        except ValueError as exc:
            self.status.set_text(str(exc))
            if self.section == "saved":
                self.manager_message.set_text(str(exc))
                self.manager_message.show()
            return
        except OSError:
            message = "Could not save the new password."
            self.status.set_text(message)
            if self.section == "saved":
                self.manager_message.set_text(message)
                self.manager_message.show()
            return
        self.breach_counts.pop(old_digest, None)
        self.saved = updated
        self.revealed_names.add(item.name)
        self._refresh_saved_rows()
        if self.section == "dashboard":
            self._refresh_dashboard()
        self.on_copy_text(fresh)
        seconds = self.preferences.clipboard_clear_seconds
        if seconds:
            message = (
                f"Replaced the password for {item.name} and copied it. "
                f"The old one is under Previous. Clipboard clears in {seconds} seconds."
            )
        else:
            message = (
                f"Replaced the password for {item.name} and copied it. "
                "The old one is under Previous."
            )
        self.status.set_text(message)
        if self.section == "saved":
            self.manager_message.set_text(message)
            self.manager_message.show()

    def on_previous_passwords(self, item: SavedPassword) -> None:
        self._note_activity()
        if self.vault_key is None:
            self.status.set_text("Saved passwords are locked.")
            return
        if not item.history:
            self.status.set_text("There is no previous password for that entry.")
            return
        gtk = self.gtk
        dialog = gtk.Dialog(title="Previous passwords", transient_for=self.window, modal=True)
        self._match_dialog(dialog)
        dialog.add_button("Close", gtk.ResponseType.CLOSE)
        content = dialog.get_content_area()
        content.set_spacing(10)
        for setter in (
            content.set_margin_top,
            content.set_margin_bottom,
            content.set_margin_start,
            content.set_margin_end,
        ):
            setter(16)
        intro = gtk.Label(
            label=(
                f'Earlier passwords for "{item.name}". Copy one, or Restore to make it current again. '
                f"Up to {MAX_PASSWORD_HISTORY} are kept."
            ),
            xalign=0,
        )
        intro.set_line_wrap(True)
        intro.set_max_width_chars(46)
        content.pack_start(intro, False, False, 0)
        choice: dict[str, object] = {"action": None}

        def choose_copy(_button, secret: str) -> None:
            choice["action"] = ("copy", secret)
            dialog.response(gtk.ResponseType.CLOSE)

        def choose_restore(_button, slot: int) -> None:
            choice["action"] = ("restore", slot)
            dialog.response(gtk.ResponseType.CLOSE)

        for index, revision in enumerate(item.history):
            row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
            detail = gtk.Label(xalign=0)
            when = revision.replaced_at.strip()
            if when:
                detail.set_text(f"Replaced {when}")
            else:
                detail.set_text(f"Previous {index + 1}")
            detail.set_line_wrap(True)
            row.pack_start(detail, True, True, 0)
            copy_btn = gtk.Button(label="Copy")
            copy_btn.get_style_context().add_class("secondary")
            copy_btn.connect("clicked", choose_copy, revision.password)
            restore_btn = gtk.Button(label="Restore")
            restore_btn.get_style_context().add_class("secondary")
            restore_btn.connect("clicked", choose_restore, index)
            row.pack_start(copy_btn, False, False, 0)
            row.pack_start(restore_btn, False, False, 0)
            content.pack_start(row, False, False, 0)
        dialog.show_all()
        dialog.run()
        dialog.destroy()
        action = choice["action"]
        if not isinstance(action, tuple):
            return
        if action[0] == "copy":
            self.on_copy_text(str(action[1]))
            message = "Copied a previous password."
            self.status.set_text(message)
            if self.section == "saved":
                self.manager_message.set_text(message)
                self.manager_message.show()
            return
        if action[0] == "restore":
            self._restore_previous(item, int(action[1]))

    def _restore_previous(self, item: SavedPassword, index: int) -> None:
        if self.vault_key is None:
            self.status.set_text("Saved passwords are locked.")
            return
        current = next((entry for entry in self.saved if entry.name == item.name), None)
        if current is None:
            self.status.set_text("That saved password is gone.")
            return
        try:
            updated = restore_entry_password(self.saved, current, index)
            write_vault(self.vault_key, updated)
        except ValueError as exc:
            self.status.set_text(str(exc))
            if self.section == "saved":
                self.manager_message.set_text(str(exc))
                self.manager_message.show()
            return
        except OSError:
            message = "Could not restore that password."
            self.status.set_text(message)
            if self.section == "saved":
                self.manager_message.set_text(message)
                self.manager_message.show()
            return
        restored = next(entry for entry in updated if entry.name == current.name)
        self.saved = updated
        self.revealed_names.add(restored.name)
        self._refresh_saved_rows()
        if self.section == "dashboard":
            self._refresh_dashboard()
        self.on_copy_text(restored.password)
        message = f"Restored the previous password for {restored.name} and copied it."
        self.status.set_text(message)
        if self.section == "saved":
            self.manager_message.set_text(message)
            self.manager_message.show()

    def _confirm_replace_password(self, item: SavedPassword) -> bool:
        gtk = self.gtk
        dialog = gtk.Dialog(title="Replace password", transient_for=self.window, modal=True)
        self._match_dialog(dialog)
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        replace = dialog.add_button("Replace", gtk.ResponseType.OK)
        replace.get_style_context().add_class("primary")
        content = dialog.get_content_area()
        content.set_spacing(8)
        for setter in (
            content.set_margin_top,
            content.set_margin_bottom,
            content.set_margin_start,
            content.set_margin_end,
        ):
            setter(16)
        reason = ""
        strength = strength_warning_for(item)
        reuse = reuse_warning_for(item, self.saved)
        if strength and reuse:
            reason = f" {strength} {reuse}"
        elif strength:
            reason = f" {strength}"
        elif reuse:
            reason = f" {reuse}"
        label = gtk.Label(
            label=(
                f'Replace the password for "{item.name}" with a new strong password?'
                f"{reason} The new password is saved and copied. The old one stays under Previous. "
                "Update the site next."
            ),
            xalign=0,
        )
        label.set_line_wrap(True)
        label.set_max_width_chars(42)
        content.pack_start(label, False, False, 0)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        return response == gtk.ResponseType.OK

    def on_toggle_reveal(self, name: str) -> None:
        if name in self.revealed_names:
            self.revealed_names.remove(name)
        else:
            if self.preferences.confirm_before_reveal and not self._confirm_reveal(name):
                return
            self.revealed_names.add(name)
        self._refresh_saved_rows()

    def _confirm_reveal(self, name: str) -> bool:
        gtk = self.gtk
        dialog = gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=gtk.MessageType.QUESTION,
            buttons=gtk.ButtonsType.OK_CANCEL,
            text="Show this password?",
        )
        dialog.format_secondary_text(
            f'"{name}" will be visible on screen until you hide it or lock the vault.'
        )
        self._match_dialog(dialog)
        answer = dialog.run()
        dialog.destroy()
        return answer == gtk.ResponseType.OK

    def _update_lock_button(self) -> None:
        style = self.lock_button.get_style_context()
        header = self.header_lock_button.get_style_context()
        status = self.vault_status.get_style_context()
        status.remove_class("locked")
        status.remove_class("unlocked")
        if self.vault_key is not None:
            # Header Lock is enough when unlocked; keep the page clear.
            self.lock_button.hide()
            self.header_lock_button.set_label("Lock")
            header.remove_class("primary")
            header.add_class("secondary")
            self.header_lock_button.show()
            self.vault_status.set_text("Vault unlocked")
            status.add_class("unlocked")
            return
        if self.locked:
            self.lock_button.set_label("Unlock")
            style.add_class("primary")
            style.remove_class("secondary")
            self.lock_button.show()
            self.header_lock_button.set_label("Unlock")
            header.add_class("primary")
            header.remove_class("secondary")
            self.header_lock_button.show()
            self.vault_status.set_text("Vault locked")
            status.add_class("locked")
            return
        self.lock_button.hide()
        self.header_lock_button.hide()
        self.vault_status.set_text("No vault yet")

    def _sync_note(self, text: str) -> bool:
        self.sync_status.set_text(text)
        if text:
            self.sync_status.show()
        if self.section == "saved":
            self.manager_message.set_text(text)
            if text:
                self.manager_message.show()
        return False

    def on_send_vault(self, *_args) -> None:
        """Offer the encrypted vault until another device presents the pairing code."""
        path = vault_path()
        if not path.is_file():
            self._sync_note("Save a password on this computer first.")
            return
        try:
            offer = vault_sync.VaultOffer(path.read_bytes())
            offer.start()
        except (OSError, ValueError) as exc:
            self._sync_note(str(exc))
            return
        if offer.error or offer.port == 0:
            offer.stop()
            self._sync_note(offer.error or "Could not offer the vault on this network.")
            return
        self._show_offer(offer)

    def _show_offer(self, offer: vault_sync.VaultOffer) -> None:
        from gi.repository import GLib

        gtk = self.gtk
        dialog = gtk.Dialog(title="Send vault", transient_for=self.window, modal=True)
        self._match_dialog(dialog)
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(8)
        label = gtk.Label(
            label=(
                "On the other device, choose Receive vault and enter this code. "
                "Both devices need the same Wi-Fi. The passphrase stays on this computer. "
                "The first time, Windows may ask to allow this app on private networks."
            ),
            xalign=0,
        )
        label.set_line_wrap(True)
        label.set_max_width_chars(42)
        content.pack_start(label, False, False, 0)
        code = gtk.Label(label=offer.code, xalign=0)
        code.set_selectable(True)
        code.get_style_context().add_class("pairing-code")
        content.pack_start(code, False, False, 0)
        where = offer.where()
        if where:
            address = gtk.Label(
                label=f"If the code is not found, enter this address: {where}",
                xalign=0,
            )
            address.set_line_wrap(True)
            address.set_max_width_chars(42)
            address.set_selectable(True)
            content.pack_start(address, False, False, 0)
        limit = gtk.Label(label="The offer lasts two minutes.", xalign=0)
        limit.get_style_context().add_class("hint")
        content.pack_start(limit, False, False, 0)
        dialog.show_all()

        def tick() -> bool:
            if offer.sent:
                dialog.response(gtk.ResponseType.OK)
                return False
            if offer.error:
                dialog.response(gtk.ResponseType.CANCEL)
                return False
            return True

        source = GLib.timeout_add(400, tick)
        dialog.run()
        GLib.source_remove(source)
        sent = offer.sent
        problem = offer.error
        offer.stop()
        dialog.destroy()
        if sent:
            self._sync_note("The encrypted vault was sent. The passphrase stayed on this computer.")
        elif problem:
            self._sync_note(problem)
        else:
            self._sync_note("The offer was cancelled. Nothing was sent.")

    def on_receive_vault(self, *_args) -> None:
        """Pull an encrypted vault from a device that is offering one."""
        from gi.repository import GLib

        gtk = self.gtk
        dialog = gtk.Dialog(title="Receive vault", transient_for=self.window, modal=True)
        self._match_dialog(dialog)
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        dialog.add_button("Receive", gtk.ResponseType.OK)
        dialog.set_default_response(gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(8)
        label = gtk.Label(
            label=(
                "Enter the 6-digit code from the other device. "
                "Both devices need the same Wi-Fi. The passphrase is not sent."
            ),
            xalign=0,
        )
        label.set_line_wrap(True)
        label.set_max_width_chars(42)
        content.pack_start(label, False, False, 0)
        code_entry = gtk.Entry()
        code_entry.set_placeholder_text("6-digit code")
        code_entry.set_max_length(6)
        content.pack_start(code_entry, False, False, 0)
        address_entry = gtk.Entry()
        address_entry.set_placeholder_text("Optional address, such as 192.168.1.20:12345")
        content.pack_start(address_entry, False, False, 0)
        problem = gtk.Label(label="", xalign=0)
        problem.set_line_wrap(True)
        problem.get_style_context().add_class("danger")
        content.pack_start(problem, False, False, 0)
        dialog.show_all()
        code_entry.grab_focus()
        code_entry.connect("activate", lambda *_args: dialog.response(gtk.ResponseType.OK))
        code = ""
        address = ""
        while True:
            response = dialog.run()
            if response != gtk.ResponseType.OK:
                dialog.destroy()
                return
            try:
                code = vault_sync.normalize_code(code_entry.get_text())
            except ValueError as exc:
                problem.set_text(str(exc))
                continue
            address = address_entry.get_text().strip()
            dialog.destroy()
            break
        self._sync_note("Looking for the other device.")

        def work() -> None:
            try:
                blob = vault_sync.receive_vault(code, address or None)
            except ValueError as exc:
                GLib.idle_add(self._sync_note, str(exc))
                return
            GLib.idle_add(self._apply_received, blob)

        threading.Thread(target=work, name="vault-receive", daemon=True).start()

    def _apply_received(self, blob: bytes) -> bool:
        try:
            self._merge_or_store(blob)
        except ValueError as exc:
            self._sync_note(str(exc))
        except OSError:
            self._sync_note("Could not save the vault from the other device.")
        return False

    def _merge_or_store(self, blob: bytes) -> None:
        path = vault_path()
        if not path.is_file():
            store_vault_blob(blob, path)
            self._prepare_saved()
            self.show_section("saved")
            self._sync_note(
                "Vault received. The passphrase was not sent. Unlock with the same passphrase."
            )
            return
        if not self._ensure_vault_key():
            self._sync_note("Unlock this computer's vault before merging. Nothing was replaced.")
            return
        incoming = items_from_same_vault(blob, self.vault_key)
        if incoming is None:
            self._merge_foreign(blob)
            return
        self._finish_merge(incoming)

    def _merge_foreign(self, blob: bytes) -> None:
        while True:
            secret = self._prompt_passphrase(
                confirm=False,
                message=(
                    "This vault uses a different passphrase. Enter it to merge the passwords. "
                    "It is not sent."
                ),
            )
            if secret is None:
                self._sync_note("Nothing was merged.")
                return
            try:
                _material, incoming = open_vault_bytes(secret, blob)
            except ValueError as exc:
                self._sync_note(str(exc))
                continue
            self._finish_merge(incoming)
            return

    def _finish_merge(self, incoming: list[SavedPassword]) -> None:
        merged, splits = merge_saved(self.saved, incoming)
        write_vault(self.vault_key, merged)
        self.saved = merged
        self.locked = False
        self.show_section("saved")
        self._refresh_saved_rows()
        self._update_lock_button()
        if splits == 1:
            extra = " One name differed, so both copies were kept."
        elif splits:
            extra = f" {splits} names differed, so both copies were kept."
        else:
            extra = ""
        self._sync_note("Passwords arrived. The passphrase was not sent." + extra)

    def _prompt_passphrase(self, *, confirm: bool, message: str | None = None) -> str | None:
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
        if message is None and confirm:
            message = "Choose a passphrase to lock saved passwords. It is not stored."
        elif message is None:
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

    def _clear_stale_lock_status(self) -> None:
        """Drop Generate status text that still says locked after a successful unlock."""
        if self.status.get_text() in (
            "Saved passwords are locked.",
            "Saved passwords locked after sitting idle.",
        ):
            self.status.set_text("Generate a password. Name it, then save it.")

    def on_lock_toggle(self, _button) -> None:
        if self.vault_key is not None:
            self._lock_saved()
            return
        if not self._ensure_vault_key():
            self._update_lock_button()
            return
        self.revealed_names.clear()
        self._clear_stale_lock_status()
        self._update_lock_button()
        if self.section == "dashboard":
            self._refresh_dashboard()
        else:
            self.show_section("saved")

    def _lock_saved(self) -> None:
        self.vault_key = None
        self.saved = []
        self.removed_entry = None
        self.undo_remove_button.hide()
        self.revealed_names.clear()
        self.breach_counts.clear()
        self._breach_check_running = False
        if hasattr(self, "check_breaches_button"):
            self.check_breaches_button.set_sensitive(True)
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
        if self.section == "dashboard":
            self._refresh_dashboard()

    def on_copy_text(self, text: str) -> None:
        if not text:
            return
        self._note_activity()
        copied = False
        # On Windows, GTK Clipboard.set_text often looks successful but does not
        # put text on the system clipboard other apps paste from. Prefer Win32.
        if sys.platform == "win32":
            copied = generator.copy_with_windows(text)
        if not copied and copy_with_xclip(text):
            copied = True
        if not copied:
            try:
                clipboard = self.gtk.Clipboard.get(self.gdk.SELECTION_CLIPBOARD)
                clipboard.set_text(text, -1)
                clipboard.store()
                copied = True
            except Exception:
                copied = False
        if not copied and sys.platform != "win32":
            copied = generator.copy_with_windows(text)
        if copied:
            self._schedule_clipboard_clear(text)
            seconds = self.preferences.clipboard_clear_seconds
            if seconds:
                message = f"Copied. Clipboard clears in {seconds} seconds."
            else:
                message = "Copied."
        else:
            message = "Copy failed."
        self.status.set_text(message)
        if self.section == "saved" and self.vault_key is not None:
            self.manager_message.set_text(message)
            self.manager_message.show()
        if self.section == "settings":
            self._sync_note(message)

    def on_copy_saved_secret(self, item: SavedPassword, text: str) -> None:
        """Copy a field from a saved entry and mark that entry as recently used."""
        self.on_copy_text(text)
        if self.vault_key is None or not text:
            return
        current = next((entry for entry in self.saved if entry.name == item.name), None)
        if current is None:
            return
        try:
            updated = touch_last_used(self.saved, current)
            write_vault(self.vault_key, updated)
        except (OSError, ValueError):
            return
        self.saved = updated
        if self.saved_sort_mode == SAVED_SORT_RECENT:
            self._refresh_saved_rows()
        elif self.section == "dashboard":
            self._refresh_dashboard()

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
        current = next((entry for entry in self.saved if entry.name == name), None)
        if current is None:
            self.status.set_text("That saved password is gone.")
            return
        if not self._confirm_remove(name):
            return
        try:
            updated = remove_entry(self.saved, current)
            write_vault(self.vault_key, updated)
        except ValueError as exc:
            self.status.set_text(str(exc))
            return
        except OSError:
            self.status.set_text("Could not remove the saved password.")
            return
        self.saved = updated
        self.removed_entry = current
        self.revealed_names.discard(name)
        self.showing_saved = False
        self._refresh_saved_rows()
        message = f'Removed "{current.name}". Undo to put it back.'
        self.status.set_text(message)
        self.manager_message.set_text(message)
        self.manager_message.show()
        self.undo_remove_button.show()
        if self.section == "dashboard":
            self._refresh_dashboard()

    def on_undo_remove(self, *_args) -> None:
        """Restore the last removed Saved entry."""
        self._note_activity()
        if self.vault_key is None:
            self.status.set_text("Saved passwords are locked.")
            return
        item = self.removed_entry
        if item is None:
            self.status.set_text("Nothing to undo.")
            self.undo_remove_button.hide()
            return
        try:
            updated = restore_removed_entry(self.saved, item)
            write_vault(self.vault_key, updated)
        except (OSError, ValueError) as exc:
            self.status.set_text(str(exc) or "Could not restore that entry.")
            return
        self.saved = updated
        restored = updated[0]
        self.removed_entry = None
        self.undo_remove_button.hide()
        message = f'Restored "{restored.name}".'
        self.status.set_text(message)
        self.manager_message.set_text(message)
        self.manager_message.show()
        self._refresh_saved_rows()
        if self.section == "dashboard":
            self._refresh_dashboard()

    def _confirm_remove(self, name: str) -> bool:
        gtk = self.gtk
        dialog = gtk.Dialog(title="Remove saved password", transient_for=self.window, modal=True)
        self._match_dialog(dialog)
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        remove = dialog.add_button("Remove", gtk.ResponseType.OK)
        remove.get_style_context().add_class("primary")
        content = dialog.get_content_area()
        content.set_spacing(8)
        for setter in (
            content.set_margin_top,
            content.set_margin_bottom,
            content.set_margin_start,
            content.set_margin_end,
        ):
            setter(16)
        label = gtk.Label(
            label=f'Remove "{name}" from this computer? You can Undo on the Saved page.',
            xalign=0,
        )
        label.set_line_wrap(True)
        label.set_max_width_chars(42)
        content.pack_start(label, False, False, 0)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        return response == gtk.ResponseType.OK

    def on_add_password(self, *_args) -> None:
        """Add a password manually without generating one first."""
        self._note_activity()
        if not self._ensure_vault_key():
            return
        blank = SavedPassword("", "")
        created = self._edit_entry_dialog(blank, title="Add password", require_password=True)
        if created is None:
            return
        stamp = utc_now()
        created = replace(created, created=stamp, modified=stamp)
        try:
            updated = upsert_entry(self.saved, created)
            write_vault(self.vault_key, updated)
        except ValueError as exc:
            self.status.set_text(str(exc))
            if self.section == "saved":
                self.manager_message.set_text(str(exc))
                self.manager_message.show()
            return
        except OSError:
            self.status.set_text("Could not save the password.")
            return
        self.saved = updated
        self.locked = False
        self._update_lock_button()
        message = f"Saved {created.name}."
        self.status.set_text(message)
        self.show_section("saved")
        self.manager_message.set_text(message)
        self.manager_message.show()

    def on_edit_entry(self, item: SavedPassword) -> None:
        if self.vault_key is None:
            self.status.set_text("Saved passwords are locked.")
            return
        edited = self._edit_entry_dialog(item)
        if edited is None:
            return
        if edited.password != item.password:
            edited = with_changed_password(
                replace(
                    item,
                    name=edited.name,
                    username=edited.username,
                    url=edited.url,
                    notes=edited.notes,
                    category=edited.category,
                    favorite=edited.favorite,
                    archived=edited.archived,
                    last_used=edited.last_used,
                    extras=dict(edited.extras),
                ),
                edited.password,
            )
        try:
            updated = upsert_entry(self.saved, edited, previous_name=item.name)
            write_vault(self.vault_key, updated)
        except ValueError as exc:
            self.status.set_text(str(exc))
            self.manager_message.set_text(str(exc))
            self.manager_message.show()
            return
        except OSError:
            self.status.set_text("Could not save the changes.")
            return
        if item.name in self.revealed_names and edited.name != item.name:
            self.revealed_names.discard(item.name)
            self.revealed_names.add(edited.name)
        self.saved = updated
        self._refresh_saved_rows()
        self.status.set_text(f"Updated {edited.name}.")
        self.manager_message.set_text(f"Updated {edited.name}.")
        self.manager_message.show()
        if self.section == "dashboard":
            self._refresh_dashboard()

    def _edit_entry_dialog(
        self,
        item: SavedPassword,
        *,
        title: str = "Edit saved password",
        require_password: bool = False,
    ) -> SavedPassword | None:
        gtk = self.gtk
        dialog = gtk.Dialog(title=title, transient_for=self.window, modal=True)
        self._match_dialog(dialog)
        dialog.add_button("Cancel", gtk.ResponseType.CANCEL)
        save = dialog.add_button("Save", gtk.ResponseType.OK)
        save.get_style_context().add_class("primary")
        dialog.set_default_response(gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_spacing(8)
        for setter in (
            content.set_margin_top,
            content.set_margin_bottom,
            content.set_margin_start,
            content.set_margin_end,
        ):
            setter(16)

        def field(caption: str, value: str, *, password: bool = False, multiline: bool = False):
            box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=4)
            label = gtk.Label(label=caption, xalign=0)
            box.pack_start(label, False, False, 0)
            if multiline:
                view = gtk.TextView()
                view.set_wrap_mode(gtk.WrapMode.WORD_CHAR)
                view.get_buffer().set_text(value)
                view.set_size_request(-1, 72)
                box.pack_start(view, False, False, 0)
                content.pack_start(box, False, False, 0)
                return view
            entry = gtk.Entry()
            entry.set_text(value)
            if password:
                entry.set_visibility(False)
                entry.set_input_purpose(gtk.InputPurpose.PASSWORD)
            box.pack_start(entry, False, False, 0)
            content.pack_start(box, False, False, 0)
            return entry

        name_entry = field("Name", item.name)
        username_entry = field("Username", item.username)
        url_entry = field("URL", item.url)
        password_entry = field("Password", item.password, password=True)
        category_entry = field("Category", item.category)
        presets = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=6)
        for label in DEFAULT_CATEGORIES:
            chip = gtk.Button(label=label)
            chip.get_style_context().add_class("secondary")
            chip.connect(
                "clicked",
                lambda *_args, chosen=label: category_entry.set_text(chosen),
            )
            presets.pack_start(chip, False, False, 0)
        scroller = gtk.ScrolledWindow()
        scroller.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.NEVER)
        scroller.add(presets)
        content.pack_start(scroller, False, False, 0)
        notes_view = field("Notes", item.notes, multiline=True)
        favorite = gtk.CheckButton(label="Favorite")
        favorite.set_active(item.favorite)
        content.pack_start(favorite, False, False, 0)
        archived = gtk.CheckButton(label="Archived")
        archived.set_active(item.archived)
        content.pack_start(archived, False, False, 0)
        problem = gtk.Label(label="", xalign=0)
        problem.set_line_wrap(True)
        problem.get_style_context().add_class("danger")
        content.pack_start(problem, False, False, 0)
        dialog.show_all()
        name_entry.grab_focus()
        while True:
            response = dialog.run()
            if response != gtk.ResponseType.OK:
                dialog.destroy()
                return None
            buffer = notes_view.get_buffer()
            notes = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
            try:
                raw_password = password_entry.get_text()
                if require_password and not raw_password.strip():
                    raise ValueError("Enter a password to save.")
                edited = SavedPassword(
                    clean_name(name_entry.get_text()),
                    _password_line(raw_password),
                    username=clean_username(username_entry.get_text()),
                    url=clean_url(url_entry.get_text()),
                    notes=clean_notes(notes),
                    category=clean_category(category_entry.get_text()),
                    favorite=favorite.get_active(),
                    archived=archived.get_active(),
                    created=item.created,
                    modified=item.modified,
                    last_used=item.last_used,
                    history=item.history,
                    extras=dict(item.extras),
                )
            except ValueError as exc:
                problem.set_text(str(exc))
                continue
            if any(
                entry.name == edited.name and entry.name != item.name for entry in self.saved
            ):
                problem.set_text("Another saved password already uses that name.")
                continue
            dialog.destroy()
            return edited


if __name__ == "__main__":
    main()
