#!/usr/bin/env python3
"""Draw the green key icon used by the Windows exe and the window."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

GREEN = (0x08, 0x77, 0x5B, 255)
CREAM = (0xF5, 0xF4, 0xEF, 255)
SIZES = (16, 24, 32, 48, 64, 128, 256)
HERE = Path(__file__).resolve().parent


def draw_icon(size: int) -> Image.Image:
    """Key on a green rounded square. Coordinates match the 64px SVG."""
    scale = size / 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    radius = max(2, round(16 * scale))
    pen.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=GREEN)
    stroke = max(1, round(3 * scale))
    cx = 32 * scale
    cy = 26 * scale
    radius_key = 8 * scale
    pen.ellipse(
        (cx - radius_key, cy - radius_key, cx + radius_key, cy + radius_key),
        outline=CREAM,
        width=stroke,
    )
    shaft_radius = max(1, round(1.5 * scale))
    pen.rounded_rectangle(
        (30 * scale, 32 * scale, 34 * scale, 46 * scale),
        radius=shaft_radius,
        fill=CREAM,
    )
    pen.rounded_rectangle(
        (28 * scale, 42 * scale, 36 * scale, 45 * scale),
        radius=shaft_radius,
        fill=CREAM,
    )
    return image


def write_icons(directory: Path = HERE) -> tuple[Path, Path]:
    images = [draw_icon(size) for size in SIZES]
    png_path = directory / "local-password.png"
    ico_path = directory / "local-password.ico"
    images[-1].save(png_path, format="PNG")
    images[-1].save(
        ico_path,
        format="ICO",
        sizes=[(size, size) for size in SIZES],
        append_images=images[:-1],
    )
    return png_path, ico_path


if __name__ == "__main__":
    png_path, ico_path = write_icons()
    print(png_path)
    print(ico_path)
