"""Translation cache: same text never hits the provider twice."""
from __future__ import annotations

import logging

from security.hashing import sha256_text, translation_cache_key
from storage.database import Database, DatabaseError
from storage.repository import TranslationCacheRepository

logger = logging.getLogger(__name__)


class TranslationCache:
    def __init__(self, db: Database) -> None:
        self._repo = TranslationCacheRepository(db)

    @staticmethod
    def make_key(provider: str, source: str, target: str, text: str) -> str:
        return translation_cache_key(provider, source, target, text)

    def get(self, provider: str, source: str, target: str, text: str) -> str | None:
        key = self.make_key(provider, source, target, text)
        try:
            return self._repo.get(key)
        except DatabaseError:
            logger.warning("translation cache read failed")
            return None

    def put(self, provider: str, source: str, target: str, text: str, translated: str) -> None:
        key = self.make_key(provider, source, target, text)
        try:
            self._repo.put(
                cache_key=key,
                provider=provider,
                source=source,
                target=target,
                source_hash=sha256_text(text),
                translated=translated,
            )
        except DatabaseError:
            logger.warning("translation cache write failed")

    @staticmethod
    def source_fingerprint(text: str) -> str:
        return sha256_text(text)
