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
