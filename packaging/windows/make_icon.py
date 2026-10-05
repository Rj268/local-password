#!/usr/bin/env python3
"""Draw the green key icon used by the Windows exe and the window."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

GREEN = (0x0E, 0x6B, 0x52, 255)
CREAM = (0xF5, 0xF4, 0xEF, 255)
SIZES = (16, 24, 32, 48, 64, 128, 256)
HERE = Path(__file__).resolve().parent


def draw_icon(size: int) -> Image.Image:
    """Compact classic key on a green rounded square — fits round launcher masks."""
    scale = size / 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    corner = max(2, round(14 * scale))
    pen.rounded_rectangle((0, 0, size - 1, size - 1), radius=corner, fill=GREEN)

    def box(x0: float, y0: float, x1: float, y1: float) -> tuple[float, float, float, float]:
        return (x0 * scale, y0 * scale, x1 * scale, y1 * scale)

    cx, cy = 22.0, 32.0
    outer, inner = 11.0, 5.0
    pen.ellipse(box(cx - outer, cy - outer, cx + outer, cy + outer), fill=CREAM)
    pen.ellipse(box(cx - inner, cy - inner, cx + inner, cy + inner), fill=GREEN)

    radius = max(1, round(2 * scale))
    # Shaft starts inside the ring; tip stays clear of the icon edge
    pen.rounded_rectangle(box(24, 28, 52, 36), radius=radius, fill=CREAM)
    pen.rounded_rectangle(box(38, 33, 45, 47), radius=radius, fill=CREAM)
    pen.rounded_rectangle(box(47, 33, 54, 43), radius=radius, fill=CREAM)
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
