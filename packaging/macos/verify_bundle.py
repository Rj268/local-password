"""Fail the build if the app depends on the builder's Homebrew installation."""
import argparse
import json
from pathlib import Path
import plistlib
import platform
import re
import subprocess

MACHO_MAGIC = {bytes.fromhex(x) for x in ('feedface', 'cefaedfe', 'feedfacf', 'cffaedfe', 'cafebabe', 'bebafeca', 'cafebabf')}


def version_tuple(value):
    if not re.fullmatch(r'\d+(?:\.\d+){0,2}', value):
        raise RuntimeError(f'Invalid macOS version: {value}')
    parts = tuple(map(int, value.split('.')))
    return parts + (0,) * (3 - len(parts))


def minimum_macos(load_commands):
    """Read deployment targets, never the SDK used to compile the binary."""
    command = None
    targets = []
    for line in load_commands.splitlines():
        fields = line.strip().split()
        if len(fields) == 2 and fields[0] == 'cmd':
            command = fields[1]
        if not fields:
            continue
        if command == 'LC_BUILD_VERSION' and fields[0] == 'platform':
            if fields[1] not in ('1', 'MACOS', 'macos'):
                raise RuntimeError('Non-macOS native binary in desktop bundle')
        if len(fields) == 2 and ((command == 'LC_BUILD_VERSION' and fields[0] == 'minos') or
                                (command == 'LC_VERSION_MIN_MACOSX' and fields[0] == 'version')):
            targets.append(version_tuple(fields[1]))
    if not targets:
        raise RuntimeError('Native binary has no macOS deployment target')
    return max(targets)


def verify_bundle(bundle, architecture):
    bundle = bundle.resolve()
    with (bundle / 'Contents/Info.plist').open('rb') as handle:
        info = plistlib.load(handle)
    binary_count = 0
    declared_minimum = version_tuple(info['LSMinimumSystemVersion'])
    highest_target = (0, 0, 0)
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
        commands = subprocess.check_output(['/usr/bin/otool', '-arch', architecture, '-l', str(path)], text=True)
        target = minimum_macos(commands)
        highest_target = max(highest_target, target)
        if target > declared_minimum:
            raise RuntimeError(f'{path.relative_to(bundle)} requires macOS {target}, above declared {declared_minimum}')
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
            'highest_native_minimum_macos': '.'.join(map(str, highest_target)),
            'deployment_target_audit': 'passed', 'runtime_test_macos': platform.mac_ver()[0],
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
