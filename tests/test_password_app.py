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
                uppercase=False,
                lowercase=False,
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
                    uppercase=True,
                    lowercase=True,
                    symbols=True,
                )
                self.assertEqual(list(Path(directory).iterdir()), [])
            finally:
                os.chdir(previous)
        self.assertEqual(result.label, "Very strong")
        self.assertEqual(len(result.text), 16)
        self.assertIn("bits", result.bits_label)
        self.assertEqual(result.note, "")

    def test_five_words_are_fair(self) -> None:
        result = password_app.generate(
            mode="passphrase",
            length=16,
            words=5,
            count=1,
        )
        self.assertEqual(len(result.text.split()), 5)
        self.assertEqual(result.label, "Fair")
        self.assertIn("75", result.note)

    def test_six_words_are_strong(self) -> None:
        result = password_app.generate(
            mode="passphrase",
            length=16,
            words=6,
            count=2,
        )
        lines = result.text.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(len(line.split()) == 6 for line in lines))
        self.assertEqual(result.label, "Strong")
        self.assertIn("each", result.bits_label)

    def test_exclude_ambiguous_drops_confusable_characters(self) -> None:
        pool = password_app.character_pool(
            digits=True,
            uppercase=True,
            lowercase=True,
            symbols=False,
            exclude_ambiguous=True,
        )
        for char in "0Ool1I|":
            self.assertNotIn(char, pool)
        result = password_app.generate(
            mode="characters",
            length=24,
            words=6,
            count=1,
            digits=True,
            uppercase=True,
            lowercase=True,
            symbols=False,
            exclude_ambiguous=True,
        )
        for char in "0Ool1I|":
            self.assertNotIn(char, result.text)

    def test_uppercase_only_pool(self) -> None:
        pool = password_app.character_pool(uppercase=True)
        self.assertTrue(set(pool) <= set(string.ascii_uppercase))

    def test_hyphen_passphrase_and_capitalize(self) -> None:
        result = password_app.generate(
            mode="passphrase",
            length=16,
            words=4,
            count=1,
            separator="-",
            capitalize=True,
        )
        parts = result.text.split("-")
        self.assertEqual(len(parts), 4)
        self.assertTrue(all(part[:1].isupper() for part in parts))

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
        existing = [
            password_app.SavedPassword(
                "Email",
                "old",
                username="me@example.com",
                created="2020-01-01T00:00:00Z",
            )
        ]
        saved = password_app.remember_named(existing, "  Email  ", ["new"])
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].name, "Email")
        self.assertEqual(saved[0].password, "new")
        self.assertEqual(saved[0].username, "me@example.com")
        self.assertEqual(saved[0].created, "2020-01-01T00:00:00Z")
        self.assertTrue(saved[0].modified)

    def test_several_passwords_share_a_numbered_name(self) -> None:
        saved = password_app.remember_named([], "Router", ["one", "two"])
        self.assertEqual([(item.name, item.password) for item in saved], [("Router 1", "one"), ("Router 2", "two")])

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

    def test_recovery_key_opens_the_vault_without_being_stored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.vault"
            recovery = password_app.new_recovery_key()
            self.assertEqual(len(recovery.split()), password_app.RECOVERY_WORD_COUNT)
            material = password_app.new_vault_key("a-long-secret", recovery, n=2**14)
            password_app.write_vault(material, self._items(), path)
            blob = path.read_bytes()
            self.assertTrue(blob.startswith(b"LPV2"))
            self.assertNotIn(b"a-long-secret", blob)
            self.assertNotIn(recovery.encode("utf-8"), blob)
            self.assertNotIn(b"Email", blob)
            opened, by_phrase = password_app.open_vault("a-long-secret", path)
            self.assertEqual(by_phrase, self._items())
            extra = [password_app.SavedPassword("Bank", "second-secret")]
            password_app.write_vault(opened, self._items() + extra, path)
            rewritten = path.read_bytes()
            self.assertNotIn(recovery.encode("utf-8"), rewritten)
            self.assertNotIn(b"second-secret", rewritten)
            typed = recovery.upper().replace(" ", "  ")
            _key, by_recovery = password_app.open_vault(typed, path)
            self.assertEqual(by_recovery, self._items() + extra)
            with self.assertRaises(ValueError) as caught:
                password_app.open_vault("another-secret", path)
            self.assertIn("did not unlock", str(caught.exception))

    def test_reused_password_groups_and_warning(self) -> None:
        items = [
            password_app.SavedPassword("Email", "shared"),
            password_app.SavedPassword("Bank", "shared"),
            password_app.SavedPassword("Unique", "solo"),
        ]
        groups = password_app.reused_password_groups(items)
        self.assertEqual(set(groups), {"shared"})
        self.assertEqual(groups["shared"], ["Email", "Bank"])
        self.assertEqual(
            password_app.reuse_warning_for(items[0], items),
            "Same password as Bank.",
        )
        self.assertEqual(password_app.reuse_warning_for(items[2], items), "")

    def test_browseable_url_accepts_http_and_adds_https(self) -> None:
        self.assertEqual(password_app.browseable_url("https://mail.example"), "https://mail.example")
        self.assertEqual(password_app.browseable_url("mail.example"), "https://mail.example")
        self.assertEqual(password_app.browseable_url("localhost:8080"), "https://localhost:8080")
        self.assertIsNone(password_app.browseable_url(""))
        self.assertIsNone(password_app.browseable_url("javascript:alert(1)"))
        self.assertIsNone(password_app.browseable_url("file:///tmp/x"))

    def test_password_health_flags_weak_and_reused(self) -> None:
        weak = password_app.SavedPassword("Old", "abc123")
        strong = password_app.SavedPassword("Bank", "correct-horse-battery-staple-extra")
        reused_a = password_app.SavedPassword("Email", "shared-secret-value")
        reused_b = password_app.SavedPassword("Shop", "shared-secret-value")
        items = [weak, strong, reused_a, reused_b]
        self.assertTrue(password_app.entry_is_weak(weak.password))
        self.assertFalse(password_app.entry_is_weak(strong.password))
        self.assertEqual(password_app.weak_password_names(items), ["Old"])
        warning = password_app.strength_warning_for(weak)
        self.assertTrue(warning.endswith("bits)."))
        self.assertIn("password", warning)
        self.assertEqual(password_app.strength_warning_for(strong), "")
        self.assertTrue(password_app.entry_needs_attention(weak, items))
        self.assertFalse(password_app.entry_needs_attention(strong, items))
        self.assertTrue(password_app.entry_needs_attention(reused_a, items))
        weak_count, reuse_count, attention_count = password_app.password_health_summary(items)
        self.assertEqual(weak_count, 1)
        self.assertEqual(reuse_count, 1)
        self.assertEqual(attention_count, 3)

    def test_replace_entry_password_keeps_fields_and_is_strong(self) -> None:
        item = password_app.SavedPassword(
            "Old",
            "abc123",
            username="me",
            url="https://old.example",
            notes="keep",
            category="web",
            favorite=True,
            created="2024-01-01T00:00:00Z",
        )
        fresh = password_app.strong_replacement_password()
        self.assertFalse(password_app.entry_is_weak(fresh))
        updated = password_app.replace_entry_password([item], item, fresh)
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].name, "Old")
        self.assertEqual(updated[0].password, fresh)
        self.assertEqual(updated[0].username, "me")
        self.assertEqual(updated[0].url, "https://old.example")
        self.assertEqual(updated[0].notes, "keep")
        self.assertEqual(updated[0].category, "web")
        self.assertTrue(updated[0].favorite)
        self.assertEqual(updated[0].created, "2024-01-01T00:00:00Z")
        self.assertTrue(updated[0].modified)
        self.assertNotEqual(updated[0].modified, item.modified)

    def test_change_vault_credentials_keeps_items_and_retires_old_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.vault"
            old_recovery = password_app.new_recovery_key()
            material = password_app.new_vault_key("old-passphrase", old_recovery, n=2**14)
            password_app.write_vault(material, self._items(), path)
            new_recovery = password_app.new_recovery_key()
            fresh, shown = password_app.change_vault_credentials(
                self._items(),
                "new-passphrase",
                recovery_key=new_recovery,
                path=path,
                n=2**14,
            )
            self.assertEqual(shown, password_app.require_recovery_key(new_recovery))
            self.assertTrue(fresh.recovery_wrap)
            _key, by_phrase = password_app.open_vault("new-passphrase", path)
            self.assertEqual(by_phrase, self._items())
            _key, by_recovery = password_app.open_vault(new_recovery, path)
            self.assertEqual(by_recovery, self._items())
            with self.assertRaises(ValueError):
                password_app.open_vault("old-passphrase", path)
            with self.assertRaises(ValueError):
                password_app.open_vault(old_recovery, path)

    def test_optional_fields_round_trip_and_unknown_keys_survive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.vault"
            material = password_app.new_vault_key("a-long-secret", n=2**14)
            rich = password_app.SavedPassword(
                "Email",
                "secret",
                username="me@example.com",
                url="https://mail.example",
                notes="work account",
                category="Mail",
                favorite=True,
                created="2020-01-01T00:00:00Z",
                modified="2020-02-01T00:00:00Z",
                extras={"label_color": "green", "priority": 2},
            )
            password_app.write_vault(material, [rich], path)
            _key, items = password_app.open_vault("a-long-secret", path)
            self.assertEqual(items, [rich])

    def test_old_name_password_entries_still_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.vault"
            material = password_app.new_vault_key("a-long-secret", n=2**14)
            password_app.write_vault(
                material,
                [password_app.SavedPassword("Email", "secret")],
                path,
            )
            _key, items = password_app.open_vault("a-long-secret", path)
            self.assertEqual(items[0].name, "Email")
            self.assertEqual(items[0].password, "secret")
            self.assertEqual(items[0].username, "")
            self.assertFalse(items[0].favorite)

    def test_upsert_can_rename_and_edit_fields(self) -> None:
        existing = [
            password_app.SavedPassword(
                "Email",
                "secret",
                created="2020-01-01T00:00:00Z",
            )
        ]
        edited = password_app.SavedPassword(
            "Work email",
            "secret",
            username="me",
            category="Mail",
            favorite=True,
        )
        updated = password_app.upsert_entry(existing, edited, previous_name="Email")
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].name, "Work email")
        self.assertEqual(updated[0].username, "me")
        self.assertEqual(updated[0].created, "2020-01-01T00:00:00Z")
        self.assertTrue(updated[0].favorite)

    def test_search_matches_username_and_category(self) -> None:
        item = password_app.SavedPassword(
            "Mailbox",
            "secret",
            username="me@example.com",
            category="Mail",
        )
        self.assertTrue(password_app.entry_matches(item, "example"))
        self.assertTrue(password_app.entry_matches(item, "mail"))
        self.assertFalse(password_app.entry_matches(item, "bank"))


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
        self.assertEqual(result.label, "Very strong")
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


class AppearanceTests(unittest.TestCase):
    def test_dark_choice_stays_private_on_this_computer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = os.environ.get("XDG_DATA_HOME")
            os.environ["XDG_DATA_HOME"] = directory
            try:
                self.assertFalse(password_app.load_dark_mode())
                password_app.store_appearance(True)
                path = password_app.appearance_path()
                self.assertEqual(path.read_text(encoding="utf-8"), "dark\n")
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                self.assertTrue(password_app.load_dark_mode())
                password_app.store_appearance(False)
                self.assertFalse(password_app.load_dark_mode())
                path.unlink()
                path.symlink_to(path.with_name("other"))
                with self.assertRaises(ValueError):
                    password_app.store_appearance(True)
                self.assertFalse(password_app.load_dark_mode())
            finally:
                if previous is None:
                    os.environ.pop("XDG_DATA_HOME", None)
                else:
                    os.environ["XDG_DATA_HOME"] = previous

    def test_security_preferences_stay_private_on_this_computer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = os.environ.get("XDG_DATA_HOME")
            os.environ["XDG_DATA_HOME"] = directory
            try:
                defaults = password_app.load_preferences()
                self.assertEqual(defaults.clipboard_clear_seconds, 30)
                self.assertEqual(defaults.auto_lock_seconds, 300)
                password_app.store_preferences(
                    password_app.Preferences(clipboard_clear_seconds=15, auto_lock_seconds=60)
                )
                path = password_app.preferences_path()
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                loaded = password_app.load_preferences()
                self.assertEqual(loaded.clipboard_clear_seconds, 15)
                self.assertEqual(loaded.auto_lock_seconds, 60)
                path.write_text(
                    "clipboard_clear_seconds=999\nauto_lock_seconds=abc\n",
                    encoding="utf-8",
                )
                repaired = password_app.load_preferences()
                self.assertEqual(repaired.clipboard_clear_seconds, 30)
                self.assertEqual(repaired.auto_lock_seconds, 300)
                path.unlink()
                path.symlink_to(path.with_name("other"))
                with self.assertRaises(ValueError):
                    password_app.store_preferences(password_app.Preferences())
            finally:
                if previous is None:
                    os.environ.pop("XDG_DATA_HOME", None)
                else:
                    os.environ["XDG_DATA_HOME"] = previous

    def test_vault_blob_helper_rejects_junk(self) -> None:
        self.assertFalse(password_app.is_vault_blob(b"not-a-vault"))
        self.assertFalse(password_app.is_vault_blob(b"LPV2" + b"\0" * 10))
        self.assertTrue(password_app.is_vault_blob(b"LPV2" + b"\0" * 44))

    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a graphical session")
    def test_dark_switch_changes_the_window(self) -> None:
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
                self.assertEqual(window.dark_button.get_label(), "Dark    Off")
                self.assertFalse(window.window.get_style_context().has_class("dark"))
                window.on_toggle_dark()
                self.assertEqual(window.dark_button.get_label(), "Dark    On")
                self.assertTrue(window.window.get_style_context().has_class("dark"))
                self.assertTrue(password_app.load_dark_mode())
                window.window.destroy()
                while Gtk.events_pending():
                    Gtk.main_iteration_do(False)
            finally:
                if previous is None:
                    os.environ.pop("XDG_DATA_HOME", None)
                else:
                    os.environ["XDG_DATA_HOME"] = previous


class PassphraseWarningTests(unittest.TestCase):
    def test_warning_says_a_lost_passphrase_cannot_be_recovered(self) -> None:
        self.assertIn("cannot be recovered", password_app.PASSPHRASE_LOSS_WARNING)
        self.assertIn("passphrase", password_app.PASSPHRASE_LOSS_WARNING)
        self.assertIn("recovery key", password_app.PASSPHRASE_LOSS_WARNING)

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


class CreatePageTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a graphical session")
    def test_create_page_stays_filled_after_opening_saved_first(self) -> None:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, Gtk

        password_app.install_styles(Gtk, Gdk)
        window = password_app.PasswordWindow(Gtk, Gdk)
        self.assertEqual(window.section, "dashboard")
        self.assertTrue(window.dashboard_view.get_visible())
        window.show_section("saved")
        window.window.show_all()
        window.show_section("create")
        self.assertEqual(window.section, "generate")
        self.assertTrue(window.generate_button.get_visible())
        self.assertTrue(window.length.get_visible())
        self.assertTrue(window.digits.get_visible())
        self.assertTrue(window.uppercase.get_visible())
        self.assertTrue(window.lowercase.get_visible())
        self.assertTrue(window.ambiguous.get_visible())
        self.assertTrue(window.single_box.get_visible())
        self.assertTrue(window.create_view.get_visible())
        self.assertFalse(window.settings_view.get_visible())
        self.assertFalse(window.saved_view.get_visible())
        self.assertFalse(window.dashboard_view.get_visible())
        window.show_section("settings")
        self.assertTrue(window.settings_view.get_visible())
        self.assertTrue(window.dark_button.get_visible())
        self.assertTrue(window.send_button.get_visible())
        self.assertTrue(window.receive_button.get_visible())
        self.assertFalse(window.create_view.get_visible())
        self.assertFalse(window.saved_view.get_visible())
        window.show_section("dashboard")
        self.assertTrue(window.dashboard_view.get_visible())
        self.assertTrue(window.dashboard_generate.get_visible())
        self.assertEqual(window.page_title.get_text(), "Dashboard")
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
                window.show_section("generate")
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
                window._confirm_recovery_key = lambda _key: True
                window.on_save_one(window.batch[1], entries[1], window.status)
                self.assertEqual([item.name for item in window.saved], ["Bank"])
                self.assertEqual(window.saved[0].password, window.batch[1])
                self.assertNotIn(window.batch[0], [item.password for item in window.saved])
                self.assertNotIn(window.batch[2], [item.password for item in window.saved])
                self.assertEqual(window.section, "generate")
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


class WindowsPrepTests(unittest.TestCase):
    def test_wordlist_lives_next_to_the_program(self) -> None:
        self.assertTrue(password_app.generator.WORDLIST_PATH.is_file())
        self.assertEqual(
            password_app.generator.app_root(),
            password_app.generator.WORDLIST_PATH.parent,
        )

    def test_windows_vault_uses_local_appdata(self) -> None:
        with patch.object(password_app.sys, "platform", "win32"), patch.dict(
            os.environ, {"LOCALAPPDATA": r"C:\Users\me\AppData\Local"}, clear=False
        ):
            previous = os.environ.pop("XDG_DATA_HOME", None)
            try:
                path = password_app.saved_passwords_path()
            finally:
                if previous is not None:
                    os.environ["XDG_DATA_HOME"] = previous
        self.assertEqual(
            path,
            Path(r"C:\Users\me\AppData\Local") / "local-password" / "saved.txt",
        )

    def test_windows_clipboard_is_not_used_here(self) -> None:
        self.assertFalse(password_app.generator.copy_with_windows("secret-value"))


if __name__ == "__main__":
    unittest.main()
