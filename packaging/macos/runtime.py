"""Configure bundled GTK resources without writing into the signed app."""
import os
import sys
from pathlib import Path

if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
    resources = Path(sys._MEIPASS)
    os.environ['FONTCONFIG_FILE'] = str(resources / 'etc/fonts/fonts.conf')
    os.environ['GSETTINGS_BACKEND'] = 'memory'
    # PyInstaller's own GI/GdkPixbuf hooks relocate typelibs and loader caches.
