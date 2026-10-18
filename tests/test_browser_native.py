"""Protocol bounds, site isolation and selective credential release."""
import io
import os
import json
import struct
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from contextlib import nullcontext

import browser_native as bridge
from password_app import SavedPassword


class BrowserBridgeTests(unittest.TestCase):
    def request(self, **changes):
        message = {'version': 1, 'action': 'fill', 'origin': 'https://example.com'}
        message.update(changes)
        payload = json.dumps(message).encode()
        return io.BytesIO(struct.pack('=I', len(payload)) + payload)

    def test_https_origin_normalization_and_port(self):
        self.assertEqual(bridge.https_origin('https://EXAMPLE.com:443/login'), 'https://example.com')
        self.assertEqual(bridge.https_origin('https://example.com:8443/login'), 'https://example.com:8443')
        self.assertEqual(bridge.https_origin('https://example.com:0/login'), 'https://example.com:0')

    def test_rejects_insecure_and_confusing_urls(self):
        for value in ('http://example.com', 'https://user@example.com', 'https://example.com\n',
                      'file:///vault', 'javascript:alert(1)', 'https://example.com:bad'):
            with self.subTest(value=value), self.assertRaises((ValueError, UnicodeError)):
                bridge.https_origin(value)

    def test_only_exact_https_origin_matches(self):
        for url, expected in (
            ('https://example.com/login', True), ('https://example.com:443/', True),
            ('https://example.com.attacker.test', False), ('https://sub.example.com', False),
            ('https://example.com:8443', False), ('https://example.com:0', False),
            ('http://example.com', False), ('', False)):
            self.assertEqual(bridge.matches(SavedPassword('test', 'synthetic', url=url),
                                            'https://example.com'), expected)
        self.assertFalse(bridge.matches(SavedPassword('test', 'synthetic',
            url='https://example.com', archived=True), 'https://example.com'))

    def test_protocol_accepts_only_minimal_canonical_fill_request(self):
        self.assertEqual(bridge.read_message(self.request()), 'https://example.com')
        for changes in ({'action': 'export'}, {'version': True}, {'origin': 'https://example.com/login'},
                        {'password': 'never-accept'}, {'origin': 'http://example.com'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                bridge.read_message(self.request(**changes))

    def test_rejects_oversize_truncated_and_nonobject_messages(self):
        for data in (b'', b'abc', struct.pack('=I', bridge.MAX_MESSAGE + 1),
                     struct.pack('=I', 10) + b'{}', struct.pack('=I', 2) + b'[]'):
            with self.assertRaises(ValueError):
                bridge.read_message(io.BytesIO(data))

    def test_unicode_response_has_byte_length_header(self):
        stream = io.BytesIO()
        bridge.write_message(stream, {'username': 'synthetic-\u00e9', 'password': 'synthetic'})
        value = stream.getvalue()
        self.assertEqual(struct.unpack('=I', value[:4])[0], len(value) - 4)
        self.assertEqual(json.loads(value[4:])['username'], 'synthetic-\u00e9')

    def host_response(self, chooser):
        output = io.BytesIO()
        with patch.object(bridge.sys, 'platform', 'linux'), \
             patch.object(bridge.sys, 'stdin', SimpleNamespace(buffer=self.request())), \
             patch.object(bridge.sys, 'stdout', SimpleNamespace(buffer=output)), \
             patch.object(bridge, 'choose_login', chooser):
            bridge.main()
        return json.loads(output.getvalue()[4:])

    def test_cancelled_approval_releases_no_credentials(self):
        result = self.host_response(lambda origin: {'ok': False, 'error': 'cancelled'})
        self.assertEqual(result, {'ok': False, 'error': 'cancelled'})

    def test_internal_exception_details_are_not_returned_to_browser(self):
        def fail(origin):
            raise RuntimeError('synthetic-private-secret')
        self.assertEqual(self.host_response(fail), {'ok': False, 'error': 'request_failed'})


@unittest.skipUnless(os.environ.get('DISPLAY'), 'needs a graphical session')
class ApprovalWindowTests(unittest.TestCase):
    def approve(self, *, cancelled=False, archived=False):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        original_run = Gtk.Dialog.run
        calls = []
        item = SavedPassword('Synthetic account', 'synthetic-password',
                             username='synthetic-user', url='https://example.com/login', archived=archived)
        def scripted_run(dialog):
            calls.append(True)
            if len(calls) == 1:
                for child in dialog.get_content_area().get_children():
                    if isinstance(child, Gtk.Entry):
                        child.set_text('synthetic passphrase only')
                return Gtk.ResponseType.OK
            if len(calls) == 2:
                return original_run(dialog)  # Exercise the real worker/completion event loop.
            return Gtk.ResponseType.CANCEL if cancelled else Gtk.ResponseType.OK
        # GTK's Python signal wakeup creates a TCP socketpair on Windows. The
        # sandbox forbids that loopback connection; it is unrelated to UI behavior.
        with patch('gi._ossighelper.wakeup_on_signal', lambda: nullcontext()), \
             patch('password_app.open_vault', return_value=(object(), [item])) as unlock, \
             patch.object(Gtk.Dialog, 'run', scripted_run):
            result = bridge.choose_login('https://example.com')
            unlock.assert_called_once_with('synthetic passphrase only')
            return result, len(calls)

    def test_native_window_releases_only_an_approved_match(self):
        result, count = self.approve()
        self.assertEqual(count, 3)
        self.assertEqual(result, {'ok': True, 'origin': 'https://example.com',
                                 'username': 'synthetic-user', 'password': 'synthetic-password'})

    def test_cancel_after_unlock_releases_no_login(self):
        result, count = self.approve(cancelled=True)
        self.assertEqual(result, {'ok': False, 'error': 'cancelled'})

    def test_archived_login_is_not_offered(self):
        result, count = self.approve(archived=True)
        self.assertEqual(count, 3)
        self.assertEqual(result, {'ok': False, 'error': 'no_matching_login'})


if __name__ == '__main__':
    unittest.main()
