# Privacy policy for Local Password

Local Password is a local password manager. This policy describes what the free core does with your data.

## Short version

- Your vault and passphrase stay on your device.
- There is no account, analytics, advertising, or crash telemetry in the free core.
- The only optional network use is a breach check you start yourself.

## What stays on this device

- Saved passwords live in an encrypted vault file on this computer (or phone).
- Preferences such as theme, clipboard clear, auto-lock, and lock-on-open stay on this device and hold no passwords.
- Export vault, Import vault, Send vault, and Receive vault move the encrypted vault file. The passphrase is not inside those transfers.

## What can leave this device

- **Nothing by default.** Opening, generating, saving, locking, and exporting do not contact a Local Password server. There is no Local Password cloud account.
- **Optional breach checks.** If you choose **Check breaches** (or **Check breach** on one row), the app contacts Have I Been Pwned’s Pwned Passwords service using k-anonymity: only the first five characters of a SHA-1 password hash are sent. The password, full hash, vault file, and passphrase are never sent. You can stay offline; the vault still works.
- **LAN transfer.** Send vault / Receive vault talk to another device you choose on the same Wi-Fi. That is peer-to-peer for the encrypted file, not an upload to Local Password.

## What we do not collect

The free core does not collect names, emails, vault contents, usage analytics, advertising identifiers, or crash reports.

## Third parties

- **Have I Been Pwned** — only if you run a breach check. See [haveibeenpwned.com](https://haveibeenpwned.com/).
- Your operating system and other apps may keep clipboard contents after a copy. Clipboard clear in Local Password is best-effort.

## Contact

For privacy or security concerns, contact the project maintainer privately when practical. Do not include real vault passphrases, recovery keys, or decrypted password lists in reports.

## Changes

If this policy changes, the updated text ships with the app and in `PRIVACY.md` in the project.
