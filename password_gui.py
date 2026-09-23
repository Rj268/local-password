#!/usr/bin/env python3
"""Local web interface for the password generator.

The page asks this process to generate passwords. Nothing is written to disk
and nothing is sent off the machine.
"""

from __future__ import annotations

import argparse
import json
import string
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import random_password_generator as generator

GUI_DIR = Path(__file__).resolve().parent / "gui"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8741
MAX_BODY_BYTES = 8192

STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/styles.css": "styles.css",
    "/app.js": "app.js",
}
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
}


def _require_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be true or false.")
    return value


def pool_from_options(
    *,
    digits: bool,
    letters: bool,
    special: bool,
    all_special: bool,
) -> str:
    """Build a character pool from explicit GUI choices.

    Unchecking every character type is an error. The command-line tool treats
    a missing flag as 'use the default alphabet'; the checkboxes are explicit.
    """
    if not (digits or letters or special or all_special):
        raise ValueError("Choose at least one character type.")
    parts: list[str] = []
    if digits:
        parts.append(string.digits)
    if letters:
        parts.append(string.ascii_letters)
    if special or all_special:
        parts.append(generator.special_characters(all_special=all_special))
    return "".join(parts)


def generate_response(options: dict) -> dict:
    """Generate passwords from a JSON object and describe their strength."""
    mode = options.get("mode", "characters")
    if mode not in {"characters", "passphrase"}:
        raise ValueError("Mode must be characters or passphrase.")
    count_value = options.get("count", 1)
    if isinstance(count_value, bool) or not isinstance(count_value, int):
        raise ValueError("Count must be an integer.")
    if count_value < 1 or count_value > generator.MAX_PASSWORD_COUNT:
        raise ValueError(
            f"Count must be between 1 and {generator.MAX_PASSWORD_COUNT}."
        )

    notes: list[str] = []
    if mode == "passphrase":
        word_count = generator.require_word_count(options.get("words", generator.DEFAULT_WORD_COUNT))
        wordlist = generator.load_wordlist()
        passwords = [
            generator.generate_passphrase(word_count, wordlist=wordlist) for _ in range(count_value)
        ]
        bits = generator.passphrase_entropy_bits(word_count, len(wordlist))
        report = generator.describe_passwords(passwords, entropy_bits=bits)
    else:
        length = generator.require_password_length(options.get("length", 16))
        digits = _require_bool(options.get("digits", True), "Digits")
        letters = _require_bool(options.get("letters", True), "Letters")
        special = _require_bool(options.get("special", True), "Symbols")
        all_special = _require_bool(options.get("allSpecial", False), "Shell symbols")
        no_ambiguous = _require_bool(options.get("noAmbiguous", False), "Ambiguous characters")
        character_list = generator.prepare_character_list(
            pool_from_options(
                digits=digits,
                letters=letters,
                special=special,
                all_special=all_special,
            ),
            exclude_ambiguous=no_ambiguous,
        )
        passwords = [
            generator.generate_password(length, character_list) for _ in range(count_value)
        ]
        bits = generator.password_entropy_bits(length, len(character_list))
        report = generator.describe_passwords(passwords, len(character_list))
        if not generator.can_be_strong(length, character_list):
            notes.append(generator.strong_line_message())
        if no_ambiguous:
            notes.append(f"Ambiguous characters left out: {generator.AMBIGUOUS_CHARACTERS}.")

    return {
        "passwords": passwords,
        "report": report,
        "bits": round(bits),
        "strong": bits >= generator.STRONG_ENTROPY_BITS,
        "notes": notes,
    }


def config_response() -> dict:
    return {
        "minLength": generator.MIN_PASSWORD_LENGTH,
        "maxLength": generator.MAX_PASSWORD_LENGTH,
        "minWords": generator.MIN_WORD_COUNT,
        "maxWords": generator.MAX_WORD_COUNT,
        "defaultWords": generator.DEFAULT_WORD_COUNT,
        "minCount": 1,
        "maxCount": generator.MAX_PASSWORD_COUNT,
        "strongBits": generator.STRONG_ENTROPY_BITS,
        "ambiguousCharacters": generator.AMBIGUOUS_CHARACTERS,
    }


class GeneratorHandler(BaseHTTPRequestHandler):
    server_version = "PasswordGeneratorGUI"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/config":
            self._send_json(200, config_response())
            return
        filename = STATIC_FILES.get(path)
        if filename is None:
            self._send_json(404, {"error": "Not found."})
            return
        file_path = GUI_DIR / filename
        if not file_path.is_file():
            self._send_json(404, {"error": "Not found."})
            return
        content_type = CONTENT_TYPES.get(file_path.suffix, "application/octet-stream")
        body = file_path.read_bytes()
        self._send_bytes(200, body, content_type)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/generate":
            self._send_json(404, {"error": "Not found."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "Request body must be JSON."})
            return
        if length < 0 or length > MAX_BODY_BYTES:
            self._send_json(413, {"error": "Request is too large."})
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "Request body must be JSON."})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "Request body must be a JSON object."})
            return
        try:
            result = generate_response(payload)
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(200, result)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        message = format % args
        if "/api/generate" in message:
            return
        super().log_message("%s", message)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Open the password generator in a browser.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Address to bind (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to listen on (default {DEFAULT_PORT})")
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), GeneratorHandler)
    display_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    print(f"Password Generator GUI: http://{display_host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
