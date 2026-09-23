"""Tests for the local password generator GUI."""

from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request

import password_gui
import random_password_generator as generator


class GenerateResponseTests(unittest.TestCase):
    def test_default_password_is_shell_safe_and_strong(self) -> None:
        result = password_gui.generate_response({"mode": "characters", "length": 16, "count": 1})
        self.assertEqual(len(result["passwords"]), 1)
        self.assertEqual(len(result["passwords"][0]), 16)
        self.assertTrue(set(result["passwords"][0]).isdisjoint(generator.SHELL_SENSITIVE_CHARACTERS))
        self.assertTrue(result["strong"])
        self.assertGreaterEqual(result["bits"], generator.STRONG_ENTROPY_BITS)

    def test_short_password_is_weak(self) -> None:
        result = password_gui.generate_response(
            {
                "mode": "characters",
                "length": 8,
                "digits": True,
                "letters": True,
                "special": True,
                "allSpecial": False,
                "noAmbiguous": False,
            }
        )
        self.assertFalse(result["strong"])
        self.assertTrue(result["notes"])

    def test_ambiguous_characters_are_removed(self) -> None:
        result = password_gui.generate_response(
            {
                "mode": "characters",
                "length": 40,
                "digits": True,
                "letters": True,
                "special": True,
                "allSpecial": True,
                "noAmbiguous": True,
            }
        )
        self.assertTrue(set(result["passwords"][0]).isdisjoint(generator.AMBIGUOUS_CHARACTERS))

    def test_all_special_pool_includes_shell_characters(self) -> None:
        pool = password_gui.pool_from_options(digits=True, letters=True, special=True, all_special=True)
        self.assertIn("'", pool)
        self.assertIn("\\", pool)
        self.assertIn("`", pool)

    def test_rejects_empty_character_selection_and_bad_length(self) -> None:
        with self.assertRaises(ValueError):
            password_gui.generate_response(
                {
                    "mode": "characters",
                    "length": 12,
                    "digits": False,
                    "letters": False,
                    "special": False,
                    "allSpecial": False,
                }
            )
        with self.assertRaises(ValueError):
            password_gui.generate_response({"mode": "characters", "length": 0})

    def test_passphrase_has_six_words(self) -> None:
        result = password_gui.generate_response({"mode": "passphrase"})
        words = result["passwords"][0].split()
        self.assertEqual(len(words), 6)
        self.assertTrue(set(words) <= set(generator.load_wordlist()))
        self.assertTrue(result["strong"])

    def test_five_word_passphrase_is_weak(self) -> None:
        result = password_gui.generate_response({"mode": "passphrase", "words": 5, "count": 2})
        self.assertEqual(len(result["passwords"]), 2)
        self.assertTrue(all(len(password.split()) == 5 for password in result["passwords"]))
        self.assertFalse(result["strong"])


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = password_gui.ThreadingHTTPServer(("127.0.0.1", 0), password_gui.GeneratorHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def test_page_loads(self) -> None:
        with urllib.request.urlopen(self.url("/")) as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("Password Generator", body)
            self.assertIn("styles.css", body)

    def test_generate_endpoint(self) -> None:
        request = urllib.request.Request(
            self.url("/api/generate"),
            data=json.dumps({"mode": "characters", "length": 20, "count": 1}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            payload = json.load(response)
        self.assertEqual(len(payload["passwords"][0]), 20)
        self.assertTrue(payload["strong"])

    def test_bad_request_is_json(self) -> None:
        request = urllib.request.Request(
            self.url("/api/generate"),
            data=b"{",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code, 400)
        payload = json.load(caught.exception)
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
