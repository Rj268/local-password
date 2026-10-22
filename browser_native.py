"""One-shot native messaging bridge. Unlock and account approval stay on device."""
from __future__ import annotations

import json
from contextlib import redirect_stdout
import struct
import sys
from urllib.parse import urlsplit

MAX_MESSAGE = 16 * 1024


def https_origin(value: str) -> str:
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) <= 32 for c in value):
        raise ValueError('Invalid destination')
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('HTTPS is required')
    host = parsed.hostname.encode('idna').decode('ascii').lower()
    if ':' in host:
        host = '[' + host + ']'
    port = parsed.port
    return 'https://' + host + (f':{port}' if port is not None and port != 443 else '')


def matches(item, origin: str) -> bool:
    if item.archived or not item.url:
        return False
    try:
        return https_origin(item.url) == origin
    except (ValueError, UnicodeError):
        return False


def read_message(stream):
    header = stream.read(4)
    if len(header) != 4:
        raise ValueError('Missing message header')
    length = struct.unpack('=I', header)[0]
    if not 0 < length <= MAX_MESSAGE:
        raise ValueError('Invalid message size')
    payload = stream.read(length)
    if len(payload) != length:
        raise ValueError('Incomplete message')
    message = json.loads(payload)
    if not isinstance(message, dict) or set(message) != {'version', 'action', 'origin'}:
        raise ValueError('Invalid message')
    if type(message['version']) is not int or message['version'] != 1 or message['action'] != 'fill':
        raise ValueError('Unsupported request')
    origin = https_origin(message['origin'])
    if message['origin'] != origin:
        raise ValueError('Expected a canonical origin')
    return origin


def write_message(stream, message):
    payload = json.dumps(message, ensure_ascii=True).encode('utf-8')
    if len(payload) > 1024 * 1024:
        raise ValueError('Response too large')
    stream.write(struct.pack('=I', len(payload)))
    stream.write(payload)
    stream.flush()


def choose_login(origin):
    import concurrent.futures
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, GLib, Gdk
    import password_app as app

    app.set_windows_app_id()
    dialog = Gtk.Dialog(title='Local Password')
    for icon in app._icon_candidates():
        if icon.is_file() and icon.suffix == '.png':
            dialog.set_icon_from_file(str(icon))
            break
    provider = Gtk.CssProvider()
    provider.load_from_data(b"dialog { background: #f3f8f5; color: #183c32; font-family: Segoe UI, sans-serif; font-size: 15px; } entry { padding: 10px; border-radius: 8px; background: white; color: #183c32; } button { padding: 8px 16px; border-radius: 8px; } button.suggested-action { background: #08775b; color: white; } .request-title { font-size: 22px; font-weight: bold; }")
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    dialog.set_default_size(480, 320)
    dialog.set_resizable(False)
    dialog.set_border_width(18)
    dialog.add_button('Cancel', Gtk.ResponseType.CANCEL)
    unlock = dialog.add_button('Unlock vault', Gtk.ResponseType.OK)
    unlock.get_style_context().add_class('suggested-action')
    box = dialog.get_content_area()
    heading = Gtk.Label(label='Unlock to use a saved login')
    heading.get_style_context().add_class('request-title')
    heading.set_xalign(0)
    heading.set_line_wrap(True)
    box.pack_start(heading, False, False, 8)
    site = Gtk.Label(label=origin)
    site.set_xalign(0)
    site.set_line_wrap(True)
    site.set_max_width_chars(48)
    box.pack_start(site, False, False, 8)
    field_label = Gtk.Label(label='Vault passphrase or recovery key')
    field_label.set_xalign(0)
    box.pack_start(field_label, False, False, 4)
    secret = Gtk.Entry()
    secret.get_accessible().set_name('Vault passphrase or recovery key')
    secret.set_visibility(False)
    secret.set_placeholder_text('Vault passphrase or recovery key')
    secret.set_activates_default(True)
    dialog.set_default_response(Gtk.ResponseType.OK)
    box.pack_start(secret, False, False, 8)
    status = Gtk.Label(label='Unlock your vault, then choose an account for this site.')
    status.set_line_wrap(True)
    status.set_xalign(0)
    status.set_max_width_chars(48)
    box.pack_start(status, False, False, 8)
    dialog.show_all()
    if dialog.run() != Gtk.ResponseType.OK:
        dialog.destroy()
        return {'ok': False, 'error': 'cancelled'}
    passphrase = secret.get_text()
    secret.set_text('')
    secret.set_sensitive(False)
    unlock.set_sensitive(False)
    status.set_text('Unlocking your local vault…')
    # The expensive key derivation must not freeze the approval window.
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(app.open_vault, passphrase)
    del passphrase
    def ready():
        if not future.done():
            return True
        dialog.response(Gtk.ResponseType.APPLY)
        return False
    timer = GLib.timeout_add(100, ready)
    response = dialog.run()
    if response != Gtk.ResponseType.APPLY:
        GLib.source_remove(timer)
        dialog.destroy()
        executor.shutdown(wait=True)
        return {'ok': False, 'error': 'cancelled'}
    executor.shutdown(wait=True)
    def show_problem(text):
        status.set_text(text)
        secret.hide()
        field_label.hide()
        unlock.set_label('Close')
        unlock.set_sensitive(True)
        dialog.run()
        dialog.destroy()
    try:
        _, items = future.result()
    except Exception:
        show_problem('The vault could not be unlocked. Check your passphrase or recovery key, then try again from the browser.')
        return {'ok': False, 'error': 'unlock_failed'}
    candidates = [item for item in items if matches(item, origin)]
    if not candidates:
        show_problem('No saved login matches this exact site. Add its full HTTPS URL to the entry in your desktop vault.')
        return {'ok': False, 'error': 'no_matching_login'}
    secret.destroy()
    field_label.set_text('Saved account')
    heading.set_text('Choose a saved login')
    selector = Gtk.ComboBoxText()
    for item in candidates:
        selector.append_text(item.name + (' — ' + item.username if item.username else ''))
    selector.set_active(0)
    box.pack_start(selector, False, False, 10)
    status.set_text('Fill this login into the site shown above? The form will not be submitted.')
    unlock.set_label('Fill selected login')
    unlock.set_sensitive(True)
    dialog.show_all()
    response = dialog.run()
    index = selector.get_active()
    dialog.destroy()
    if response != Gtk.ResponseType.OK or index < 0:
        return {'ok': False, 'error': 'cancelled'}
    item = candidates[index]
    return {'ok': True, 'origin': origin, 'username': item.username, 'password': item.password}


def main():
    # Browser pipes must be binary on Windows. Never log secrets or raw requests.
    if sys.platform == 'win32':
        import msvcrt
        import os
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    output = sys.stdout.buffer
    try:
        origin = read_message(sys.stdin.buffer)
        with redirect_stdout(sys.stderr):
            response = choose_login(origin)
    except Exception:
        response = {'ok': False, 'error': 'request_failed'}
    write_message(output, response)


if __name__ == '__main__':
    main()
