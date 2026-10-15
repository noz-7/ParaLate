"""Background loader for encrypted documents (keeps UI responsive)."""
from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal

from storage.encrypted_document import DocumentStoreError, EncryptedDocumentStore

logger = logging.getLogger(__name__)


class LoadDocumentWorker(QObject):
    """Decrypts a .plt into memory on a worker thread."""

    loaded = pyqtSignal(str, bytes)     # document_id, pdf bytes
    failed = pyqtSignal(str, str)       # document_id, error code

    def __init__(self, store: EncryptedDocumentStore, document_id: str, storage_path: str) -> None:
        super().__init__()
        self._store = store
        self._document_id = document_id
        self._storage_path = storage_path

    def run(self) -> None:
        try:
            data = self._store.load(self._storage_path)
            self.loaded.emit(self._document_id, data)
        except DocumentStoreError as error:
            logger.warning("document load failed: %s", error.code)
            self.failed.emit(self._document_id, error.code)
        except Exception:
            logger.exception("unexpected document load failure")
            self.failed.emit(self._document_id, "internal")
