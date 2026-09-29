"""The encrypted vault can move to another device without the passphrase."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import password_app
import vault_sync


class VaultSyncTests(unittest.TestCase):
    def test_pairing_code_pulls_the_vault(self) -> None:
        payload = b"LPV2" + b"\x00" * 60
        offer = vault_sync.VaultOffer(payload, "123456")
        offer.start()
        try:
            self.assertEqual(offer.error, "")
            received = vault_sync.receive_vault("12 34 56", f"127.0.0.1:{offer.port}", timeout=5)
            self.assertEqual(received, payload)
            self.assertTrue(offer.sent)
        finally:
            offer.stop()

    def test_wrong_code_is_refused(self) -> None:
        payload = b"LPV2" + b"\x00" * 60
        offer = vault_sync.VaultOffer(payload, "123456")
        offer.start()
        try:
            with self.assertRaisesRegex(ValueError, "refused"):
                vault_sync.receive_vault("000000", f"127.0.0.1:{offer.port}", timeout=5)
            self.assertFalse(offer.sent)
        finally:
            offer.stop()

    def test_same_vault_decrypts_and_a_different_one_does_not(self) -> None:
        recovery = "one two three four five six seven eight"
        material = password_app.new_vault_key("a-long-secret", recovery, n=2**14)
        items = [password_app.SavedPassword("Email", "alpha")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.vault"
            password_app.write_vault(material, items, path)
            opened, _loaded = password_app.open_vault("a-long-secret", path)
            extra = items + [password_app.SavedPassword("Router", "beta")]
            password_app.write_vault(opened, extra, path)
            again = password_app.items_from_same_vault(path.read_bytes(), opened)
            self.assertEqual(
                [(item.name, item.password) for item in again],
                [("Email", "alpha"), ("Router", "beta")],
            )
            other = password_app.new_vault_key(
                "different-secret",
                "eight seven six five four three two one",
                n=2**14,
            )
            other_path = Path(directory) / "other.vault"
            password_app.write_vault(other, items, other_path)
            self.assertIsNone(password_app.items_from_same_vault(other_path.read_bytes(), opened))

    def test_a_different_password_for_the_same_name_is_kept(self) -> None:
        local = [
            password_app.SavedPassword("Email", "alpha"),
            password_app.SavedPassword("Bank", "one"),
        ]
        incoming = [
            password_app.SavedPassword("Email", "alpha"),
            password_app.SavedPassword("Bank", "two"),
            password_app.SavedPassword("Mail", "three"),
        ]
        merged, splits = password_app.merge_saved(local, incoming)
        self.assertEqual(splits, 1)
        self.assertEqual(
            [item.name for item in merged],
            ["Email", "Bank", "Bank (other device)", "Mail"],
        )
        self.assertEqual(merged[2].password, "two")

    def test_matching_passwords_fill_empty_optional_fields(self) -> None:
        local = [password_app.SavedPassword("Email", "alpha", username="me")]
        incoming = [
            password_app.SavedPassword(
                "Email",
                "alpha",
                url="https://mail.example",
                favorite=True,
                extras={"custom": "keep"},
            )
        ]
        merged, splits = password_app.merge_saved(local, incoming)
        self.assertEqual(splits, 0)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].username, "me")
        self.assertEqual(merged[0].url, "https://mail.example")
        self.assertTrue(merged[0].favorite)
        self.assertEqual(merged[0].extras["custom"], "keep")
