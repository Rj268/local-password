# Vault compatibility fixture

`computer.vault` is a synthetic desktop-created vault used by Android tests to verify cross-platform decoding, recovery, and invalid-data handling. Its test passphrase and recovery phrase are intentionally present in test source.

Keep this fixture when cleaning the repository. It is test input, not a build artifact or a user's saved vault. Never replace it with personal password data.
