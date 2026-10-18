"""Exercise installed Linux files with the shared desktop smoke checks."""
from pathlib import Path
import runpy
import sys

import password_app

if Path(password_app.__file__).resolve() != Path('/usr/share/local-password/password_app.py'):
    raise RuntimeError('Smoke test must exercise the installed package')
checks = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'macos' / 'launcher.py'))
checks['self_test'](sys.argv[1])
