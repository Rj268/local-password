"""Tests for the random password generator."""

from __future__ import annotations

import os
import stat
import string
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import random_password_generator as generator


class GeneratePasswordTests(unittest.TestCase):
    def test_length_and_alphabet(self) -> None:
        character_list = "abcABC123!?"
        password = generator.generate_password(12, character_list)
        self.assertEqual(len(password), 12)
        self.assertTrue(set(password) <= set(character_list))

    def test_duplicate_characters_are_not_weighted(self) -> None:
        self.assertEqual(generator.unique_characters("aaab"), "ab")

    def test_includes_every_selected_group_when_length_allows(self) -> None:
        character_list = string.digits + string.ascii_letters + string.punctuation
        for _ in range(25):
            password = generator.generate_password(12, character_list)
            self.assertTrue(any(char.isdigit() for char in password))
            self.assertTrue(any(char.islower() for char in password))
            self.assertTrue(any(char.isupper() for char in password))
            self.assertTrue(any(char in string.punctuation for char in password))
            self.assertTrue(generator.is_strong_password(password))

    def test_short_password_stays_inside_the_pool(self) -> None:
        password = generator.generate_password(3, "abcXYZ")
        self.assertEqual(len(password), 3)
        self.assertTrue(set(password) <= set("abcXYZ"))

    def test_rejects_empty_pool_and_bad_lengths(self) -> None:
        with self.assertRaises(ValueError):
            generator.generate_password(8, "")
        with self.assertRaises(ValueError):
            generator.generate_password(0, string.ascii_letters)
        with self.assertRaises(ValueError):
            generator.generate_password(generator.MAX_PASSWORD_LENGTH + 1, string.digits)
        with self.assertRaises(ValueError):
            generator.generate_password(True, string.digits)  # type: ignore[arg-type]

    def test_passwords_differ(self) -> None:
        character_list = string.ascii_letters + string.digits
        passwords = {generator.generate_password(24, character_list) for _ in range(5)}
        self.assertGreater(len(passwords), 1)


class StrengthTests(unittest.TestCase):
    def test_strong_password(self) -> None:
        self.assertTrue(generator.is_strong_password("Abcdef1!"))
        self.assertEqual(generator.strength_label("Abcdef1!"), "Strong Password")

    def test_weak_password_explains_what_is_missing(self) -> None:
        self.assertFalse(generator.is_strong_password("abcdefgh"))
        label = generator.strength_label("abcdefgh")
        self.assertIn("Weak Password", label)
        self.assertIn("an uppercase letter", label)
        self.assertIn("a digit", label)
        self.assertIn("a special character", label)

    def test_can_be_strong_requires_length_and_all_groups(self) -> None:
        pool = string.ascii_letters + string.digits + string.punctuation
        self.assertTrue(generator.can_be_strong(8, pool))
        self.assertFalse(generator.can_be_strong(7, pool))
        self.assertFalse(generator.can_be_strong(12, string.digits))


class FilenameTests(unittest.TestCase):
    def test_sanitizes_path_characters(self) -> None:
        self.assertEqual(generator.sanitize_filename("../etc/passwd"), "etcpasswd")
        self.assertEqual(generator.password_file_path("my-vault").name, "my-vault.txt")
        self.assertEqual(generator.password_file_path("notes.txt").name, "notes.txt")

    def test_rejects_empty_filename(self) -> None:
        with self.assertRaises(ValueError):
            generator.sanitize_filename("../...")

    def test_file_contains_only_the_password_and_is_user_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                path = generator.save_password_to_file("Abcdef1!", "vault")
                self.assertEqual(path.read_text(encoding="utf-8"), "Abcdef1!")
                mode = stat.S_IMODE(path.stat().st_mode)
                self.assertEqual(mode & 0o077, 0)
            finally:
                os.chdir(previous)


class CommandLineTests(unittest.TestCase):
    def test_noninteractive_password_is_strong(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            generator.main(["--length", "16", "--digits", "--letters", "--special"])
        password = stdout.getvalue().strip()
        self.assertEqual(len(password), 16)
        self.assertTrue(generator.is_strong_password(password))
        self.assertIn("Strong Password", stderr.getvalue())

    def test_quiet_prints_only_the_password(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            generator.main(["-l", "10", "-q"])
        password = stdout.getvalue().strip()
        self.assertEqual(len(password), 10)
        self.assertEqual(stderr.getvalue(), "")

    def test_invalid_length_exits(self) -> None:
        with patch("sys.stderr", StringIO()):
            with self.assertRaises(SystemExit) as caught:
                generator.main(["--length", "0", "--digits"])
        self.assertEqual(caught.exception.code, 2)

    def test_output_flag_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                stdout = StringIO()
                with patch("sys.stdout", stdout), patch("sys.stderr", StringIO()):
                    generator.main(["--length", "12", "--output", "saved"])
                password = stdout.getvalue().strip()
                self.assertEqual(Path("saved.txt").read_text(encoding="utf-8"), password)
            finally:
                os.chdir(previous)

    def test_copy_flag(self) -> None:
        with patch("pyperclip.copy") as copy, patch("sys.stdout", StringIO()), patch("sys.stderr", StringIO()):
            generator.main(["--length", "12", "--copy"])
        copy.assert_called_once()
        self.assertEqual(len(copy.call_args.args[0]), 12)

    def test_interactive_flow_can_decline_saving(self) -> None:
        answers = iter(["16", "1", "2", "3", "4", "no", "no"])
        stdout = StringIO()
        with patch("builtins.input", side_effect=lambda _prompt: next(answers)), patch("sys.stdout", stdout):
            generator.main([])
        text = stdout.getvalue()
        self.assertIn("Welcome to the Password Generator", text)
        self.assertIn("Generated Password:", text)
        self.assertIn("Password not saved", text)
        self.assertIn("Strong Password", text)

    def test_interactive_exit_without_character_types(self) -> None:
        answers = iter(["12", "4"])
        stdout = StringIO()
        with patch("builtins.input", side_effect=lambda _prompt: next(answers)), patch("sys.stdout", stdout):
            generator.main([])
        self.assertIn("You have chosen to exit.", stdout.getvalue())
        self.assertNotIn("Generated Password:", stdout.getvalue())

    def test_count_prints_one_password_per_line(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            generator.main(["--length", "12", "--count", "3", "--quiet"])
        passwords = stdout.getvalue().splitlines()
        self.assertEqual(len(passwords), 3)
        self.assertEqual(len(set(passwords)), 3)
        self.assertTrue(all(len(password) == 12 for password in passwords))
        self.assertEqual(stderr.getvalue(), "")

    def test_count_reports_entropy_once(self) -> None:
        stderr = StringIO()
        with patch("sys.stdout", StringIO()), patch("sys.stderr", stderr):
            generator.main(["--length", "16", "--count", "4"])
        text = stderr.getvalue()
        self.assertIn("About ", text)
        self.assertIn("bits of entropy each.", text)
        self.assertIn("4 strong passwords.", text)

    def test_invalid_count_exits(self) -> None:
        with patch("sys.stderr", StringIO()):
            with self.assertRaises(SystemExit) as caught:
                generator.main(["--length", "12", "--count", "0"])
        self.assertEqual(caught.exception.code, 2)

    def test_no_ambiguous_leaves_out_confusable_characters(self) -> None:
        stdout = StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", StringIO()):
            generator.main(["--length", "40", "--no-ambiguous", "--quiet"])
        password = stdout.getvalue().strip()
        self.assertEqual(len(password), 40)
        self.assertTrue(set(password).isdisjoint(generator.AMBIGUOUS_CHARACTERS))
        self.assertTrue(generator.is_strong_password(password))

    def test_existing_output_is_kept_until_force(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                path = Path("saved.txt")
                path.write_text("keep", encoding="utf-8")
                path.chmod(0o644)
                stderr = StringIO()
                with patch("sys.stderr", stderr):
                    with self.assertRaises(SystemExit) as caught:
                        generator.main(["--length", "12", "--output", "saved"])
                self.assertEqual(caught.exception.code, 1)
                self.assertEqual(path.read_text(encoding="utf-8"), "keep")
                self.assertIn("--force", stderr.getvalue())

                stdout = StringIO()
                with patch("sys.stdout", stdout), patch("sys.stderr", StringIO()):
                    generator.main(["--length", "12", "--output", "saved", "--force"])
                self.assertEqual(path.read_text(encoding="utf-8"), stdout.getvalue().strip())
                mode = stat.S_IMODE(path.stat().st_mode)
                self.assertEqual(mode & 0o077, 0)
            finally:
                os.chdir(previous)

    def test_interactive_repeats_an_unclear_answer(self) -> None:
        answers = iter(["12", "1", "2", "3", "4", "maybe", "no", "no"])
        stdout = StringIO()
        with patch("builtins.input", side_effect=lambda _prompt: next(answers)), patch("sys.stdout", stdout):
            generator.main([])
        text = stdout.getvalue()
        self.assertIn("Please answer yes or no.", text)
        self.assertIn("Password not saved", text)

    def test_interactive_can_skip_ambiguous_characters(self) -> None:
        answers = iter(["20", "1", "2", "3", "4", "yes", "no"])
        stdout = StringIO()
        with patch("builtins.input", side_effect=lambda _prompt: next(answers)), patch("sys.stdout", stdout):
            generator.main([])
        text = stdout.getvalue()
        password = text.split("Generated Password:", 1)[1].splitlines()[0].strip()
        self.assertTrue(set(password).isdisjoint(generator.AMBIGUOUS_CHARACTERS))
        self.assertIn("bits", text)


class PoolAndEntropyTests(unittest.TestCase):
    def test_ambiguous_filter_and_empty_pool(self) -> None:
        self.assertEqual(generator.without_ambiguous("a0O1l"), "a")
        with self.assertRaises(ValueError):
            generator.prepare_character_list("0Ool1I|", exclude_ambiguous=True)

    def test_entropy_matches_pool_size(self) -> None:
        self.assertAlmostEqual(generator.password_entropy_bits(10, 2), 10.0)
        self.assertIn("about 10 bits", generator.describe_passwords(["a" * 10], 2))

    def test_symlink_output_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                target = Path("secret.txt")
                target.write_text("keep", encoding="utf-8")
                Path("link.txt").symlink_to(target)
                with patch("sys.stderr", StringIO()):
                    with self.assertRaises(SystemExit) as caught:
                        generator.main(["--length", "12", "--output", "link", "--force"])
                self.assertEqual(caught.exception.code, 1)
                self.assertEqual(target.read_text(encoding="utf-8"), "keep")
            finally:
                os.chdir(previous)

    def test_several_passwords_are_one_per_line_in_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                stdout = StringIO()
                with patch("sys.stdout", stdout), patch("sys.stderr", StringIO()):
                    generator.main(["--length", "8", "--count", "2", "--output", "batch", "--quiet"])
                passwords = stdout.getvalue().splitlines()
                self.assertEqual(Path("batch.txt").read_text(encoding="utf-8").splitlines(), passwords)
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
