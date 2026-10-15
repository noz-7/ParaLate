"""AES-256-GCM encryption for ParaLate internal documents (.plt).

Key management order:
1. OS keyring (Windows Credential Manager / Secret Service)
2. Restricted file next to the config (POSIX mode 0600)
3. Generate a fresh key and persist it to the first store that works.
"""
from __future__ import annotations

import base64
import logging
import os
import sys
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.constants import ENCRYPTION_VERSION, KEYRING_SERVICE, MASTER_KEY_ENTRY, PLT_MAGIC
from storage.paths import AppPaths

logger = logging.getLogger(__name__)

_NONCE_SIZE = 12
_KEY_SIZE = 32


class EncryptionError(Exception):
    """Decryption/encryption failure with a user-safe message code."""

    def __init__(self, code: str = "encryption") -> None:
        super().__init__(code)
        self.code = code


def _keyring_get() -> bytes | None:
    try:
        import keyring

        stored = keyring.get_password(KEYRING_SERVICE, MASTER_KEY_ENTRY)
        return base64.urlsafe_b64decode(stored) if stored else None
    except Exception:
        logger.debug("keyring unavailable for read", exc_info=True)
        return None


def _keyring_set(key: bytes) -> bool:
    try:
        import keyring

        keyring.set_password(
            KEYRING_SERVICE, MASTER_KEY_ENTRY, base64.urlsafe_b64encode(key).decode("ascii")
        )
        return True
    except Exception:
        logger.debug("keyring unavailable for write", exc_info=True)
        return False


def _file_get(path: Path) -> bytes | None:
    try:
        if path.exists():
            raw = base64.urlsafe_b64decode(path.read_text(encoding="ascii").strip())
            if len(raw) == _KEY_SIZE:
                return raw
    except Exception:
        logger.exception("failed to read master key file")
    return None


def _file_set(path: Path, key: bytes) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(base64.urlsafe_b64encode(key).decode("ascii"), encoding="ascii")
        if sys.platform.startswith("posix"):
            path.chmod(0o600)
        return True
    except OSError:
        logger.exception("failed to write master key file")
        return False


class DocumentCipher:
    """Encrypts/decrypts whole PDF byte blobs for internal .plt storage."""

    def __init__(self, key: bytes) -> None:
        if len(key) != _KEY_SIZE:
            raise EncryptionError("invalid_key")
        self._aesgcm = AESGCM(key)

    @classmethod
    def load_or_create(cls, paths: AppPaths) -> "DocumentCipher":
        key = _keyring_get() or _file_get(paths.master_key_file)
        if key is None:
            key = os.urandom(_KEY_SIZE)
            if not _keyring_set(key):
                _file_set(paths.master_key_file, key)
            logger.info("generated new document master key")
        elif _file_get(paths.master_key_file) is None and _keyring_get() is None:
            _file_set(paths.master_key_file, key)
        return cls(key)

    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(_NONCE_SIZE)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, PLT_MAGIC)
        header = PLT_MAGIC + bytes([ENCRYPTION_VERSION]) + nonce
        return header + ciphertext

    def decrypt(self, blob: bytes) -> bytes:
        header_size = len(PLT_MAGIC) + 1 + _NONCE_SIZE
        if len(blob) < header_size or not blob.startswith(PLT_MAGIC):
            raise EncryptionError("not_a_plt_file")
        version = blob[len(PLT_MAGIC)]
        if version != ENCRYPTION_VERSION:
            raise EncryptionError("unsupported_version")
        nonce = blob[len(PLT_MAGIC) + 1 : header_size]
        ciphertext = blob[header_size:]
        try:
            return self._aesgcm.decrypt(nonce, ciphertext, PLT_MAGIC)
        except InvalidTag as exc:
            raise EncryptionError("decrypt_failed") from exc
