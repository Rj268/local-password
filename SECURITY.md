# Security notes for Local Password

Local Password encrypts saved passwords on this computer. It is not a guarantee of absolute security. Treat this document as an honest summary of what the app does and does not do before a public release.

## What is protected

- The vault file (`saved.vault`) uses authenticated encryption (AES-GCM).
- Passphrases and recovery keys are run through scrypt before they can unlock the vault.
- LPV2 vaults can open with either the passphrase or a one-time recovery key. Neither is stored in plaintext.
- Export vault writes the encrypted file. The passphrase is not inside that export.
- Password health checks (weak, reused, stale) run only against entries already in the local vault. Nothing is sent to a breach service.

## What is not guaranteed

- Clipboard clearing is best-effort. Other apps or the operating system may keep a copy after Local Password clears its own clipboard contents.
- Send vault / Receive vault move an encrypted file on the local network with a short pairing code. Being on the same Wi-Fi does not by itself make the transfer private from every other device on that network.
- Auto-lock hides decrypted entries after idle time in this app session. It does not erase residual memory the operating system may still hold.
- Lock on open is optional and off by default. When on, the app prompts for the passphrase at startup if a vault already exists.
- Strength labels estimate search-space size from length and alphabet (or word count). They are not a proof that a password is safe against every attacker.
- Losing both the passphrase and the recovery key makes the vault unrecoverable by design. There is no backdoor.

## Before public distribution

1. Have an independent security review of the vault format, transfer protocol, and desktop/Android clients.
2. Ship a privacy policy that states there is no analytics or advertising telemetry in the free core.
3. Code-sign Windows and macOS builds when certificates are available.
4. Keep recovery and import overwrite warnings visible in the UI.

## Reporting issues

If you find a security problem, describe it privately to the project maintainer before public disclosure when practical. Do not include real vault passphrases, recovery keys, or decrypted password lists in reports.
