"""Reject binaries too new for the advertised macOS minimum."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
import plistlib

path = Path(__file__).resolve().parents[1] / 'packaging/macos/verify_bundle.py'
spec = importlib.util.spec_from_file_location('macos_bundle_verifier', path)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class DeploymentTargetTests(unittest.TestCase):
    def test_build_version_uses_minos_not_newer_sdk(self):
        commands = 'cmd LC_BUILD_VERSION\ncmdsize 32\nplatform 1\nminos 11.0\nsdk 15.5\n'
        self.assertEqual(verifier.minimum_macos(commands), (11, 0, 0))

    def test_legacy_version_command(self):
        self.assertEqual(verifier.minimum_macos('cmd LC_VERSION_MIN_MACOSX\nversion 10.13\nsdk 14.0'), (10, 13, 0))

    def test_returns_highest_requirement(self):
        commands = 'cmd LC_BUILD_VERSION\nplatform MACOS\nminos 12.0\ncmd LC_BUILD_VERSION\nplatform MACOS\nminos 13.1'
        self.assertGreater(verifier.minimum_macos(commands), verifier.version_tuple('12.0'))

    def test_missing_or_nonmacos_target_is_rejected(self):
        for commands in ('cmd LC_UUID\nuuid ABC', 'cmd LC_BUILD_VERSION\nplatform IOS\nminos 12.0'):
            with self.assertRaises(RuntimeError):
                verifier.minimum_macos(commands)

    def test_version_comparison_is_numeric(self):
        self.assertLess(verifier.version_tuple('12.9'), verifier.version_tuple('12.10'))
        self.assertEqual(verifier.version_tuple('12'), verifier.version_tuple('12.0.0'))

    def check_bundle(self, target):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / 'Example.app'
            contents = bundle / 'Contents'
            contents.mkdir(parents=True)
            with (contents / 'Info.plist').open('wb') as file:
                plistlib.dump({'LSMinimumSystemVersion': '12.0', 'CFBundleShortVersionString': '1.31.8'}, file)
            (contents / 'example').write_bytes(bytes.fromhex('cffaedfe'))
            def command(args, **kwargs):
                if args[0].endswith('lipo'):
                    return 'x86_64'
                if '-l' in args:
                    return f'cmd LC_BUILD_VERSION\nplatform 1\nminos {target}\nsdk 15.5'
                return 'example:\n\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0)'
            with patch.object(verifier.subprocess, 'check_output', side_effect=command), \
                 patch.object(verifier.subprocess, 'run'):
                return verifier.verify_bundle(bundle, 'x86_64')

    def test_bundle_rejects_library_too_new_despite_plist_claim(self):
        with self.assertRaisesRegex(RuntimeError, 'above declared'):
            self.check_bundle('13.0')

    def test_bundle_accepts_compatible_library_built_using_newer_sdk(self):
        report = self.check_bundle('12.0')
        self.assertEqual(report['deployment_target_audit'], 'passed')
        self.assertEqual(report['highest_native_minimum_macos'], '12.0.0')
