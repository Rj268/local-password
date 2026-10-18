"""Fail the build if the app depends on the builder's Homebrew installation."""
import argparse
import json
from pathlib import Path
import plistlib
import subprocess

MACHO_MAGIC = {bytes.fromhex(x) for x in ('feedface', 'cefaedfe', 'feedfacf', 'cffaedfe', 'cafebabe', 'bebafeca', 'cafebabf')}


def verify_bundle(bundle, architecture):
    bundle = bundle.resolve()
    with (bundle / 'Contents/Info.plist').open('rb') as handle:
        info = plistlib.load(handle)
    binary_count = 0
    for path in bundle.rglob('*'):
        if path.is_symlink():
            if not path.resolve().is_relative_to(bundle):
                raise RuntimeError(f'External bundle symlink: {path.relative_to(bundle)}')
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() in {'.vault', '.keystore', '.jks', '.p12', '.pfx', '.log'} or path.name in {'keystore.properties', 'local.properties', 'preferences', 'appearance'}:
            raise RuntimeError(f'Private or unnecessary file bundled: {path.relative_to(bundle)}')
        with path.open('rb') as handle:
            magic = handle.read(4)
        if magic not in MACHO_MAGIC:
            continue
        binary_count += 1
        slices = subprocess.check_output(['/usr/bin/lipo', '-archs', str(path)], text=True).split()
        if architecture not in slices:
            raise RuntimeError(f'Wrong architecture: {path.relative_to(bundle)}')
        libraries = subprocess.check_output(['/usr/bin/otool', '-L', str(path)], text=True)
        for line in libraries.splitlines()[1:]:
            dependency = line.strip().split(' (', 1)[0]
            if dependency.startswith('/') and not dependency.startswith(('/usr/lib/', '/System/Library/')):
                raise RuntimeError(f'Unbundled dependency in {path.relative_to(bundle)}: {dependency}')
    if not binary_count:
        raise RuntimeError('No native application binaries found')
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(bundle)], check=True)
    return {'version': info['CFBundleShortVersionString'], 'architecture': architecture,
            'minimum_macos': info['LSMinimumSystemVersion'], 'native_binaries_checked': binary_count,
            'bundle_signature_integrity': 'passed (ad-hoc, not notarized)',
            'external_build_machine_dependencies': 'none', 'private_file_scan': 'passed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle', type=Path)
    parser.add_argument('architecture', choices=['arm64', 'x86_64'])
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    report = verify_bundle(args.bundle, args.architecture)
    args.report.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
