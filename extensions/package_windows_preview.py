"""Package only built runtime files and the explicit browser extension assets."""
import hashlib
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
destination = root / 'dist/extensions/LocalPassword-browser-windows-preview.zip'
host = root / 'dist/browser-host/LocalPasswordBrowser'
if not (host / 'LocalPasswordBrowser.exe').is_file():
    raise RuntimeError('Build the native Windows host first')
extension_files = ['background.js', 'popup.html', 'popup.css', 'popup.js', 'manifest.json', 'icon.png']
with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(host.rglob('*')):
        if path.is_file():
            if path.suffix.lower() in ('.vault', '.keystore', '.pfx', '.p12'):
                raise RuntimeError('Unexpected private file in runtime')
            archive.write(path, 'LocalPasswordBrowser/' + path.relative_to(host).as_posix())
    for browser in ('chromium', 'firefox'):
        for name in extension_files:
            archive.write(root / 'dist/extensions' / browser / name, browser + '/' + name)
    archive.write(root / 'extensions/register-windows.ps1', 'register-windows.ps1')
    archive.write(root / 'extensions/WINDOWS-PREVIEW.md', 'START-HERE.md')
digest = hashlib.file_digest(destination.open('rb'), 'sha256').hexdigest()
(destination.parent / 'SHA256SUMS-browser-preview.txt').write_text(f'{digest}  {destination.name}\n')
print(destination)
print(digest)
