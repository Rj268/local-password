"""Tests for the random password generator."""

from __future__ import annotations

import os
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
    def test_short_mixed_password_is_below_the_strong_line(self) -> None:
        self.assertFalse(generator.is_strong_password("Abcdef1!"))
        self.assertEqual(generator.strength_label("Abcdef1!"), "Fair password")
        self.assertEqual(len("Abcdefghijk1!"), 13)
        self.assertTrue(generator.is_strong_password("Abcdefghijk1!"))
        self.assertEqual(generator.strength_label("Abcdefghijk1!"), "Strong password")

    def test_can_be_strong_follows_entropy(self) -> None:
        pool = string.ascii_letters + string.digits + string.punctuation
        self.assertFalse(generator.can_be_strong(8, pool))
        self.assertTrue(generator.can_be_strong(13, pool))
        self.assertFalse(generator.can_be_strong(12, string.digits))


class CommandLineTests(unittest.TestCase):
    def test_noninteractive_password_is_strong(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            generator.main(["--length", "16", "--digits", "--letters", "--special"])
        password = stdout.getvalue().strip()
        self.assertEqual(len(password), 16)
        self.assertTrue(generator.is_strong_password(password))
        self.assertIn("Strong password", stderr.getvalue())

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

    def test_there_is_no_file_output_option(self) -> None:
        stderr = StringIO()
        with patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as caught:
                generator.main(["--length", "12", "--output", "saved"])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("unrecognized arguments", stderr.getvalue())

    def test_generation_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                with patch("sys.stdout", StringIO()), patch("sys.stderr", StringIO()):
                    generator.main(["--length", "16", "--quiet"])
                self.assertEqual(list(Path(directory).iterdir()), [])
            finally:
                os.chdir(previous)

    def test_copy_flag(self) -> None:
        with patch("pyperclip.copy") as copy, patch("sys.stdout", StringIO()), patch("sys.stderr", StringIO()):
            generator.main(["--length", "12", "--copy"])
        copy.assert_called_once()
        self.assertEqual(len(copy.call_args.args[0]), 12)

    def test_interactive_flow_can_decline_saving(self) -> None:
        answers = iter(["no", "16", "1", "2", "3", "4", "no", "no"])
        stdout = StringIO()
        with patch("builtins.input", side_effect=lambda _prompt: next(answers)), patch("sys.stdout", stdout):
            generator.main([])
        text = stdout.getvalue()
        self.assertIn("Welcome to the Password Generator", text)
        self.assertIn("Generated Password:", text)
        self.assertIn("Password was not copied.", text)
        self.assertIn("Strong password", text)

    def test_interactive_exit_without_character_types(self) -> None:
        answers = iter(["no", "12", "4"])
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

    def test_interactive_repeats_an_unclear_answer(self) -> None:
        answers = iter(["no", "12", "1", "2", "3", "4", "maybe", "no", "no"])
        stdout = StringIO()
        with patch("builtins.input", side_effect=lambda _prompt: next(answers)), patch("sys.stdout", stdout):
            generator.main([])
        text = stdout.getvalue()
        self.assertIn("Please answer yes or no.", text)
        self.assertIn("Password was not copied.", text)

    def test_interactive_can_skip_ambiguous_characters(self) -> None:
        answers = iter(["no", "20", "1", "2", "3", "4", "yes", "no"])
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

    def test_default_symbols_leave_out_shell_metacharacters(self) -> None:
        self.assertEqual(generator.special_characters(), "%+,-./:=@^_")
        full = generator.special_characters(all_special=True)
        self.assertIn("'", full)
        self.assertIn("\\", full)
        self.assertIn("`", full)
        stdout = StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", StringIO()):
            generator.main(["--length", "48", "--quiet"])
        password = stdout.getvalue().strip()
        self.assertTrue(set(password).isdisjoint(generator.SHELL_SENSITIVE_CHARACTERS))

    def test_passphrase_uses_six_words_from_the_eff_list(self) -> None:
        wordlist = generator.load_wordlist()
        self.assertEqual(len(wordlist), 7776)
        self.assertEqual(len(set(wordlist)), 7776)
        stdout = StringIO()
        stderr = StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            generator.main(["--passphrase"])
        words = stdout.getvalue().strip().split()
        self.assertEqual(len(words), 6)
        self.assertTrue(set(words) <= set(wordlist))
        self.assertIn("Strong password", stderr.getvalue())
        self.assertIn("bits", stderr.getvalue())

    def test_five_word_passphrase_is_under_the_strong_line(self) -> None:
        stderr = StringIO()
        with patch("sys.stdout", StringIO()), patch("sys.stderr", stderr):
            generator.main(["--words", "5"])
        self.assertIn("Fair password", stderr.getvalue())

    def test_passphrase_rejects_a_character_length(self) -> None:
        with patch("sys.stderr", StringIO()):
            with self.assertRaises(SystemExit) as caught:
                generator.main(["--passphrase", "--length", "16"])
        self.assertEqual(caught.exception.code, 2)

    def test_interactive_passphrase(self) -> None:
        answers = iter(["yes", "6", "no"])
        stdout = StringIO()
        with patch("builtins.input", side_effect=lambda _prompt: next(answers)), patch("sys.stdout", stdout):
            generator.main([])
        text = stdout.getvalue()
        phrase = text.split("Generated Passphrase:", 1)[1].splitlines()[0].strip()
        self.assertEqual(len(phrase.split()), 6)
        self.assertIn("Strong password", text)
        self.assertIn("Password was not copied.", text)

    def test_entropy_matches_pool_size(self) -> None:
        self.assertAlmostEqual(generator.password_entropy_bits(10, 2), 10.0)
        self.assertIn("about 10 bits", generator.describe_passwords(["a" * 10], 2))

    def test_copy_message_says_copied(self) -> None:
        stderr = StringIO()
        with patch("pyperclip.copy"), patch("sys.stdout", StringIO()), patch("sys.stderr", stderr):
            generator.main(["--length", "12", "--copy"])
        self.assertIn("Password copied.", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
