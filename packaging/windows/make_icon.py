#!/usr/bin/env python3
"""Build Local Password icon assets from the official Premium Emerald artwork."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# Official artwork (diagonal white key on emerald squircle).
SOURCE_CANDIDATES = (
    ROOT / "packaging" / "branding" / "app-icon.png",
    HERE / "icon-source.png",
)

PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
# Android launcher densities (px for mdpi baseline 48dp).
ANDROID_MIPMAPS = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}
# Adaptive foreground is 108dp; keep artwork in the safe zone with padding.
ANDROID_ADAPTIVE_FG = 432  # xxxhdpi 108dp


def resolve_source() -> Path:
    for path in SOURCE_CANDIDATES:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "Missing icon source. Expected packaging/branding/app-icon.png"
    )


def load_master() -> Image.Image:
    source = resolve_source()
    image = Image.open(source).convert("RGBA")
    # Normalize to a square master so every export stays centered.
    side = max(image.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    x = (side - image.width) // 2
    y = (side - image.height) // 2
    canvas.paste(image, (x, y), image)
    return canvas


def resize(image: Image.Image, size: int) -> Image.Image:
    return image.resize((size, size), Image.Resampling.LANCZOS)


def adaptive_foreground(master: Image.Image, size: int = ANDROID_ADAPTIVE_FG) -> Image.Image:
    """Place the full icon inside the adaptive safe zone on a transparent canvas."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    # Safe zone ~66/108 of the canvas; use ~72% so the squircle fills nicely.
    inner = int(round(size * 0.72))
    icon = resize(master, inner)
    x = (size - inner) // 2
    y = (size - inner) // 2
    canvas.paste(icon, (x, y), icon)
    return canvas


def write_icons(directory: Path = HERE) -> tuple[Path, Path, Path]:
    master = load_master()
    icons_dir = directory / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    by_size = {size: resize(master, size) for size in PNG_SIZES}
    for size, image in by_size.items():
        image.save(icons_dir / f"local-password-{size}.png", format="PNG")

    png_path = directory / "local-password.png"
    by_size[256].save(png_path, format="PNG")

    ico_images = [by_size[size] for size in ICO_SIZES]
    ico_path = directory / "local-password.ico"
    ico_images[-1].save(
        ico_path,
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
        append_images=ico_images[:-1],
    )

    # Keep a copy next to the generator for Windows rebuilds that only ship packaging/windows.
    shutil.copy2(resolve_source(), directory / "icon-source.png")

    android_res = ROOT / "android" / "app" / "src" / "main" / "res"
    for folder, size in ANDROID_MIPMAPS.items():
        out_dir = android_res / folder
        out_dir.mkdir(parents=True, exist_ok=True)
        resize(master, size).save(out_dir / "ic_launcher.png", format="PNG")

    fg_dir = android_res / "drawable"
    fg_dir.mkdir(parents=True, exist_ok=True)
    adaptive_foreground(master).save(fg_dir / "ic_launcher_fg.png", format="PNG")

    return png_path, ico_path, icons_dir


if __name__ == "__main__":
    png_path, ico_path, icons_dir = write_icons()
    print(png_path)
    print(ico_path)
    print(icons_dir)
