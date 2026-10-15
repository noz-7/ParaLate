# ParaLate Premium key generator

Run `generate_premium_key.bat` and enter a start date (`YYYY-MM-DD`, blank
means today) and a duration. The generated code is signed with the existing
Ed25519 issuer key at:

`%APPDATA%\ParaLate\issuer\issuer_ed25519_private.pem`

The generator verifies the code against the public key embedded in ParaLate
before displaying it. Activation dates must be within two days of the current
date because that is the app's accepted activation window.

The private key is not included in this folder and must never be distributed.
Keep it backed up securely and restrict its Windows file permissions.

The generator expects the `Paralate Generator` and `Paralate-free` folders to
be siblings. It uses the project's `.venv` when available; otherwise Python
must have the project's `cryptography` dependency installed.
