"""PyInstaller runtime hook. Point GTK at the files shipped beside the exe."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def _alias_loader(loaders: Path, name: str) -> Path | None:
    """Return the loader DLL that is actually on disk.

    Windows GTK asks for both pixbufloader_svg.dll and libpixbufloader_svg.dll.
    librsvg ships only one of those names.
    """
    direct = loaders / name
    if name.startswith("lib"):
        alternate = loaders / name[3:]
    else:
        alternate = loaders / f"lib{name}"
    if direct.is_file():
        if not alternate.is_file():
            try:
                alternate.write_bytes(direct.read_bytes())
            except OSError:
                pass
        return direct
    if alternate.is_file():
        return alternate
    return None


def _prepare_gtk() -> None:
    exe_dir = Path(sys.executable).resolve().parent
    meipass = Path(getattr(sys, "_MEIPASS", exe_dir))

    # The SVG loader lives under lib/ and its dependencies sit next to the exe.
    os.environ["PATH"] = str(exe_dir) + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(exe_dir))

    typelibs: list[str] = []
    data_dirs: list[str] = []
    for base in (exe_dir, meipass):
        typelib = base / "lib" / "girepository-1.0"
        if typelib.is_dir() and str(typelib) not in typelibs:
            typelibs.append(str(typelib))
        share = base / "share"
        if share.is_dir() and str(share) not in data_dirs:
            data_dirs.append(str(share))
    if typelibs:
        os.environ["GI_TYPELIB_PATH"] = os.pathsep.join(typelibs)
    if data_dirs:
        os.environ["XDG_DATA_DIRS"] = os.pathsep.join(data_dirs)

    schema_dir = exe_dir / "share" / "glib-2.0" / "schemas"
    if schema_dir.is_dir():
        os.environ["GSETTINGS_SCHEMA_DIR"] = str(schema_dir)

    for base in (exe_dir, meipass):
        fonts = base / "etc" / "fonts" / "fonts.conf"
        if fonts.is_file():
            os.environ["FONTCONFIG_FILE"] = str(fonts)
            break

    for base in (exe_dir, meipass):
        cache = base / "lib" / "gdk-pixbuf-2.0" / "2.10.0" / "loaders.cache"
        loaders = base / "lib" / "gdk-pixbuf-2.0" / "2.10.0" / "loaders"
        if not (cache.is_file() and loaders.is_dir()):
            continue
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(loaders))
        text = cache.read_text(encoding="utf-8", errors="replace")

        def relocate(match: re.Match[str]) -> str:
            found = _alias_loader(loaders, Path(match.group(1)).name)
            target = found if found is not None else loaders / Path(match.group(1)).name
            return '"' + target.as_posix() + '"'

        rewritten = re.sub(r'"([^"]*loaders[/\\][^"]+)"', relocate, text)
        cache.write_text(rewritten, encoding="utf-8")
        os.environ["GDK_PIXBUF_MODULE_FILE"] = str(cache)
        os.environ["GDK_PIXBUF_MODULEDIR"] = str(loaders)
        break


_prepare_gtk()
