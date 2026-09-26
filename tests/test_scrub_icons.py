"""The Windows bundle must not keep SVG theme icons."""

from __future__ import annotations

import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packaging" / "windows"))

import password_app  # noqa: E402
import scrub_icons  # noqa: E402


class ScrubIconTests(unittest.TestCase):
    def test_svg_theme_icons_are_replaced_with_a_png_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = root / "_internal" / "share" / "icons" / "Adwaita" / "scalable" / "status"
            status.mkdir(parents=True)
            (status / "image-missing.svg").write_text("<svg/>", encoding="utf-8")
            plain = root / "_internal" / "share" / "icons" / "Adwaita" / "16x16" / "status"
            plain.mkdir(parents=True)
            theme = root / "_internal" / "share" / "icons" / "Adwaita" / "index.theme"
            theme.write_text(
                "\n".join(
                    [
                        "[Icon Theme]",
                        "Name=Adwaita",
                        "Directories=16x16/status,scalable/status,symbolic/status,",
                        "",
                        "[16x16/status]",
                        "Size=16",
                        "Type=Fixed",
                        "",
                        "[scalable/status]",
                        "Size=128",
                        "Type=Scalable",
                        "",
                        "[symbolic/status]",
                        "Size=16",
                        "Type=Scalable",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            cache = root / "_internal" / "share" / "icons" / "Adwaita" / "icon-theme.cache"
            cache.write_bytes(b"cache")
            kept = root / "_internal" / "local-password.svg"
            kept.write_text("<svg/>", encoding="utf-8")

            themes, removed = scrub_icons.scrub_icon_themes(root)

            self.assertEqual(themes, 1)
            self.assertEqual(removed, 1)
            self.assertFalse((status / "image-missing.svg").exists())
            self.assertTrue((plain / "image-missing.png").is_file())
            self.assertTrue((status / "image-missing.png").is_file())
            self.assertFalse(cache.exists())
            self.assertTrue(kept.is_file())
            text = theme.read_text(encoding="utf-8")
            self.assertIn("Directories=16x16/status", text)
            self.assertNotIn("scalable", text)
            self.assertNotIn("symbolic", text)
            self.assertNotIn("[scalable/status]", text)

    def test_command_scrubs_the_directory_it_is_given(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            icons = root / "share" / "icons" / "Adwaita"
            (icons / "scalable" / "status").mkdir(parents=True)
            (icons / "scalable" / "status" / "image-missing.svg").write_text("<svg/>", encoding="utf-8")
            (icons / "index.theme").write_text(
                "[Icon Theme]\nDirectories=scalable/status\n\n[scalable/status]\nType=Scalable\n",
                encoding="utf-8",
            )
            self.assertEqual(scrub_icons.main([str(root)]), 0)
            self.assertFalse((icons / "scalable" / "status" / "image-missing.svg").exists())
            self.assertEqual(scrub_icons.main([]), 2)
            self.assertEqual(scrub_icons.main(["/tmp/does-not-exist-local-password"]), 1)

    def test_frozen_app_drops_svg_icons_before_gtk_starts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = root / "_internal" / "share" / "icons" / "Adwaita" / "scalable" / "status"
            status.mkdir(parents=True)
            (status / "image-missing.svg").write_text("<svg/>", encoding="utf-8")
            theme = root / "_internal" / "share" / "icons" / "Adwaita" / "index.theme"
            theme.write_text(
                "[Icon Theme]\nDirectories=scalable/status\n\n[scalable/status]\nType=Scalable\n",
                encoding="utf-8",
            )
            exe = root / "LocalPassword.exe"
            exe.write_bytes(b"")
            self.assertTrue((status / "image-missing.svg").is_file())
            password_app.repair_bundled_icons()
            self.assertTrue((status / "image-missing.svg").is_file())
            with unittest.mock.patch.object(password_app.sys, "frozen", True, create=True), unittest.mock.patch.object(
                password_app.sys, "executable", str(exe)
            ), unittest.mock.patch.object(password_app.sys, "_MEIPASS", str(root / "_internal"), create=True):
                password_app.repair_bundled_icons()
            self.assertFalse((status / "image-missing.svg").exists())
            self.assertTrue((status / "image-missing.png").is_file())
            self.assertNotIn("scalable", theme.read_text(encoding="utf-8"))

    def test_missing_icon_tree_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                scrub_icons.scrub_icon_themes(Path(directory))

    def test_windows_build_calls_the_scrub_with_a_windows_path(self) -> None:
        script = (
            Path(__file__).resolve().parents[1] / "packaging" / "windows" / "build.sh"
        ).read_text(encoding="utf-8")
        self.assertIn('WINDEST=$(cygpath -m "$DEST")', script)
        self.assertIn('python "$WINROOT/packaging/windows/scrub_icons.py" "$WINDEST"', script)
        self.assertNotIn('python - "$DEST"', script)
        self.assertIn('--icon "$WINROOT/packaging/windows/local-password.ico"', script)
        self.assertIn("LocalPassword-windows.zip", script)

    def test_windows_icon_is_a_multisize_key(self) -> None:
        root = Path(__file__).resolve().parents[1] / "packaging" / "windows"
        ico = (root / "local-password.ico").read_bytes()
        png = (root / "local-password.png").read_bytes()
        self.assertEqual(int.from_bytes(ico[0:2], "little"), 0)
        self.assertEqual(int.from_bytes(ico[2:4], "little"), 1)
        count = int.from_bytes(ico[4:6], "little")
        widths = []
        for index in range(count):
            width = ico[6 + index * 16]
            widths.append(256 if width == 0 else width)
        self.assertIn(16, widths)
        self.assertIn(32, widths)
        self.assertIn(256, widths)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
