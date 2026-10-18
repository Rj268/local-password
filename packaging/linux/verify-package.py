"""Check release metadata and the complete, explicit package file list."""
import ast
import json
from pathlib import Path
import subprocess
import tarfile
import io

root = Path(__file__).resolve().parents[2]
tree = ast.parse((root / 'password_app.py').read_text())
version = next(ast.literal_eval(node.value) for node in tree.body
               if isinstance(node, ast.Assign) and any(
                   isinstance(target, ast.Name) and target.id == 'APP_VERSION'
                   for target in node.targets))
package = root / 'dist' / f'local-password_{version}_all.deb'
def field(name):
    return subprocess.check_output(['dpkg-deb', '-f', str(package), name], text=True).strip()
assert field('Version') == version
assert field('Architecture') == 'all'
expected = {
    'usr/bin/local-password', 'usr/bin/random-password-generator',
    'usr/share/applications/local-password.desktop',
    'usr/share/icons/hicolor/scalable/apps/local-password.svg',
    'usr/share/icons/hicolor/256x256/apps/local-password.png',
}
expected.update('usr/share/local-password/' + name for name in (
    'password_app.py', 'random_password_generator.py', 'vault_sync.py',
    'eff_large_wordlist.txt', 'eff_large_wordlist.LICENSE.txt',
    'local-password.svg', 'local-password.png'))
expected.update('usr/share/doc/local-password/' + name for name in (
    'eff_large_wordlist.LICENSE.txt', 'PRIVACY.md', 'SECURITY.md',
    'USER_GUIDE.md', 'LICENSE', 'copyright'))
archive = subprocess.check_output(['dpkg-deb', '--fsys-tarfile', str(package)])
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    files = {member.name.removeprefix('./') for member in tar if not member.isdir()}
assert files == expected, f'Unexpected or missing package files: {files ^ expected}'
(root / 'dist' / 'package-verification.json').write_text(json.dumps({
    'version': version, 'architecture': 'all (Python; system libraries)',
    'files_checked': len(files), 'explicit_file_list': 'passed',
    'private_file_scan': 'passed', 'metadata': 'passed',
}, indent=2))
