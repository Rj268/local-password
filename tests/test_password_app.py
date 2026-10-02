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

    def test_exclude_specific_characters_from_pool(self) -> None:
        pool = password_app.character_pool(
            digits=True,
            uppercase=True,
            lowercase=True,
            symbols=True,
            exclude="$!@",
        )
        for char in "$!@":
            self.assertNotIn(char, pool)
        result = password_app.generate(
            mode="characters",
            length=32,
            words=6,
            count=1,
            digits=True,
            uppercase=True,
            lowercase=True,
            symbols=True,
            exclude="$!@",
        )
        for char in "$!@":
            self.assertNotIn(char, result.text)
        self.assertIn("extra characters", result.note)
        with self.assertRaises(ValueError):
            password_app.character_pool(digits=True, exclude="0123456789")

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

    def test_optional_copy_fields_for_url_and_notes(self) -> None:
        bare = password_app.SavedPassword("Bare", "secret-value-here")
        self.assertEqual(password_app.optional_copy_fields(bare), [])
        with_url = password_app.SavedPassword(
            "Mail",
            "secret-value-here",
            url="  mail.example/login  ",
        )
        self.assertEqual(
            password_app.optional_copy_fields(with_url),
            [("Copy URL", "mail.example/login")],
        )
        with_notes = password_app.SavedPassword(
            "Bank",
            "secret-value-here",
            notes="recovery codes\nkeep private",
        )
        self.assertEqual(
            password_app.optional_copy_fields(with_notes),
            [("Copy notes", "recovery codes\nkeep private")],
        )
        both = password_app.SavedPassword(
            "Work",
            "secret-value-here",
            url="https://work.example",
            notes="  desk drawer  ",
        )
        self.assertEqual(
            password_app.optional_copy_fields(both),
            [
                ("Copy URL", "https://work.example"),
                ("Copy notes", "  desk drawer  "),
            ],
        )
        whitespace_only = password_app.SavedPassword(
            "Empty",
            "secret-value-here",
            url="   ",
            notes="\n\t",
        )
        self.assertEqual(password_app.optional_copy_fields(whitespace_only), [])

    def test_login_copy_text_joins_username_and_password(self) -> None:
        bare = password_app.SavedPassword("Bare", "secret-value-here")
        self.assertEqual(password_app.login_copy_text(bare), "")
        whitespace_user = password_app.SavedPassword(
            "Empty",
            "secret-value-here",
            username="   ",
        )
        self.assertEqual(password_app.login_copy_text(whitespace_user), "")
        with_user = password_app.SavedPassword(
            "Mail",
            "secret-value-here",
            username="  me@example.com  ",
        )
        self.assertEqual(
            password_app.login_copy_text(with_user),
            "me@example.com\tsecret-value-here",
        )

    def test_password_health_flags_weak_and_reused(self) -> None:
        from datetime import date

        today = date(2024, 12, 1)
        recent = "2024-11-15T00:00:00Z"
        weak = password_app.SavedPassword("Old", "abc123", modified=recent)
        strong = password_app.SavedPassword(
            "Bank",
            "correct-horse-battery-staple-extra",
            modified=recent,
        )
        reused_a = password_app.SavedPassword(
            "Email",
            "shared-secret-value",
            modified=recent,
        )
        reused_b = password_app.SavedPassword(
            "Shop",
            "shared-secret-value",
            modified=recent,
        )
        items = [weak, strong, reused_a, reused_b]
        self.assertTrue(password_app.entry_is_weak(weak.password))
        self.assertFalse(password_app.entry_is_weak(strong.password))
        self.assertEqual(password_app.weak_password_names(items), ["Old"])
        warning = password_app.strength_warning_for(weak)
        self.assertTrue(warning.endswith("bits)."))
        self.assertIn("password", warning)
        self.assertEqual(password_app.strength_warning_for(strong), "")
        self.assertTrue(password_app.entry_needs_attention(weak, items, today=today))
        self.assertFalse(password_app.entry_needs_attention(strong, items, today=today))
        self.assertTrue(password_app.entry_needs_attention(reused_a, items, today=today))
        weak_count, reuse_count, stale_count, attention_count = password_app.password_health_summary(
            items, today=today
        )
        self.assertEqual(weak_count, 1)
        self.assertEqual(reuse_count, 1)
        self.assertEqual(stale_count, 0)
        self.assertEqual(attention_count, 3)

    def test_stale_password_flags_old_unchanged_entries(self) -> None:
        from datetime import date

        today = date(2024, 12, 1)
        stale = password_app.SavedPassword(
            "Legacy",
            "correct-horse-battery-staple-extra",
            modified="2024-01-01T00:00:00Z",
        )
        fresh = password_app.SavedPassword(
            "Current",
            "correct-horse-battery-staple-fresh",
            modified="2024-11-01T00:00:00Z",
        )
        created_only = password_app.SavedPassword(
            "CreatedOnly",
            "correct-horse-battery-staple-created",
            created="2023-01-01T00:00:00Z",
        )
        self.assertTrue(password_app.entry_is_stale(stale, today=today))
        self.assertFalse(password_app.entry_is_stale(fresh, today=today))
        self.assertTrue(password_app.entry_is_stale(created_only, today=today))
        self.assertEqual(
            password_app.stale_warning_for(stale, today=today),
            "Not changed since 2024-01-01.",
        )
        self.assertEqual(password_app.stale_warning_for(fresh, today=today), "")
        items = [stale, fresh, created_only]
        self.assertEqual(
            password_app.stale_password_names(items, today=today),
            ["Legacy", "CreatedOnly"],
        )
        self.assertTrue(password_app.entry_needs_attention(stale, items, today=today))
        self.assertFalse(password_app.entry_needs_attention(fresh, items, today=today))
        weak_count, reuse_count, stale_count, attention_count = password_app.password_health_summary(
            items, today=today
        )
        self.assertEqual(weak_count, 0)
        self.assertEqual(reuse_count, 0)
        self.assertEqual(stale_count, 2)
        self.assertEqual(attention_count, 2)

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
        self.assertEqual(len(updated[0].history), 1)
        self.assertEqual(updated[0].history[0].password, "abc123")

    def test_duplicate_entry_copies_fields_and_names_uniquely(self) -> None:
        item = password_app.SavedPassword(
            "Bank",
            "secret-bank-value",
            username="me",
            url="https://bank.example",
            notes="keep",
            category="finance",
            favorite=True,
            created="2024-01-01T00:00:00Z",
            modified="2024-02-01T00:00:00Z",
            last_used="2024-03-01T00:00:00Z",
            history=(password_app.PasswordRevision("old-secret", "2024-01-15T00:00:00Z"),),
        )
        other = password_app.SavedPassword("Email", "secret-email-value")
        updated = password_app.duplicate_entry([item, other], item, when="2024-04-01T00:00:00Z")
        self.assertEqual(updated[0].name, "Bank (copy)")
        self.assertEqual(updated[0].password, "secret-bank-value")
        self.assertEqual(updated[0].username, "me")
        self.assertEqual(updated[0].url, "https://bank.example")
        self.assertEqual(updated[0].notes, "keep")
        self.assertEqual(updated[0].category, "finance")
        self.assertTrue(updated[0].favorite)
        self.assertEqual(updated[0].created, "2024-04-01T00:00:00Z")
        self.assertEqual(updated[0].modified, "2024-04-01T00:00:00Z")
        self.assertEqual(updated[0].last_used, "")
        self.assertEqual(updated[0].history, ())
        self.assertEqual(updated[1].name, "Bank")
        self.assertEqual(updated[1].last_used, "2024-03-01T00:00:00Z")
        self.assertEqual(len(updated[1].history), 1)
        again = password_app.duplicate_entry(updated, updated[1], when="2024-04-02T00:00:00Z")
        self.assertEqual(again[0].name, "Bank (copy 2)")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.vault"
            material = password_app.new_vault_key("passphrase-here", password_app.new_recovery_key(), n=2**14)
            password_app.write_vault(material, again, path)
            _key, loaded = password_app.open_vault("passphrase-here", path)
            names = {entry.name for entry in loaded}
            self.assertEqual(names, {"Bank", "Bank (copy)", "Bank (copy 2)", "Email"})

    def test_toggle_entry_favorite_keeps_timestamps(self) -> None:
        item = password_app.SavedPassword(
            "Bank",
            "secret-bank-value",
            favorite=False,
            created="2024-01-01T00:00:00Z",
            modified="2024-02-01T00:00:00Z",
            last_used="2024-03-01T00:00:00Z",
        )
        other = password_app.SavedPassword("Email", "secret-email-value", favorite=True)
        updated = password_app.toggle_entry_favorite([item, other], item)
        self.assertTrue(updated[0].favorite)
        self.assertEqual(updated[0].modified, "2024-02-01T00:00:00Z")
        self.assertEqual(updated[0].last_used, "2024-03-01T00:00:00Z")
        self.assertEqual(updated[0].password, "secret-bank-value")
        self.assertTrue(updated[1].favorite)
        cleared = password_app.toggle_entry_favorite(updated, updated[0])
        self.assertFalse(cleared[0].favorite)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.vault"
            material = password_app.new_vault_key("passphrase-here", password_app.new_recovery_key(), n=2**14)
            password_app.write_vault(material, cleared, path)
            _key, loaded = password_app.open_vault("passphrase-here", path)
            loaded_bank = next(entry for entry in loaded if entry.name == "Bank")
            self.assertFalse(loaded_bank.favorite)
            self.assertEqual(loaded_bank.modified, "2024-02-01T00:00:00Z")

    def test_last_used_label_and_recently_used_entries(self) -> None:
        alpha = password_app.SavedPassword(
            "Alpha",
            "secret-alpha-value",
            modified="2024-01-02T00:00:00Z",
        )
        beta = password_app.SavedPassword(
            "Beta",
            "secret-beta-value",
            modified="2024-03-01T00:00:00Z",
            last_used="2024-02-01T12:30:00Z",
        )
        gamma = password_app.SavedPassword(
            "Gamma",
            "secret-gamma-value",
            modified="2024-01-01T00:00:00Z",
            last_used="2024-04-01T08:00:00Z",
        )
        self.assertEqual(password_app.last_used_label(alpha), "Not used yet")
        self.assertEqual(password_app.last_used_label(beta), "Last used 2024-02-01")
        recent = password_app.recently_used_entries([alpha, beta, gamma], 2)
        self.assertEqual([item.name for item in recent], ["Gamma", "Beta"])
        unused_only = password_app.recently_used_entries([alpha], 5)
        self.assertEqual([item.name for item in unused_only], ["Alpha"])

    def test_remove_and_restore_entry(self) -> None:
        bank = password_app.SavedPassword(
            "Bank",
            "secret-bank-value",
            username="me",
            notes="keep",
            favorite=True,
            created="2024-01-01T00:00:00Z",
            modified="2024-02-01T00:00:00Z",
            last_used="2024-03-01T00:00:00Z",
            history=(password_app.PasswordRevision("old-secret", "2024-01-15T00:00:00Z"),),
        )
        email = password_app.SavedPassword("Email", "secret-email-value")
        removed = password_app.remove_entry([bank, email], bank)
        self.assertEqual([item.name for item in removed], ["Email"])
        restored = password_app.restore_removed_entry(removed, bank)
        self.assertEqual(restored[0].name, "Bank")
        self.assertEqual(restored[0].password, "secret-bank-value")
        self.assertEqual(restored[0].username, "me")
        self.assertEqual(restored[0].notes, "keep")
        self.assertTrue(restored[0].favorite)
        self.assertEqual(restored[0].last_used, "2024-03-01T00:00:00Z")
        self.assertEqual(len(restored[0].history), 1)
        conflicted = password_app.restore_removed_entry(
            [password_app.SavedPassword("Bank", "other"), email],
            bank,
        )
        self.assertEqual(conflicted[0].name, "Bank (restored)")
        self.assertEqual(conflicted[0].password, "secret-bank-value")
        with self.assertRaises(ValueError):
            password_app.remove_entry([email], bank)

    def test_entry_dates_label_shows_created_and_changed(self) -> None:
        bare = password_app.SavedPassword("Bare", "secret-bare-value")
        created_only = password_app.SavedPassword(
            "Created",
            "secret-created-value",
            created="2024-01-15T09:00:00Z",
        )
        both = password_app.SavedPassword(
            "Both",
            "secret-both-value",
            created="2024-01-15T09:00:00Z",
            modified="2024-03-20T18:30:00Z",
        )
        self.assertEqual(password_app.entry_dates_label(bare), "")
        self.assertEqual(password_app.entry_dates_label(created_only), "Created 2024-01-15")
        self.assertEqual(
            password_app.entry_dates_label(both),
            "Created 2024-01-15 · Changed 2024-03-20",
        )

    def test_sorted_saved_entries_and_touch_last_used(self) -> None:
        alpha = password_app.SavedPassword(
            "Alpha",
            "secret-alpha-value",
            favorite=True,
            modified="2024-01-02T00:00:00Z",
        )
        beta = password_app.SavedPassword(
            "Beta",
            "secret-beta-value",
            modified="2024-03-01T00:00:00Z",
            last_used="2024-02-01T00:00:00Z",
        )
        gamma = password_app.SavedPassword(
            "Gamma",
            "secret-gamma-value",
            modified="2024-01-01T00:00:00Z",
            last_used="2024-04-01T00:00:00Z",
        )
        items = [alpha, beta, gamma]
        by_name = password_app.sorted_saved_entries(items, password_app.SAVED_SORT_NAME)
        self.assertEqual([item.name for item in by_name], ["Alpha", "Beta", "Gamma"])
        by_recent = password_app.sorted_saved_entries(items, password_app.SAVED_SORT_RECENT)
        self.assertEqual([item.name for item in by_recent], ["Gamma", "Beta", "Alpha"])
        by_changed = password_app.sorted_saved_entries(items, password_app.SAVED_SORT_CHANGED)
        self.assertEqual([item.name for item in by_changed], ["Beta", "Alpha", "Gamma"])
        stamped = password_app.touch_last_used(items, alpha, when="2024-05-01T00:00:00Z")
        self.assertEqual(stamped[0].last_used, "2024-05-01T00:00:00Z")
        self.assertEqual(stamped[0].modified, alpha.modified)
        self.assertEqual(stamped[0].password, alpha.password)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.vault"
            material = password_app.new_vault_key("passphrase-here", password_app.new_recovery_key(), n=2**14)
            password_app.write_vault(material, stamped, path)
            _key, loaded = password_app.open_vault("passphrase-here", path)
            loaded_alpha = next(item for item in loaded if item.name == "Alpha")
            self.assertEqual(loaded_alpha.last_used, "2024-05-01T00:00:00Z")

    def test_password_history_restore_and_cap(self) -> None:
        item = password_app.SavedPassword("Site", "one")
        items = [item]
        for secret in ("two", "three", "four", "five", "six", "seven"):
            items = password_app.replace_entry_password(items, items[0], secret)
        self.assertEqual(items[0].password, "seven")
        self.assertEqual(len(items[0].history), password_app.MAX_PASSWORD_HISTORY)
        self.assertEqual([entry.password for entry in items[0].history], ["six", "five", "four", "three", "two"])
        restored = password_app.restore_entry_password(items, items[0], 1)
        self.assertEqual(restored[0].password, "five")
        self.assertEqual(restored[0].history[0].password, "seven")
        self.assertNotIn("five", [entry.password for entry in restored[0].history])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.vault"
            material = password_app.new_vault_key("passphrase-here", password_app.new_recovery_key(), n=2**14)
            password_app.write_vault(material, restored, path)
            _key, loaded = password_app.open_vault("passphrase-here", path)
            self.assertEqual(loaded[0].password, "five")
            self.assertEqual([entry.password for entry in loaded[0].history], [entry.password for entry in restored[0].history])
            self.assertEqual(loaded[0].history[0].replaced_at, restored[0].history[0].replaced_at)

    def test_parse_password_csv_and_merge_imported(self) -> None:
        text = (
            "name,username,password,url,notes,category\n"
            "Email,me@example.com,secret-one,https://mail.example,work mail,web\n"
            "Bank,,abc123,https://bank.example,,finance\n"
            '"Quoted, Name",user,"pass,word",https://q.example,,\n'
        )
        items = password_app.parse_password_csv(text)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].name, "Email")
        self.assertEqual(items[0].username, "me@example.com")
        self.assertEqual(items[0].password, "secret-one")
        self.assertEqual(items[0].url, "https://mail.example")
        self.assertEqual(items[0].notes, "work mail")
        self.assertEqual(items[0].category, "web")
        self.assertEqual(items[2].name, "Quoted, Name")
        self.assertEqual(items[2].password, "pass,word")
        local = [password_app.SavedPassword("Email", "different-secret")]
        merged, splits = password_app.merge_entries(local, items, conflict_suffix=" (imported)")
        self.assertEqual(splits, 1)
        names = {item.name for item in merged}
        self.assertIn("Email", names)
        self.assertIn("Email (imported)", names)
        self.assertIn("Bank", names)
        chrome = "name,url,username,password\nSite,https://site.example,u,p\n"
        chrome_items = password_app.parse_password_csv(chrome)
        self.assertEqual(chrome_items[0].name, "Site")
        with self.assertRaises(ValueError):
            password_app.parse_password_csv("title,login\nA,B\n")

    def test_format_password_csv_round_trips(self) -> None:
        items = [
            password_app.SavedPassword(
                "Email",
                "secret-one",
                username="me@example.com",
                url="https://mail.example",
                notes="work mail",
                category="web",
            ),
            password_app.SavedPassword(
                "Quoted, Name",
                "pass,word",
                username="user",
                url="https://q.example",
            ),
        ]
        text = password_app.format_password_csv(items)
        self.assertTrue(text.startswith("name,username,password,url,notes,category\n"))
        self.assertIn('"Quoted, Name"', text)
        self.assertIn('"pass,word"', text)
        back = password_app.parse_password_csv(text)
        self.assertEqual(len(back), 2)
        self.assertEqual(back[0].name, "Email")
        self.assertEqual(back[0].password, "secret-one")
        self.assertEqual(back[0].username, "me@example.com")
        self.assertEqual(back[1].name, "Quoted, Name")
        self.assertEqual(back[1].password, "pass,word")
        with self.assertRaises(ValueError):
            password_app.format_password_csv([])

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

    def test_archive_hides_from_active_health_and_recent(self) -> None:
        from datetime import date

        today = date(2024, 12, 1)
        recent = "2024-11-15T00:00:00Z"
        active = password_app.SavedPassword(
            "Email",
            "correct-horse-battery-staple-extra",
            modified=recent,
            last_used="2024-11-20T00:00:00Z",
        )
        archived = password_app.SavedPassword(
            "Old",
            "abc123",
            archived=True,
            modified="2020-01-01T00:00:00Z",
            last_used="2024-11-21T00:00:00Z",
        )
        items = [active, archived]
        self.assertEqual(
            [item.name for item in password_app.active_saved_entries(items)],
            ["Email"],
        )
        toggled = password_app.toggle_entry_archived(items, active)
        self.assertTrue(toggled[0].archived)
        restored = password_app.toggle_entry_archived(toggled, toggled[0])
        self.assertFalse(restored[0].archived)
        health = password_app.password_health_summary(items, today=today)
        self.assertEqual(health, (0, 0, 0, 0))
        recent_names = [item.name for item in password_app.recently_used_entries(items)]
        self.assertEqual(recent_names, ["Email"])
        sealed = password_app._entry_to_json(archived)
        self.assertTrue(sealed["archived"])
        round_trip = password_app._entry_from_json(sealed)
        self.assertTrue(round_trip.archived)

    def test_rename_entry_changes_name_and_refuses_clash(self) -> None:
        email = password_app.SavedPassword(
            "Email",
            "secret-value-here",
            username="me",
            notes="keep",
            favorite=True,
            created="2020-01-01T00:00:00Z",
            modified="2020-02-01T00:00:00Z",
            last_used="2020-03-01T00:00:00Z",
        )
        bank = password_app.SavedPassword("Bank", "other-secret-value")
        same = password_app.rename_entry([email, bank], email, "Email")
        self.assertEqual([item.name for item in same], ["Email", "Bank"])
        self.assertEqual(same[0].modified, "2020-02-01T00:00:00Z")
        updated = password_app.rename_entry(
            [email, bank],
            email,
            "  Work email  ",
            when="2024-05-01T00:00:00Z",
        )
        self.assertEqual([item.name for item in updated], ["Work email", "Bank"])
        self.assertEqual(updated[0].username, "me")
        self.assertEqual(updated[0].notes, "keep")
        self.assertTrue(updated[0].favorite)
        self.assertEqual(updated[0].created, "2020-01-01T00:00:00Z")
        self.assertEqual(updated[0].modified, "2024-05-01T00:00:00Z")
        self.assertEqual(updated[0].last_used, "2020-03-01T00:00:00Z")
        with self.assertRaises(ValueError) as raised:
            password_app.rename_entry([email, bank], email, "Bank")
        self.assertIn("already uses that name", str(raised.exception))
        with self.assertRaises(ValueError):
            password_app.rename_entry([bank], email, "Mailbox")

    def test_set_entry_category_sets_clears_and_refuses_missing(self) -> None:
        email = password_app.SavedPassword(
            "Email",
            "secret-value-here",
            username="me",
            category="Mail",
            favorite=True,
            created="2020-01-01T00:00:00Z",
            modified="2020-02-01T00:00:00Z",
            last_used="2020-03-01T00:00:00Z",
        )
        bank = password_app.SavedPassword("Bank", "other-secret-value")
        same = password_app.set_entry_category([email, bank], email, "Mail")
        self.assertEqual(same[0].category, "Mail")
        self.assertEqual(same[0].modified, "2020-02-01T00:00:00Z")
        updated = password_app.set_entry_category(
            [email, bank],
            email,
            "  Work  ",
            when="2024-05-01T00:00:00Z",
        )
        self.assertEqual(updated[0].category, "Work")
        self.assertEqual(updated[0].username, "me")
        self.assertTrue(updated[0].favorite)
        self.assertEqual(updated[0].created, "2020-01-01T00:00:00Z")
        self.assertEqual(updated[0].modified, "2024-05-01T00:00:00Z")
        self.assertEqual(updated[0].last_used, "2020-03-01T00:00:00Z")
        cleared = password_app.set_entry_category(
            updated,
            updated[0],
            "   ",
            when="2024-06-01T00:00:00Z",
        )
        self.assertEqual(cleared[0].category, "")
        self.assertEqual(cleared[0].modified, "2024-06-01T00:00:00Z")
        with self.assertRaises(ValueError):
            password_app.set_entry_category([bank], email, "Mail")
        with self.assertRaises(ValueError) as raised:
            password_app.set_entry_category([email], email, "x" * 41)
        self.assertIn("40 characters", str(raised.exception))

    def test_set_entry_username_sets_clears_and_refuses_missing(self) -> None:
        email = password_app.SavedPassword(
            "Email",
            "secret-value-here",
            username="me",
            category="Mail",
            favorite=True,
            created="2020-01-01T00:00:00Z",
            modified="2020-02-01T00:00:00Z",
            last_used="2020-03-01T00:00:00Z",
        )
        bank = password_app.SavedPassword("Bank", "other-secret-value")
        same = password_app.set_entry_username([email, bank], email, "me")
        self.assertEqual(same[0].username, "me")
        self.assertEqual(same[0].modified, "2020-02-01T00:00:00Z")
        updated = password_app.set_entry_username(
            [email, bank],
            email,
            "  me@example.com  ",
            when="2024-05-01T00:00:00Z",
        )
        self.assertEqual(updated[0].username, "me@example.com")
        self.assertEqual(updated[0].category, "Mail")
        self.assertTrue(updated[0].favorite)
        self.assertEqual(updated[0].created, "2020-01-01T00:00:00Z")
        self.assertEqual(updated[0].modified, "2024-05-01T00:00:00Z")
        self.assertEqual(updated[0].last_used, "2020-03-01T00:00:00Z")
        cleared = password_app.set_entry_username(
            updated,
            updated[0],
            "   ",
            when="2024-06-01T00:00:00Z",
        )
        self.assertEqual(cleared[0].username, "")
        self.assertEqual(cleared[0].modified, "2024-06-01T00:00:00Z")
        with self.assertRaises(ValueError):
            password_app.set_entry_username([bank], email, "other")
        with self.assertRaises(ValueError) as raised:
            password_app.set_entry_username([email], email, "x" * 201)
        self.assertIn("200 characters", str(raised.exception))

    def test_set_entry_url_and_notes_set_clear_and_refuse_missing(self) -> None:
        email = password_app.SavedPassword(
            "Email",
            "secret-value-here",
            url="https://mail.example",
            notes="work inbox",
            created="2020-01-01T00:00:00Z",
            modified="2020-02-01T00:00:00Z",
        )
        bank = password_app.SavedPassword("Bank", "other-secret-value")
        same = password_app.set_entry_url([email, bank], email, "https://mail.example")
        self.assertEqual(same[0].url, "https://mail.example")
        updated = password_app.set_entry_url(
            [email, bank],
            email,
            "  https://new.example  ",
            when="2024-05-01T00:00:00Z",
        )
        self.assertEqual(updated[0].url, "https://new.example")
        self.assertEqual(updated[0].modified, "2024-05-01T00:00:00Z")
        cleared = password_app.set_entry_url(
            updated, updated[0], "  ", when="2024-06-01T00:00:00Z"
        )
        self.assertEqual(cleared[0].url, "")
        noted = password_app.set_entry_notes(
            [email, bank],
            email,
            "  keep private  ",
            when="2024-07-01T00:00:00Z",
        )
        self.assertEqual(noted[0].notes, "keep private")
        cleared_notes = password_app.set_entry_notes(
            noted, noted[0], "\n", when="2024-08-01T00:00:00Z"
        )
        self.assertEqual(cleared_notes[0].notes, "")
        with self.assertRaises(ValueError):
            password_app.set_entry_url([bank], email, "https://x")
        self.assertEqual(
            list(password_app.DEFAULT_CATEGORIES),
            [
                "Personal",
                "Work",
                "Banking",
                "Social Media",
                "Shopping",
                "Entertainment",
                "Other",
            ],
        )
        self.assertIn(
            "Custom",
            password_app.category_choices(
                [password_app.SavedPassword("X", "secret", category="Custom")]
            ),
        )

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
                self.assertFalse(defaults.confirm_before_reveal)
                password_app.store_preferences(
                    password_app.Preferences(
                        clipboard_clear_seconds=15,
                        auto_lock_seconds=60,
                        confirm_before_reveal=True,
                    )
                )
                path = password_app.preferences_path()
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                loaded = password_app.load_preferences()
                self.assertEqual(loaded.clipboard_clear_seconds, 15)
                self.assertEqual(loaded.auto_lock_seconds, 60)
                self.assertTrue(loaded.confirm_before_reveal)
                path.write_text(
                    "clipboard_clear_seconds=999\nauto_lock_seconds=abc\nconfirm_before_reveal=yes\n",
                    encoding="utf-8",
                )
                repaired = password_app.load_preferences()
                self.assertEqual(repaired.clipboard_clear_seconds, 30)
                self.assertEqual(repaired.auto_lock_seconds, 300)
                self.assertTrue(repaired.confirm_before_reveal)
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
                self.assertEqual(window.theme_mode, password_app.THEME_LIGHT)
                self.assertFalse(window.window.get_style_context().has_class("dark"))
                window.on_toggle_dark()
                self.assertEqual(window.theme_mode, password_app.THEME_DARK)
                self.assertTrue(window.window.get_style_context().has_class("dark"))
                self.assertTrue(password_app.load_dark_mode())
                self.assertEqual(password_app.load_appearance_mode(), password_app.THEME_DARK)
                window.set_theme_mode(password_app.THEME_SYSTEM)
                self.assertEqual(password_app.load_appearance_mode(), password_app.THEME_SYSTEM)
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
