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
    def test_save_round_trip_is_private_to_the_user(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "local-password" / "saved.txt"
            password_app.store_saved_passwords(["first-secret", "second-secret"], path)
            self.assertEqual(
                password_app.load_saved_passwords(path),
                ["first-secret", "second-secret"],
            )
            file_mode = stat.S_IMODE(path.stat().st_mode)
            directory_mode = stat.S_IMODE(path.parent.stat().st_mode)
            self.assertEqual(file_mode & 0o077, 0)
            self.assertEqual(directory_mode & 0o077, 0)

    def test_new_passwords_are_kept_once_and_listed_first(self) -> None:
        saved = password_app.remember_passwords(["older"], ["newer", "older"])
        self.assertEqual(saved, ["newer", "older"])

    def test_symlink_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "real.txt"
            target.write_text("keep\n", encoding="utf-8")
            link = Path(directory) / "saved.txt"
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                password_app.store_saved_passwords(["stolen"], link)
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
