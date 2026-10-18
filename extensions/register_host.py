"""Explicit per-user native host registration; never reads a vault or secret."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

NAME = 'app.localpassword.browser'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', choices=('chrome', 'brave', 'firefox'), required=True)
    parser.add_argument('--extension-id', required=True)
    parser.add_argument('--host', type=Path, required=True, help='Absolute path to the built native host executable')
    parser.add_argument('--remove', action='store_true')
    args = parser.parse_args()
    if args.browser == 'firefox':
        if args.extension_id != 'browser@localpassword.app':
            parser.error('Use the Firefox ID browser@localpassword.app')
    elif not re.fullmatch('[a-p]{32}', args.extension_id):
        parser.error('Use the 32-letter extension ID shown by your browser')
    host = args.host.resolve(strict=True)
    if not host.is_file() or (sys.platform == 'win32' and host.suffix.lower() != '.exe'):
        parser.error('The host must be a native executable (.exe on Windows)')
    if sys.platform != 'win32' and not os.access(host, os.X_OK):
        parser.error('The host is not executable')
    manifest = {'name': NAME, 'description': 'Local Password local vault bridge',
                'path': str(host), 'type': 'stdio'}
    key = 'allowed_extensions' if args.browser == 'firefox' else 'allowed_origins'
    manifest[key] = [args.extension_id if args.browser == 'firefox' else f'chrome-extension://{args.extension_id}/']
    home = Path.home()
    if sys.platform == 'win32':
        import winreg
        vendors = {'chrome': r'Google\Chrome', 'brave': r'BraveSoftware\Brave-Browser', 'firefox': r'Mozilla'}
        folder = Path(os.environ['LOCALAPPDATA']) / 'LocalPasswordBrowser' / args.browser
        registry = 'Software\\' + vendors[args.browser] + '\\NativeMessagingHosts\\' + NAME
    elif sys.platform == 'darwin':
        folders = {'chrome': 'Google/Chrome', 'brave': 'BraveSoftware/Brave-Browser', 'firefox': 'Mozilla'}
        folder = home / 'Library/Application Support' / folders[args.browser] / 'NativeMessagingHosts'
    else:
        folder = (home / '.mozilla/native-messaging-hosts' if args.browser == 'firefox' else
                  Path(os.environ.get('XDG_CONFIG_HOME', home / '.config')) /
                  {'chrome': 'google-chrome', 'brave': 'BraveSoftware/Brave-Browser'}[args.browser] / 'NativeMessagingHosts')
    path = folder / (NAME + '.json')
    if args.remove:
        if sys.platform == 'win32':
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, registry)
            except FileNotFoundError:
                pass
        path.unlink(missing_ok=True)
        print('Removed browser bridge registration:', path)
        return
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    if sys.platform == 'win32':
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, registry) as registry_key:
            winreg.SetValueEx(registry_key, '', 0, winreg.REG_SZ, str(path))
    print('Registered browser bridge:', path)


if __name__ == '__main__':
    main()
