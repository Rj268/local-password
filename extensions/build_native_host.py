"""Build a separate console host; GUI-only desktop executables cannot use stdio."""
from pathlib import Path
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
if sys.platform == 'win32':
    os.environ['PATH'] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', '')
command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--console', '--onedir',
           '--name', 'LocalPasswordBrowser', '--distpath', str(root / 'dist/browser-host'),
           '--workpath', str(root / 'build/browser-host'), '--specpath', str(root / 'build/browser-host'),
           '--paths', str(root), '--hidden-import', 'password_app', '--hidden-import', 'vault_sync',
           '--hidden-import', 'gi.repository.Gtk', '--hidden-import', 'gi.repository.Gdk',
           '--hidden-import', 'gi.repository.GLib', '--hidden-import', 'cairo']
if sys.platform == 'win32':
    command.extend(['--icon', str(root / 'packaging/windows/local-password.ico')])
for name in ('local-password.png', 'eff_large_wordlist.txt', 'eff_large_wordlist.LICENSE.txt', 'LICENSE'):
    command.extend(['--add-data', f'{root / name}{";" if sys.platform == "win32" else ":"}.'])
command.append(str(root / 'browser_native.py'))
subprocess.run(command, cwd=root, check=True)
print('Keep the complete LocalPasswordBrowser folder together when installing the host.')
