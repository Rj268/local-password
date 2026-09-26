#!/usr/bin/env python3
"""Remove SVG theme icons so GTK can open without the Windows SVG loader.

The loader reports that its module is missing and GTK then aborts on
Adwaita's image-missing.svg. PNG icons stay. A one-pixel PNG stands in
for the missing-image fallback.
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _svg_section(name: str) -> bool:
    folded = name.lower()
    return "scalable" in folded or "symbolic" in folded


def _icon_directories(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, _dirnames, _filenames in os.walk(root, followlinks=True):
        current = Path(dirpath)
        if current.name.lower() == "icons":
            found.append(current)
    return found


def scrub_icon_themes(root: Path) -> tuple[int, int]:
    """Rewrite icon themes under root. Returns (themes updated, svgs removed)."""
    if not root.is_dir():
        raise FileNotFoundError(f"Icon root is not a directory: {root}")
    icon_dirs = _icon_directories(root)
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
                (status / "image-missing.png").write_bytes(PNG_1PX)
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


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Usage: scrub_icons.py DIST_DIR", file=sys.stderr)
        return 2
    root = Path(argv[0])
    try:
        themes, removed = scrub_icon_themes(root)
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Scrubbed {themes} icon theme(s) and removed {removed} svg file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
