"""The Windows build installs like a normal Start-menu app."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import password_app

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "packaging" / "windows"


class WindowsInstallTests(unittest.TestCase):
    def test_installer_registers_a_start_menu_app(self) -> None:
        script = (WINDOWS / "install.ps1").read_text(encoding="utf-8")
        self.assertIn(r"Programs\Local Password", script)
        self.assertIn(r"Start Menu\Programs\Local Password.lnk", script)
        self.assertIn("Desktop", script)
        self.assertIn("Uninstall\\LocalPassword", script)
        self.assertIn("LocalPassword.exe", script)
        command = (WINDOWS / "Install Local Password.cmd").read_bytes()
        self.assertIn(b"\r\n", command)
        self.assertIn(b"install.ps1", command)

    def test_build_puts_the_installer_in_the_zip(self) -> None:
        script = (WINDOWS / "build.sh").read_text(encoding="utf-8")
        self.assertIn('cp "$ROOT/packaging/windows/install.ps1"', script)
        self.assertIn("Install Local Password.cmd", script)

    def test_taskbar_id_is_skipped_off_windows(self) -> None:
        with patch.object(password_app.sys, "platform", "linux"):
            password_app.set_windows_app_id()
