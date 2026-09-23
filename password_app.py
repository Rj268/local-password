#!/usr/bin/env python3
"""Local window for the password generator.

The password stays in this process. Copy is the only way it leaves.
Nothing is written to disk, and the app does not listen on a network port.
"""

from __future__ import annotations

import shutil
import string
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import random_password_generator as generator

METER_CAP_BITS = 128

STYLES = """
window.app {
  background-color: #ebe4d8;
  color: #1c1915;
  font-family: "DejaVu Sans", sans-serif;
}
.card {
  background-color: #f7f3ec;
  background-image: none;
  border: 1px solid #ddd4c6;
  border-radius: 18px;
}
.eyebrow {
  color: #0e6b52;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.5px;
}
.title {
  font-family: "DejaVu Serif", Palatino, serif;
  font-size: 32px;
  font-weight: 700;
}
.lede, .hint, .footer, .caption {
  color: #5f584e;
}
.strength.strong { color: #0e6b52; font-weight: 700; }
.strength.weak { color: #8a4b08; font-weight: 700; }
.bits { font-size: 15px; }
.slab {
  background-color: #171512;
  border-radius: 12px;
}
.slab text {
  color: #f6f1e7;
  background-color: #171512;
  font-family: "DejaVu Sans Mono", monospace;
  font-size: 16px;
}
button.mode, button.chip, button.primary, button.secondary {
  background-image: none;
  box-shadow: none;
  text-shadow: none;
  border-radius: 999px;
  border: 1px solid #d9d0c3;
  padding: 8px 14px;
  font-weight: 700;
}
button.mode.off, button.chip.off, button.secondary {
  background-color: #f3efe8;
  color: #6d655c;
  border-color: #d9d0c3;
}
button.mode.off label, button.chip.off label, button.secondary label {
  color: #6d655c;
}
button.mode.on, button.chip.on, button.primary {
  background-color: #0e6b52;
  color: #ffffff;
  border-color: #0e6b52;
}
button.mode.on label, button.chip.on label, button.primary label {
  color: #ffffff;
}
button.note-danger {
  color: #8d2c2c;
}
.danger { color: #8d2c2c; }
progressbar trough {
  min-height: 10px;
  background-color: #e4ddd2;
  border-radius: 999px;
  border: none;
}
progressbar progress {
  background-image: none;
  background-color: #0e6b52;
  border-radius: 999px;
  border: none;
}
progressbar.weak progress {
  background-color: #8a4b08;
}
"""


@dataclass(frozen=True)
class Generated:
    text: str
    label: str
    bits_label: str
    fraction: float
    note: str


def chip_label(name: str, active: bool) -> str:
    state = "On" if active else "Off"
    return f"{name}    {state}"


def _flag(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be true or false.")
    return value


def _count(count: object) -> int:
    if isinstance(count, bool) or not isinstance(count, int):
        raise ValueError("Count must be an integer.")
    if count < 1 or count > generator.MAX_PASSWORD_COUNT:
        raise ValueError(f"Count must be between 1 and {generator.MAX_PASSWORD_COUNT}.")
    return count


def character_pool(*, digits: bool, letters: bool, symbols: bool) -> str:
    """Build the alphabet. Symbols include quotes, backticks, and backslashes."""
    digits = _flag(digits, "Digits")
    letters = _flag(letters, "Letters")
    symbols = _flag(symbols, "Symbols")
    if not (digits or letters or symbols):
        raise ValueError("Choose at least one character type.")
    parts: list[str] = []
    if digits:
        parts.append(string.digits)
    if letters:
        parts.append(string.ascii_letters)
    if symbols:
        parts.append(generator.special_characters(all_special=True))
    return "".join(parts)


def generate(
    *,
    mode: str,
    length: int,
    words: int,
    count: int,
    digits: bool,
    letters: bool,
    symbols: bool,
) -> Generated:
    """Generate passwords in memory. This function does not write a file."""
    count = _count(count)
    if mode == "passphrase":
        word_count = generator.require_word_count(words)
        wordlist = generator.load_wordlist()
        passwords = [
            generator.generate_passphrase(word_count, wordlist=wordlist) for _ in range(count)
        ]
        exact = generator.passphrase_entropy_bits(word_count, len(wordlist))
        note = ""
        if exact < generator.STRONG_ENTROPY_BITS:
            note = (
                f"These options stay under {generator.STRONG_ENTROPY_BITS} bits. "
                "Add words to reach a strong passphrase."
            )
    elif mode == "characters":
        pool = character_pool(digits=digits, letters=letters, symbols=symbols)
        length = generator.require_password_length(length)
        passwords = [generator.generate_password(length, pool) for _ in range(count)]
        exact = generator.password_entropy_bits(length, len(generator.unique_characters(pool)))
        note = "" if generator.can_be_strong(length, pool) else generator.strong_line_message()
    else:
        raise ValueError("Mode must be characters or passphrase.")

    bits = round(exact)
    strong = exact >= generator.STRONG_ENTROPY_BITS
    each = "" if count == 1 else " each"
    return Generated(
        text="\n".join(passwords),
        label="Strong" if strong else "Weak",
        bits_label=f"about {bits} bits{each}",
        fraction=min(exact / METER_CAP_BITS, 1.0),
        note=note,
    )


def copy_with_xclip(text: str) -> bool:
    """Copy text by piping it to xclip. The password is not a command argument."""
    if shutil.which("xclip") is None:
        return False
    try:
        subprocess.run(
            ["xclip", "-selection", "clipboard", "-in"],
            input=text.encode("utf-8"),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def _icon_candidates() -> list[Path]:
    here = Path(__file__).resolve().parent
    return [
        here / "local-password.svg",
        here / "packaging" / "local-password.svg",
        Path("/usr/share/icons/hicolor/scalable/apps/local-password.svg"),
    ]


def install_styles(gtk, gdk) -> None:
    provider = gtk.CssProvider()
    provider.load_from_data(STYLES.encode("utf-8"))
    gtk.StyleContext.add_provider_for_screen(
        gdk.Screen.get_default(),
        provider,
        gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


def main() -> None:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, Gtk

    if Gdk.Display.get_default() is None:
        print(
            "Local Password needs a graphical session. There is no page to open.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    install_styles(Gtk, Gdk)

    window = PasswordWindow(Gtk, Gdk)
    window.window.connect("destroy", Gtk.main_quit)
    window.window.show_all()
    window.apply_mode()
    Gtk.main()


class PasswordWindow:
    """GTK window. Constructed with the Gtk and Gdk modules so import stays light."""

    def __init__(self, gtk, gdk) -> None:
        self.gtk = gtk
        self.gdk = gdk
        self.mode = "characters"
        self.current = ""

        self.window = gtk.Window(title="Local Password")
        self.window.set_default_size(960, 680)
        self.window.set_size_request(720, 560)
        self.window.get_style_context().add_class("app")
        for icon in _icon_candidates():
            if icon.is_file():
                try:
                    self.window.set_icon_from_file(str(icon))
                except Exception:
                    pass
                break

        root = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=16)
        root.set_margin_top(24)
        root.set_margin_bottom(20)
        root.set_margin_start(24)
        root.set_margin_end(24)
        self.window.add(root)

        eyebrow = gtk.Label(label="ON THIS COMPUTER", xalign=0)
        eyebrow.get_style_context().add_class("eyebrow")
        title = gtk.Label(label="Local Password", xalign=0)
        title.get_style_context().add_class("title")
        lede = gtk.Label(
            label=(
                "Generate it here, then copy it. The password stays in this window "
                "until you close it. Nothing is written to disk."
            ),
            xalign=0,
        )
        lede.set_line_wrap(True)
        lede.get_style_context().add_class("lede")
        root.pack_start(eyebrow, False, False, 0)
        root.pack_start(title, False, False, 0)
        root.pack_start(lede, False, False, 0)

        columns = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=16)
        columns.set_vexpand(True)
        root.pack_start(columns, True, True, 0)

        controls_frame, controls = self._card()
        columns.pack_start(controls_frame, True, True, 0)
        self._build_controls(controls)

        result_frame, result = self._card()
        columns.pack_start(result_frame, True, True, 0)
        self._build_result(result)

        footer = gtk.Label(
            label=(
                "Passphrases use the EFF large wordlist, created by Joseph Bonneau "
                "and the Electronic Frontier Foundation, under CC BY 3.0 US. "
                "The EFF does not endorse this project."
            ),
            xalign=0,
        )
        footer.set_line_wrap(True)
        footer.get_style_context().add_class("footer")
        root.pack_start(footer, False, False, 0)

    def _card(self):
        outer = self.gtk.Box(orientation=self.gtk.Orientation.VERTICAL)
        outer.get_style_context().add_class("card")
        outer.set_vexpand(True)
        inner = self.gtk.Box(orientation=self.gtk.Orientation.VERTICAL, spacing=12)
        for setter in (
            inner.set_margin_top,
            inner.set_margin_bottom,
            inner.set_margin_start,
            inner.set_margin_end,
        ):
            setter(16)
        outer.pack_start(inner, True, True, 0)
        return outer, inner

    def _build_controls(self, controls) -> None:
        gtk = self.gtk
        mode_row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        mode_row.set_homogeneous(True)
        self.mode_characters = gtk.Button(label="Characters")
        self.mode_words = gtk.Button(label="Words")
        for button in (self.mode_characters, self.mode_words):
            button.get_style_context().add_class("mode")
            mode_row.pack_start(button, True, True, 0)
        self.mode_characters.connect("clicked", lambda *_: self.set_mode("characters"))
        self.mode_words.connect("clicked", lambda *_: self.set_mode("passphrase"))
        controls.pack_start(mode_row, False, False, 0)

        self.character_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=12)
        controls.pack_start(self.character_box, False, False, 0)
        self.length = gtk.SpinButton.new_with_range(
            generator.MIN_PASSWORD_LENGTH, generator.MAX_PASSWORD_LENGTH, 1
        )
        self.length.set_value(16)
        self.length.set_numeric(True)
        self.character_box.pack_start(self._labeled("Length", self.length), False, False, 0)

        chips = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        chips.set_homogeneous(True)
        self.digits = self._chip("Digits", True)
        self.letters = self._chip("Letters", True)
        self.symbols = self._chip("Symbols", True)
        for chip in (self.digits, self.letters, self.symbols):
            chips.pack_start(chip, True, True, 0)
        self.character_box.pack_start(chips, False, False, 0)
        symbol_hint = gtk.Label(
            label="Symbols include quotes, backticks, and backslashes.",
            xalign=0,
        )
        symbol_hint.set_line_wrap(True)
        symbol_hint.get_style_context().add_class("hint")
        self.character_box.pack_start(symbol_hint, False, False, 0)

        self.word_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=8)
        self.word_box.set_no_show_all(True)
        controls.pack_start(self.word_box, False, False, 0)
        self.words = gtk.SpinButton.new_with_range(
            generator.MIN_WORD_COUNT, generator.MAX_WORD_COUNT, 1
        )
        self.words.set_value(generator.DEFAULT_WORD_COUNT)
        self.words.set_numeric(True)
        self.word_box.pack_start(self._labeled("Words", self.words), False, False, 0)
        word_hint = gtk.Label(
            label="Six words from the EFF list are about 78 bits. Five words fall short of the strong line.",
            xalign=0,
        )
        word_hint.set_line_wrap(True)
        word_hint.get_style_context().add_class("hint")
        self.word_box.pack_start(word_hint, False, False, 0)

        self.count = gtk.SpinButton.new_with_range(1, generator.MAX_PASSWORD_COUNT, 1)
        self.count.set_value(1)
        self.count.set_numeric(True)
        count_box = self._labeled("Number of passwords", self.count)
        count_hint = gtk.Label(label="Generate this many passwords at once.", xalign=0)
        count_hint.get_style_context().add_class("hint")
        count_box.pack_start(count_hint, False, False, 0)
        controls.pack_start(count_box, False, False, 0)

        self.generate_button = gtk.Button(label="Generate")
        self.generate_button.get_style_context().add_class("primary")
        self.generate_button.connect("clicked", self.on_generate)
        controls.pack_start(self.generate_button, False, False, 0)
        self._style_mode_buttons()

    def _build_result(self, result) -> None:
        gtk = self.gtk
        head = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=12)
        self.strength = gtk.Label(label="Result", xalign=0)
        self.strength.get_style_context().add_class("strength")
        self.strength.set_hexpand(True)
        self.bits = gtk.Label(label="Waiting to generate", xalign=1)
        self.bits.get_style_context().add_class("bits")
        head.pack_start(self.strength, True, True, 0)
        head.pack_start(self.bits, False, False, 0)
        result.pack_start(head, False, False, 0)

        self.meter = gtk.ProgressBar()
        self.meter.set_fraction(0)
        result.pack_start(self.meter, False, False, 0)
        caption = gtk.Label(
            label="The bar fills toward 128 bits. Strong starts at 75.",
            xalign=0,
        )
        caption.set_line_wrap(True)
        caption.get_style_context().add_class("caption")
        result.pack_start(caption, False, False, 0)

        self.note = gtk.Label(label="", xalign=0)
        self.note.set_line_wrap(True)
        self.note.get_style_context().add_class("danger")
        self.note.set_no_show_all(True)
        self.note.hide()
        result.pack_start(self.note, False, False, 0)

        self.buffer = gtk.TextBuffer()
        self.view = gtk.TextView.new_with_buffer(self.buffer)
        self.view.set_editable(False)
        self.view.set_cursor_visible(False)
        self.view.set_wrap_mode(gtk.WrapMode.WORD_CHAR)
        self.view.set_left_margin(14)
        self.view.set_right_margin(14)
        self.view.set_top_margin(14)
        self.view.set_bottom_margin(14)
        self.view.get_style_context().add_class("slab")
        self.view.connect("realize", lambda *_: self.view.drag_source_unset())
        scroller = gtk.ScrolledWindow()
        scroller.set_policy(gtk.PolicyType.NEVER, gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_height(160)
        scroller.set_vexpand(True)
        scroller.add(self.view)
        result.pack_start(scroller, True, True, 0)

        self.copy_button = gtk.Button(label="Copy")
        self.copy_button.get_style_context().add_class("primary")
        self.copy_button.set_sensitive(False)
        self.copy_button.connect("clicked", self.on_copy)
        result.pack_start(self.copy_button, False, False, 0)

        self.status = gtk.Label(
            label="Generate a password. It stays in this window.",
            xalign=0,
        )
        self.status.set_line_wrap(True)
        self.status.get_style_context().add_class("hint")
        result.pack_start(self.status, False, False, 0)

    def _labeled(self, caption: str, control):
        row = self.gtk.Box(orientation=self.gtk.Orientation.VERTICAL, spacing=4)
        line = self.gtk.Box(orientation=self.gtk.Orientation.HORIZONTAL, spacing=8)
        label = self.gtk.Label(label=caption, xalign=0)
        label.set_hexpand(True)
        line.pack_start(label, True, True, 0)
        line.pack_start(control, False, False, 0)
        row.pack_start(line, False, False, 0)
        return row

    def _chip(self, name: str, active: bool):
        button = self.gtk.ToggleButton(label=chip_label(name, active))
        button.set_active(active)
        button.get_style_context().add_class("chip")
        button.connect("toggled", lambda widget: self._paint_chip(widget, name))
        self._paint_chip(button, name)
        return button

    def _paint_chip(self, button, name: str) -> None:
        button.set_label(chip_label(name, button.get_active()))
        style = button.get_style_context()
        if button.get_active():
            style.add_class("on")
            style.remove_class("off")
        else:
            style.add_class("off")
            style.remove_class("on")

    def _style_mode_buttons(self) -> None:
        characters = self.mode == "characters"
        for button, selected in (
            (self.mode_characters, characters),
            (self.mode_words, not characters),
        ):
            style = button.get_style_context()
            if selected:
                style.add_class("on")
                style.remove_class("off")
            else:
                style.add_class("off")
                style.remove_class("on")

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.apply_mode()

    def apply_mode(self) -> None:
        words = self.mode == "passphrase"
        self.character_box.set_visible(not words)
        if words:
            self.word_box.set_no_show_all(False)
            self.word_box.show_all()
        else:
            self.word_box.hide()
        self._style_mode_buttons()

    def set_note(self, text: str) -> None:
        self.note.set_text(text)
        if text:
            self.note.show()
        else:
            self.note.hide()

    def on_generate(self, _button) -> None:
        try:
            result = generate(
                mode=self.mode,
                length=self.length.get_value_as_int(),
                words=self.words.get_value_as_int(),
                count=self.count.get_value_as_int(),
                digits=self.digits.get_active(),
                letters=self.letters.get_active(),
                symbols=self.symbols.get_active(),
            )
        except ValueError as exc:
            self.set_note(str(exc))
            return
        self.current = result.text
        self.buffer.set_text(result.text)
        self.strength.set_text(result.label)
        strength_style = self.strength.get_style_context()
        if result.label == "Strong":
            strength_style.add_class("strong")
            strength_style.remove_class("weak")
            self.meter.get_style_context().remove_class("weak")
        else:
            strength_style.add_class("weak")
            strength_style.remove_class("strong")
            self.meter.get_style_context().add_class("weak")
        self.bits.set_text(result.bits_label)
        self.meter.set_fraction(result.fraction)
        self.set_note(result.note)
        self.copy_button.set_sensitive(True)
        self.status.set_text("In this window only.")

    def on_copy(self, _button) -> None:
        if not self.current:
            return
        copied = False
        try:
            clipboard = self.gtk.Clipboard.get(self.gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(self.current, len(self.current))
            clipboard.store()
            copied = True
        except Exception:
            copied = False
        if copy_with_xclip(self.current):
            copied = True
        if copied:
            self.status.set_text("Copied.")
        else:
            self.status.set_text("Copy failed. The password is still only in this window.")


if __name__ == "__main__":
    main()
