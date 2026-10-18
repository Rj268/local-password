# Build natively on the target Mac architecture.
import ast
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

root = Path(SPECPATH).resolve().parents[1]
tree = ast.parse((root / 'password_app.py').read_text(encoding='utf-8'))
version = next(node.value.value for node in tree.body if isinstance(node, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == 'APP_VERSION' for t in node.targets))
datas = [(str(root / name), '.') for name in (
    'eff_large_wordlist.txt', 'eff_large_wordlist.LICENSE.txt',
    'LICENSE', 'PRIVACY.md', 'SECURITY.md', 'USER_GUIDE.md',
)]
datas += [(str(root / 'packaging/windows/local-password.png'), '.'),
          (str(root / 'packaging/macos/fonts.conf'), 'etc/fonts')]
for distribution in ('PyGObject', 'pycairo', 'cryptography', 'pyperclip'):
    datas += copy_metadata(distribution)
a = Analysis(
    [str(root / 'packaging/macos/launcher.py')],
    pathex=[str(root)], binaries=[], datas=datas,
    hiddenimports=['password_app', 'vault_sync', 'gi.repository.Gtk', 'gi.repository.Gdk',
                   'gi.repository.GLib', 'gi.repository.Gio', 'gi.repository.GdkPixbuf',
                   'gi.repository.Pango', 'gi.repository.PangoCairo', 'cairo'],
    hooksconfig={'gi': {'module-versions': {'Gtk': '3.0', 'Gdk': '3.0'},
                        'icons': ['Adwaita', 'hicolor'], 'themes': ['Adwaita'],
                        'languages': ['en']}},
    runtime_hooks=[str(root / 'packaging/macos/runtime.py')],
    excludes=['tkinter', 'pytest'], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='LocalPassword',
          console=False, debug=False, strip=False, upx=False,
          argv_emulation=False, codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='LocalPassword')
app = BUNDLE(coll, name='Local Password.app',
             icon=str(root / 'build/macos/LocalPassword.icns'),
             bundle_identifier='app.localpassword.desktop',
             info_plist={'CFBundleShortVersionString': version,
                         'CFBundleVersion': version,
                         'NSHighResolutionCapable': True,
                         'LSMinimumSystemVersion': '15.0',
                         'NSLocalNetworkUsageDescription':
                         'Send or receive your encrypted vault with another device on the same Wi-Fi.'})
