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


class VaultTests(unittest.TestCase):
    def _items(self) -> list[password_app.SavedPassword]:
        return [password_app.SavedPassword("Email", 'p@ss "word"\\')]

    def test_vault_round_trip_hides_the_password(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.vault"
            material = password_app.new_vault_key("a-long-secret", n=2**14)
            password_app.write_vault(material, self._items(), path)
            blob = path.read_bytes()
            self.assertNotIn(b"Email", blob)
            self.assertNotIn(b"word", blob)
            self.assertNotIn(b"a-long-secret", blob)
            opened, items = password_app.open_vault("a-long-secret", path)
            self.assertEqual(items, self._items())
            self.assertEqual(opened.n, 2**14)
            self.assertGreaterEqual(password_app.SCRYPT_N, 2**15)
            mode = stat.S_IMODE(path.stat().st_mode)
            self.assertEqual(mode & 0o077, 0)

    def test_wrong_passphrase_does_not_unlock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.vault"
            material = password_app.new_vault_key("a-long-secret", n=2**14)
            password_app.write_vault(material, self._items(), path)
            with self.assertRaises(ValueError) as caught:
                password_app.open_vault("another-secret", path)
            self.assertIn("did not unlock", str(caught.exception))
            tweaked = bytearray(path.read_bytes())
            tweaked[-1] ^= 0x01
            path.write_bytes(bytes(tweaked))
            with self.assertRaises(ValueError):
                password_app.open_vault("a-long-secret", path)

    def test_plaintext_file_can_be_erased(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plain = Path(directory) / "saved.txt"
            password_app.store_saved_passwords(self._items(), plain)
            vault = Path(directory) / "saved.vault"
            material = password_app.new_vault_key("a-long-secret", n=2**14)
            password_app.write_vault(material, password_app.load_saved_passwords(plain), vault)
            password_app.erase_saved_file(plain)
            self.assertFalse(plain.exists())
            _key, items = password_app.open_vault("a-long-secret", vault)
            self.assertEqual(items, self._items())

    def test_short_passphrase_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            password_app.new_vault_key("short")


class EnterpriseEntropyTests(unittest.TestCase):
    def test_meter_fills_toward_256_bits(self) -> None:
        self.assertEqual(password_app.METER_CAP_BITS, 256)

    def test_full_alphabet_reaches_256_bits_at_40_characters(self) -> None:
        pool = password_app.character_pool(digits=True, letters=True, symbols=True)
        alphabet = len(password_app.generator.unique_characters(pool))
        length = password_app.length_for_bits(pool)
        self.assertEqual(length, 40)
        reached = password_app.generator.password_entropy_bits(length, alphabet)
        short = password_app.generator.password_entropy_bits(length - 1, alphabet)
        self.assertGreaterEqual(reached, 256)
        self.assertLess(short, 256)
        result = password_app.generate(
            mode="characters",
            length=length,
            words=6,
            count=1,
            digits=True,
            letters=True,
            symbols=True,
        )
        self.assertEqual(result.fraction, 1.0)
        self.assertEqual(result.label, "Strong")
        self.assertEqual(len(result.text), 40)

    def test_twenty_words_reach_256_bits(self) -> None:
        self.assertEqual(password_app.words_for_bits(), 20)
        size = len(password_app.generator.load_wordlist())
        short = password_app.generator.passphrase_entropy_bits(19, size)
        reached = password_app.generator.passphrase_entropy_bits(20, size)
        self.assertLess(short, 256)
        self.assertGreaterEqual(reached, 256)
        result = password_app.generate(
            mode="passphrase",
            length=16,
            words=20,
            count=1,
            digits=True,
            letters=True,
            symbols=True,
        )
        self.assertEqual(result.fraction, 1.0)
        self.assertEqual(len(result.text.split()), 20)


class PassphraseWarningTests(unittest.TestCase):
    def test_warning_says_a_lost_passphrase_cannot_be_recovered(self) -> None:
        self.assertIn("cannot be recovered", password_app.PASSPHRASE_LOSS_WARNING)
        self.assertIn("lose this passphrase", password_app.PASSPHRASE_LOSS_WARNING)

    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a graphical session")
    def test_new_passphrase_dialog_shows_the_warning(self) -> None:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, Gtk

        password_app.install_styles(Gtk, Gdk)
        window = password_app.PasswordWindow(Gtk, Gdk)
        seen: list[str] = []

        def capture_and_cancel(dialog):
            def walk(widget) -> None:
                if isinstance(widget, Gtk.Label):
                    seen.append(widget.get_text())
                for child in getattr(widget, "get_children", lambda: [])():
                    walk(child)

            walk(dialog.get_content_area())
            return Gtk.ResponseType.CANCEL

        with patch.object(Gtk.Dialog, "run", capture_and_cancel):
            self.assertIsNone(window._prompt_passphrase(confirm=True))
        self.assertIn(password_app.PASSPHRASE_LOSS_WARNING, seen)
        window.window.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)


class BatchSaveTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a graphical session")
    def test_one_password_from_a_batch_can_be_saved_alone(self) -> None:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, Gtk

        with tempfile.TemporaryDirectory() as directory:
            previous = os.environ.get("XDG_DATA_HOME")
            os.environ["XDG_DATA_HOME"] = directory
            try:
                password_app.install_styles(Gtk, Gdk)
                window = password_app.PasswordWindow(Gtk, Gdk)
                window.count.set_value(3)
                window.on_generate(None)
                self.assertEqual(len(window.batch), 3)
                self.assertFalse(window.single_box.get_visible())
                self.assertTrue(window.batch_scroll.get_visible())
                entries = [
                    child
                    for child in _gtk_descendants(window.batch_box)
                    if isinstance(child, Gtk.Entry)
                ]
                self.assertEqual(len(entries), 3)
                entries[1].set_text("Bank")
                window._prompt_passphrase = lambda **_kwargs: "verify-passphrase-ok"
                window.on_save_one(window.batch[1], entries[1], window.status)
                self.assertEqual([item.name for item in window.saved], ["Bank"])
                self.assertEqual(window.saved[0].password, window.batch[1])
                self.assertNotIn(window.batch[0], [item.password for item in window.saved])
                self.assertNotIn(window.batch[2], [item.password for item in window.saved])
                self.assertEqual(window.section, "create")
                entries[1].set_text("   ")
                window.on_save_one(window.batch[0], entries[1], window.status)
                self.assertEqual([item.name for item in window.saved], ["Bank"])
                window.window.destroy()
                while Gtk.events_pending():
                    Gtk.main_iteration_do(False)
            finally:
                if previous is None:
                    os.environ.pop("XDG_DATA_HOME", None)
                else:
                    os.environ["XDG_DATA_HOME"] = previous


def _gtk_descendants(widget):
    found = []
    for child in getattr(widget, "get_children", lambda: [])():
        found.append(child)
        found.extend(_gtk_descendants(child))
    return found


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
