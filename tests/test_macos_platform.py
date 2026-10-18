"""Mac integration decisions can be checked without reading a real vault."""
import os
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
import tempfile
import unittest
from unittest.mock import patch

import password_app as app


class MacPlatformTests(unittest.TestCase):
    def test_new_mac_vault_uses_application_support(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True), patch.object(app.sys, 'platform', 'darwin'), patch.object(Path, 'home', return_value=Path(directory)):
            self.assertEqual(app.data_directory(), Path(directory) / 'Library/Application Support')

    def test_existing_source_vault_keeps_legacy_location(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True), patch.object(app.sys, 'platform', 'darwin'), patch.object(Path, 'home', return_value=Path(directory)):
            legacy = Path(directory) / '.local/share/local-password'
            legacy.mkdir(parents=True)
            (legacy / 'saved.vault').write_bytes(b'synthetic marker, not a real vault')
            self.assertEqual(app.data_directory(), legacy.parent)

    def test_explicit_data_directory_wins_on_mac(self):
        with patch.dict(os.environ, {'XDG_DATA_HOME': '/synthetic/fixture'}), patch.object(app.sys, 'platform', 'darwin'):
            self.assertEqual(app.data_directory(), Path('/synthetic/fixture'))

    def test_mac_dark_theme_uses_system_preference(self):
        with patch.object(app.sys, 'platform', 'darwin'), patch.object(app.subprocess, 'run', return_value=CompletedProcess([], 0, 'Dark\n', '')) as run:
            self.assertTrue(app.system_prefers_dark())
            run.assert_called_once_with(['/usr/bin/defaults', 'read', '-g', 'AppleInterfaceStyle'], check=False, capture_output=True, text=True, timeout=1)
        with patch.object(app.sys, 'platform', 'darwin'), patch.object(app.subprocess, 'run', return_value=CompletedProcess([], 1, '', 'not set')):
            self.assertFalse(app.system_prefers_dark())
        with patch.object(app.sys, 'platform', 'darwin'), patch.object(app.subprocess, 'run', side_effect=TimeoutExpired('defaults', 1)):
            self.assertFalse(app.system_prefers_dark())

    def test_mac_never_rewrites_the_signed_app_bundle(self):
        with patch.object(app.sys, 'platform', 'darwin'), patch.object(app.sys, 'frozen', True, create=True), patch.object(app, 'scrub_icon_themes') as scrub:
            app.repair_bundled_icons()
            scrub.assert_not_called()
