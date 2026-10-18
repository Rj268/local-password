"""Create development extension folders and ZIPs from an explicit file list."""
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent
for browser in ('chromium', 'firefox'):
    destination = ROOT.parent / 'dist' / 'extensions' / browser
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {
        'manifest_version': 3, 'name': 'Local Password', 'version': '0.1.1',
        'description': 'Choose a saved login from your local encrypted desktop vault.',
        'permissions': ['activeTab', 'scripting', 'nativeMessaging'],
        'action': {'default_popup': 'popup.html', 'default_title': 'Local Password'},
        'icons': {'128': 'icon.png'},
        'background': ({'service_worker': 'background.js'} if browser == 'chromium' else
                       {'scripts': ['background.js']}),
    }
    if browser == 'firefox':
        manifest['browser_specific_settings'] = {'gecko': {
            'id': 'browser@localpassword.app', 'strict_min_version': '128.0',
            'data_collection_permissions': {'required': ['none']},
        }}
    files = ['background.js', 'popup.html', 'popup.css', 'popup.js']
    for name in files:
        shutil.copyfile(ROOT / 'shared' / name, destination / name)
    shutil.copyfile(ROOT.parent / 'packaging/windows/local-password.png', destination / 'icon.png')
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    with zipfile.ZipFile(destination.parent / f'local-password-{browser}-development.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in files + ['manifest.json', 'icon.png']:
            archive.write(destination / name, name)
    print(destination)
