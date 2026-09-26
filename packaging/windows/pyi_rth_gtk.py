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


# os.add_dll_directory removes the directory again if its return value is
# discarded. GTK then cannot find the SVG loader's libraries.
_DLL_DIRECTORIES: list[object] = []


def _keep_dll_dir(path: Path) -> None:
    if hasattr(os, "add_dll_directory"):
        _DLL_DIRECTORIES.append(os.add_dll_directory(str(path)))


def _prepare_gtk() -> None:
    exe_dir = Path(sys.executable).resolve().parent
    meipass = Path(getattr(sys, "_MEIPASS", exe_dir))

    # PyInstaller searches _internal. The SVG loader's dependencies are also
    # copied next to the exe. Both directories have to stay on the DLL path.
    os.environ["PATH"] = (
        str(meipass) + os.pathsep + str(exe_dir) + os.pathsep + os.environ.get("PATH", "")
    )
    _keep_dll_dir(exe_dir)
    if meipass != exe_dir:
        _keep_dll_dir(meipass)
    if sys.platform == "win32":
        import ctypes

        ctypes.WinDLL("kernel32", use_last_error=True).SetDllDirectoryW(str(exe_dir))

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
        _keep_dll_dir(loaders)
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

    # password_app is the entry script, so the frozen app can import it.
    # Repair runs again at the start of main, before GTK is imported.
    try:
        import password_app

        password_app.repair_bundled_icons()
    except (ImportError, OSError):
        pass


if getattr(sys, "frozen", False):
    _prepare_gtk()
