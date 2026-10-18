# Local Password for macOS

This Mac build uses the same desktop code and Create / Vault / Settings layout as Windows 1.31.8.

## Install

The published `macos15` DMGs require macOS 15 or later. Choose `arm64` for Apple Silicon (M-series), or `x86_64` for Intel. A separate experimental `macos12-x86_64` build targets Intel Macs running macOS 12 Monterey or newer; it must pass the binary audit and still needs testing on an actual Monterey Mac. Open the DMG and drag **Local Password.app** to **Applications**, then eject the disk image and open the app from Applications.

These initial Mac builds have an ad-hoc integrity signature. They are **not Developer ID signed or notarized**, so macOS may block normal opening. They need testing on a real Mac before public distribution. The build does not remove quarantine attributes or disable macOS security settings.

## Vault and settings

New Mac installations store the encrypted vault in `~/Library/Application Support/local-password/saved.vault`. Existing source installations using `~/.local/share/local-password/saved.vault` keep that location. The `XDG_DATA_HOME` override is also respected.

Use Settings to import or export an encrypted vault. Windows and Android vault files use the same format. Keep a backup and your recovery key. Never include a personal vault in the application bundle.

## Build

Build each architecture on a Mac of that architecture. GitHub Actions uses separate macOS 15 Apple Silicon and Intel runners. No signing credentials or personal vault files are needed.

Install Homebrew's `python@3.14`, `gtk+3`, `gobject-introspection`, `cairo`, `pkgconf`, `adwaita-icon-theme`, and `librsvg`. Create a Python 3.14 virtual environment, install `packaging/macos/build-requirements.txt`, and run `bash packaging/macos/build.sh` with that environment active.

The workflow tests the shared desktop code, creates an `.app`, checks native-library architecture and portability, verifies bundle integrity, creates and mounts the DMG read-only, and runs a synthetic save/unlock and UI smoke test from the mounted application. Build artifacts include the DMG, checksum, and verification reports. It does not publish a GitHub release automatically.

### Intel Monterey candidate

The separate **Build Intel Mac Monterey DMG** workflow uses conda-forge's native
Quartz GTK runtime with Python 3.12. The solver sees `CONDA_OVERRIDE_OSX=12.0`,
and the app sets `MACOSX_DEPLOYMENT_TARGET=12.0`. This avoids using the macOS 15
Homebrew runtime for the older target. Merely changing Info.plist is insufficient.

`verify_bundle.py` reads each Intel Mach-O binary's load commands and rejects
deployment targets above the minimum declared by the application. It checks
the minimum OS, not the SDK version used to compile the file. The report records
both the declared minimum and the actual macOS version used for the smoke test.
GitHub's runner is macOS 15, so that runtime test does not certify macOS 12.
The candidate includes the desktop application; Safari integration remains
separate and is not added by changing the deployment target.

Conda package versions/URLs are included in `conda-packages.txt` with the build
artifacts. The existing Apple Silicon release is unaffected. This workflow does
not publish or replace existing release assets.

The app bundles Python, GTK, PyGObject, cryptography, and supporting libraries. Source and license information is available from [Python](https://www.python.org/), [GTK](https://www.gtk.org/), [PyGObject](https://pygobject.gnome.org/), [cryptography](https://cryptography.io/), and the Homebrew formulae used for the build. The application and EFF wordlist licenses are included in the bundle.
