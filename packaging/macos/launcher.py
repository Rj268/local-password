"""Desktop entry point and isolated packaged-app smoke test."""
import json
import os
from pathlib import Path
import sys
import tempfile


def self_test(report_path):
    # Never read or change the owner's vault during build verification.
    with tempfile.TemporaryDirectory(prefix='local-password-check-') as directory:
        os.environ['XDG_DATA_HOME'] = directory
        import gi
        gi.require_version('Gtk', '3.0')
        gi.require_version('Gdk', '3.0')
        from gi.repository import Gtk, Gdk, GLib
        import password_app as app
        import random_password_generator as generator
        print('Checking GTK and font configuration', flush=True)
        app.install_styles(Gtk, Gdk)
        window = app.PasswordWindow(Gtk, Gdk)
        window.window.show_all()
        if not window.window.get_pango_context().list_families():
            raise RuntimeError('Bundled font configuration found no system fonts')
        window.show_section('create')
        if not window.create_view.get_visible():
            raise RuntimeError('Create page did not open')
        window.on_generate(None)
        if len(window.current) != 16 or window.result_revealed:
            raise RuntimeError('Password generation or default masking failed')
        window.count.set_value(3)
        window.on_generate(None)
        if len(window.batch) != 3 or not window.batch_scroll.get_visible():
            raise RuntimeError('Batch generation failed')
        window.set_mode('passphrase')
        window.count.set_value(1)
        window.on_generate(None)
        if len(window.current.split()) != generator.DEFAULT_WORD_COUNT:
            raise RuntimeError('Word generation failed')
        print('Generator checks passed; checking encrypted vault', flush=True)
        key = app.new_vault_key('synthetic test passphrase only')
        items = [app.SavedPassword(name='Example account', password='Synthetic-only-946!')]
        vault = Path(directory) / 'local-password' / 'test.vault'
        app.write_vault(key, items, vault)
        _, reopened = app.open_vault('synthetic test passphrase only', vault)
        if reopened[0].password != items[0].password:
            raise RuntimeError('Encrypted vault round trip failed')
        window.saved, window.vault_key, window.locked = reopened, key, False
        window.show_section('saved')
        if not window.saved_box.get_children():
            raise RuntimeError('Vault list did not render')
        window.show_section('settings')
        if not window.settings_view.get_visible():
            raise RuntimeError('Settings page did not open')
        print('Vault and navigation checks passed; checking event loop', flush=True)
        # Exercise fonts and paint a real window before ending the test.
        GLib.timeout_add(750, lambda: (Gtk.main_quit(), False)[1])
        Gtk.main()
        window.window.destroy()
        Path(report_path).write_text(json.dumps({
            'version': app.APP_VERSION, 'platform': sys.platform,
            'checks': ['GTK window and fonts', 'masked generation', 'batch generation',
                       'word generation', 'encrypted save and unlock', 'Vault', 'Settings'],
            'result': 'passed',
        }, indent=2))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        self_test(sys.argv[2])
    else:
        import password_app
        password_app.main()
