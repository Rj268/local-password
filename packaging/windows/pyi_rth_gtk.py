"""PyInstaller runtime hook. Point GTK at the files shipped beside the exe."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def _prepare_gtk() -> None:
    bundled = getattr(sys, "_MEIPASS", None)
    if not bundled:
        return
    root = Path(bundled)
    os.environ["GI_TYPELIB_PATH"] = str(root / "lib" / "girepository-1.0")
    os.environ["XDG_DATA_DIRS"] = str(root / "share")
    fonts = root / "etc" / "fonts" / "fonts.conf"
    if fonts.is_file():
        os.environ["FONTCONFIG_FILE"] = str(fonts)
    cache = root / "lib" / "gdk-pixbuf-2.0" / "2.10.0" / "loaders.cache"
    loaders = root / "lib" / "gdk-pixbuf-2.0" / "2.10.0" / "loaders"
    if cache.is_file() and loaders.is_dir():
        text = cache.read_text(encoding="utf-8", errors="replace")

        def relocate(match: re.Match[str]) -> str:
            name = Path(match.group(1)).name
            return '"' + (loaders / name).as_posix() + '"'

        rewritten = re.sub(r'"([^"]*loaders[/\\][^"]+)"', relocate, text)
        cache.write_text(rewritten, encoding="utf-8")
        os.environ["GDK_PIXBUF_MODULE_FILE"] = str(cache)


_prepare_gtk()
