# Local Password

Generate passwords and passphrases, manage logins in an encrypted local vault, and fill logins using Android Autofill. Desktop apps share a Create, Vault, and Settings flow across Windows, macOS, and Linux.

## Downloads

- **Desktop:** [GitHub Releases](https://github.com/Rj268/local-password/releases). Choose your operating system and read that release's notes.
- **Android:** [Local Password on Zapstore](https://zapstore.dev/apps/app.localpassword).

Source version: **1.31.10** (Android version code **13111**). The last verified GitHub desktop release is **1.31.8**; source updates and workflow artifacts do not automatically update published downloads. Zapstore lists Android **1.31.10**.

| Platform | Package and status |
| --- | --- |
| Windows | Extract the entire ZIP and run **Install Local Password**. Python and supporting libraries are bundled. |
| macOS | Separate macOS 15+ DMGs for Apple Silicon and Intel. Drag the app into Applications. Builds are not Developer ID signed or notarized. |
| Intel macOS 12+ | Experimental Monterey workflow; validation on a newer runner does not establish compatibility on a real Monterey Mac. |
| Linux | Debian package validated on Ubuntu 22.04 and 24.04. APT installs system dependencies. |
| Android | Android 8.0+ (API 26), with biometric unlock, passphrase fallback, and Autofill. |

On Linux, run `sudo apt install ./local-password_VERSION_all.deb` from the download folder, replacing `VERSION` with the downloaded version. Launch **Local Password** from the application menu or run `local-password`.

## Features

- Character passwords and word passphrases with configurable length and exclusions.
- Search, categories, favorites, and archived logins.
- Passphrase or recovery-key unlock, encrypted backups, and vault transfers between devices.
- Local password-health estimates and optional breach checks.
- Light, dark, and system appearance, auto-lock, and clipboard-clearing preferences.

Version 1.31.10 adds duplicate-name protection and explicit confirmation for password replacement. Check your installed package's version before relying on these changes.

## Browser integration

Chrome, Brave, and Firefox integration is a [development preview](extensions/README.md) with a separate local native host. It fills only a user-approved login for the exact HTTPS origin. Chrome has had manual fill/cancellation testing; Brave and Firefox still need verification. Safari integration is not implemented.

## Privacy and recovery

Saved passwords stay in a local encrypted vault. Keep an encrypted backup and the recovery key shown during setup. Losing both the passphrase and recovery key prevents unlocking the vault. CSV exports contain plaintext passwords.

Optional breach checks contact Have I Been Pwned using a short hash prefix. Clipboard clearing is best-effort. The project has not published an independent security audit. Read the [privacy policy](PRIVACY.md) and [security notes](SECURITY.md).

## Documentation and development

- [User guide](USER_GUIDE.md)
- [Release notes](RELEASE_NOTES.md)
- [Build and test instructions](docs/BUILDING.md)
- [Command-line generator](docs/COMMAND_LINE.md)
- [Contributing](CONTRIBUTING.md)
- [Release checklist](docs/RELEASING.md)
- [macOS packaging](packaging/macos/README.md)

## License and credits

Local Password uses the [MIT License](LICENSE). The unmodified EFF large wordlist was created by Joseph Bonneau and the Electronic Frontier Foundation and is used under [CC BY 3.0 US](eff_large_wordlist.LICENSE.txt). EFF does not endorse this project.
