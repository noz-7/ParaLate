"""Internal .plt document storage: encrypt, write atomically, load in memory."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from security.encryption import DocumentCipher, EncryptionError
from storage.paths import safe_join

logger = logging.getLogger(__name__)


class DocumentStoreError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class EncryptedDocumentStore:
    """Keeps decrypted PDF bytes in memory only; plaintext never hits disk."""

    def __init__(self, documents_dir: Path, cipher: DocumentCipher) -> None:
        self._dir = documents_dir
        self._cipher = cipher

    def save(self, document_id: str, pdf_bytes: bytes) -> Path:
        """Encrypt and atomically persist; returns the .plt path."""
        blob = self._cipher.encrypt(pdf_bytes)
        self._dir.mkdir(parents=True, exist_ok=True)
        final = safe_join(self._dir, f"{document_id}.plt")
        tmp = final.with_suffix(".plt.tmp")
        try:
            tmp.write_bytes(blob)
            if sys.platform.startswith("posix"):
                tmp.chmod(0o600)
            os.replace(tmp, final)
        except OSError as exc:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise DocumentStoreError("disk") from exc
        return final

    def load(self, storage_path: str | Path) -> bytes:
        """Decrypt an internal document into memory."""
        path = Path(storage_path)
        try:
            safe_join(self._dir, path.name)
        except ValueError as exc:
            raise DocumentStoreError("invalid_path") from exc
        try:
            blob = path.read_bytes()
        except FileNotFoundError as exc:
            raise DocumentStoreError("missing_file") from exc
        except OSError as exc:
            raise DocumentStoreError("disk") from exc
        try:
            return self._cipher.decrypt(blob)
        except EncryptionError as exc:
            raise DocumentStoreError("decrypt_failed") from exc

    def delete(self, storage_path: str | Path) -> None:
        path = Path(storage_path)
        try:
            safe_join(self._dir, path.name)
        except ValueError:
            logger.warning("refused to delete path outside documents dir")
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.exception("failed to delete document file")
