#!/usr/bin/env python3
"""Remove SVG theme icons so GTK can open without the Windows SVG loader.

The window uses the same scrub, from password_app, before GTK starts.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import password_app

scrub_icon_themes = password_app.scrub_icon_themes

COOKIE = b"!<symlink>"


def _symlink_target(cookie: bytes) -> str:
    """Return the path stored in an MSYS symlink cookie."""
    rest = cookie[len(COOKIE) :]
    if rest.startswith(b"\xff\xfe"):
        text = rest[2:].decode("utf-16le", "replace")
    elif b"\x00" in rest[:8]:
        text = rest.decode("utf-16le", "replace")
    else:
        text = rest.decode("utf-8", "replace")
    return text.split("\x00", 1)[0].strip()


def follow_msys_file(path: Path) -> bytes:
    """Read a file, following MSYS !<symlink> cookies to the real bytes."""
    seen: set[Path] = set()
    current = path
    while True:
        data = current.read_bytes()
        if not data.startswith(COOKIE):
            return data
        resolved = current.resolve()
        if resolved in seen:
            return data
        seen.add(resolved)
        target = Path(_symlink_target(data))
        current = target if target.is_absolute() else current.parent / target


def materialize_dlls(root: Path, source_bin: Path) -> int:
    """Replace copied MSYS symlink cookies with the real DLL bytes.

    MSYS stores some libraries as !<symlink> files. cp keeps that cookie.
    Windows then reports the DLL as a bad image.
    """
    replaced = 0
    for dll in root.rglob("*.dll"):
        try:
            head = dll.read_bytes()[:2]
            linked = dll.is_symlink()
        except OSError:
            continue
        if head == b"MZ" and not linked:
            continue
        source = source_bin / dll.name
        if not source.is_file():
            print(f"No real library for {dll.name}", file=sys.stderr)
            continue
        try:
            data = follow_msys_file(source)
        except OSError as exc:
            print(f"Could not read {source}: {exc}", file=sys.stderr)
            continue
        if not data.startswith(b"MZ"):
            print(f"{source} is not a Windows library", file=sys.stderr)
            continue
        if dll.is_symlink() or dll.is_file():
            dll.unlink()
        dll.write_bytes(data)
        replaced += 1
        print(f"Replaced shortcut library {dll.relative_to(root)}")
    return replaced


def main(argv: list[str]) -> int:
    if len(argv) not in (1, 2):
        print("Usage: scrub_icons.py DIST_DIR [DLL_SOURCE_DIR]", file=sys.stderr)
        return 2
    root = Path(argv[0])
    if len(argv) == 2:
        try:
            replaced = materialize_dlls(root, Path(argv[1]))
        except OSError as exc:
            print(exc, file=sys.stderr)
            return 1
        print(f"Replaced {replaced} shortcut library(s).")
    try:
        themes, removed = scrub_icon_themes(root)
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Scrubbed {themes} icon theme(s) and removed {removed} svg file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
