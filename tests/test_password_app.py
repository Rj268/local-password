"""Tests for the local password window's generator and clipboard helper."""

from __future__ import annotations

import os
import stat
import string
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import password_app


class GenerateTests(unittest.TestCase):
    def test_symbols_include_quotes_and_backslashes(self) -> None:
        pool = password_app.character_pool(digits=False, letters=False, symbols=True)
        self.assertIn("'", pool)
        self.assertIn("\\", pool)
        self.assertIn("`", pool)
        self.assertTrue(set(string.punctuation) <= set(pool))

    def test_empty_selection_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            password_app.generate(
                mode="characters",
                length=16,
                words=6,
                count=1,
                digits=False,
                letters=False,
                symbols=False,
            )

    def test_sixteen_characters_are_strong_and_unwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                result = password_app.generate(
                    mode="characters",
                    length=16,
                    words=6,
                    count=1,
                    digits=True,
                    letters=True,
                    symbols=True,
                )
                self.assertEqual(list(Path(directory).iterdir()), [])
            finally:
                os.chdir(previous)
        self.assertEqual(result.label, "Strong")
        self.assertEqual(len(result.text), 16)
        self.assertIn("bits", result.bits_label)
        self.assertEqual(result.note, "")

    def test_five_words_are_weak(self) -> None:
        result = password_app.generate(
            mode="passphrase",
            length=16,
            words=5,
            count=1,
            digits=True,
            letters=True,
            symbols=True,
        )
        self.assertEqual(len(result.text.split()), 5)
        self.assertEqual(result.label, "Weak")
        self.assertIn("75", result.note)

    def test_six_words_are_strong(self) -> None:
        result = password_app.generate(
            mode="passphrase",
            length=16,
            words=6,
            count=2,
            digits=True,
            letters=True,
            symbols=True,
        )
        lines = result.text.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(len(line.split()) == 6 for line in lines))
        self.assertEqual(result.label, "Strong")
        self.assertIn("each", result.bits_label)

    def test_chip_label_states_on_and_off(self) -> None:
        self.assertIn("On", password_app.chip_label("Digits", True))
        self.assertIn("Off", password_app.chip_label("Letters", False))


class SavedPasswordTests(unittest.TestCase):
    def test_save_round_trip_keeps_the_name_and_is_private(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "local-password" / "saved.txt"
            saved = [
                password_app.SavedPassword("Email", "first-secret"),
                password_app.SavedPassword("Bank", 'say "hi"\\'),
            ]
            password_app.store_saved_passwords(saved, path)
            self.assertEqual(password_app.load_saved_passwords(path), saved)
            file_mode = stat.S_IMODE(path.stat().st_mode)
            directory_mode = stat.S_IMODE(path.parent.stat().st_mode)
            self.assertEqual(file_mode & 0o077, 0)
            self.assertEqual(directory_mode & 0o077, 0)

    def test_same_name_replaces_the_previous_password(self) -> None:
        existing = [password_app.SavedPassword("Email", "old")]
        saved = password_app.remember_named(existing, "  Email  ", ["new"])
        self.assertEqual(saved, [password_app.SavedPassword("Email", "new")])

    def test_several_passwords_share_a_numbered_name(self) -> None:
        saved = password_app.remember_named([], "Router", ["one", "two"])
        self.assertEqual(
            saved,
            [
                password_app.SavedPassword("Router 1", "one"),
                password_app.SavedPassword("Router 2", "two"),
            ],
        )

    def test_a_blank_name_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            password_app.remember_named([], "   ", ["secret"])

    def test_older_unnamed_file_loads_as_untitled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.txt"
            path.write_text("first-secret\nsecond-secret\n", encoding="utf-8")
            self.assertEqual(
                password_app.load_saved_passwords(path),
                [
                    password_app.SavedPassword("Untitled", "first-secret"),
                    password_app.SavedPassword("Untitled 2", "second-secret"),
                ],
            )

    def test_display_puts_the_name_above_the_password(self) -> None:
        text = password_app.saved_display([password_app.SavedPassword("Email", "secret")])
        self.assertEqual(text, "Email\nsecret")

    def test_symlink_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "real.txt"
            target.write_text("keep\n", encoding="utf-8")
            link = Path(directory) / "saved.txt"
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                password_app.store_saved_passwords(
                    [password_app.SavedPassword("Email", "stolen")],
                    link,
                )
            self.assertEqual(target.read_text(encoding="utf-8"), "keep\n")
            with self.assertRaises(ValueError):
                password_app.load_saved_passwords(link)

    def test_missing_file_means_nothing_is_saved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.txt"
            self.assertEqual(password_app.load_saved_passwords(path), [])


class ClipboardTests(unittest.TestCase):
    def test_xclip_receives_the_password_on_stdin(self) -> None:
        with patch("password_app.shutil.which", return_value="/usr/bin/xclip"), patch(
            "password_app.subprocess.run"
        ) as run:
            self.assertTrue(password_app.copy_with_xclip("secret-value"))
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["xclip", "-selection", "clipboard", "-in"])
        self.assertEqual(kwargs["input"], b"secret-value")
        self.assertFalse(kwargs.get("shell", False))

    def test_missing_xclip_does_not_spawn_a_process(self) -> None:
        with patch("password_app.shutil.which", return_value=None), patch(
            "password_app.subprocess.run"
        ) as run:
            self.assertFalse(password_app.copy_with_xclip("secret-value"))
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
