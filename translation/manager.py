"""TranslationManager: cache → provider chain → retry → controlled fallback."""
from __future__ import annotations

import logging
import re
import time
from typing import Callable, Iterable

from app.constants import (
    ALLOW_PROVIDER_FALLBACK,
    TRANSLATE_MAX_CHARS,
    TRANSLATE_RETRY_ATTEMPTS,
    TRANSLATE_RETRY_BACKOFF,
)
from translation.base import (
    FatalTranslationError,
    TranslationError,
    TranslationErrorCode,
    TranslationProvider,
    TransientTranslationError,
)
from translation.cache import TranslationCache
from translation.google import GoogleTranslateProvider
from translation.libretranslate import LibreTranslateProvider
from translation.microsoft import MicrosoftTranslatorProvider
from translation.mymemory import MyMemoryProvider

logger = logging.getLogger(__name__)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")


class TranslationCancelled(TranslationError):
    def __init__(self) -> None:
        super().__init__(TranslationErrorCode.CANCELLED)


def build_default_providers() -> list[TranslationProvider]:
    """Providers in configured order; unavailable ones are skipped later."""
    return [
        GoogleTranslateProvider(),
        MyMemoryProvider(),
        MicrosoftTranslatorProvider(),
        LibreTranslateProvider(),
    ]


class TranslationManager:
    """Single entry point used by the worker. Owns caching and fallback."""

    def __init__(
        self,
        providers: Iterable[TranslationProvider] | None = None,
        cache: TranslationCache | None = None,
        allow_fallback: bool = ALLOW_PROVIDER_FALLBACK,
        on_fallback: Callable[[str, str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._providers = list(providers) if providers is not None else build_default_providers()
        self._cache = cache
        self._allow_fallback = allow_fallback
        self._on_fallback = on_fallback
        self._should_cancel = should_cancel or (lambda: False)
        self._sleep = sleep
        self.active_provider_name: str = ""

    def available_providers(self) -> list[TranslationProvider]:
        return [p for p in self._providers if p.is_available()]

    def translate(self, text: str, source: str, target: str) -> str:
        """Translate one text unit with caching, retry and fallback."""
        stripped = text.strip()
        if not stripped:
            return text

        candidates = self.available_providers()
        if not candidates:
            raise TranslationError(TranslationErrorCode.UNAVAILABLE, "no provider configured")

        last_error: TranslationError | None = None
        for index, provider in enumerate(candidates):
            cached = self._cached(provider, source, target, stripped)
            if cached is not None:
                self.active_provider_name = provider.name
                return cached
            try:
                result = self._request_with_retry(provider, stripped, source, target)
            except FatalTranslationError as error:
                logger.warning("provider %s fatal: %s", provider.name, error.code)
                last_error = error
                if not self._should_fallback(index, candidates):
                    raise
                self._notify_fallback(provider.name, candidates[index + 1].name)
                continue
            except TransientTranslationError as error:
                logger.warning("provider %s transient: %s", provider.name, error.code)
                last_error = error
                if not self._should_fallback(index, candidates):
                    raise
                self._notify_fallback(provider.name, candidates[index + 1].name)
                continue
            self.active_provider_name = provider.name
            self._store(provider, source, target, stripped, result)
            return result
        raise last_error or TranslationError(TranslationErrorCode.UNAVAILABLE, "chain exhausted")

    def detect(self, text: str) -> str | None:
        for provider in self.available_providers():
            try:
                result = provider.detect(text[:500])
            except Exception:
                logger.debug("detect failed on %s", provider.name, exc_info=True)
                continue
            if result and result.language:
                return result.language
        return None

    # --- internals --------------------------------------------------------- #
    def _should_fallback(self, index: int, candidates: list[TranslationProvider]) -> bool:
        return self._allow_fallback and index + 1 < len(candidates)

    def _notify_fallback(self, failed: str, next_name: str) -> None:
        if self._on_fallback:
            try:
                self._on_fallback(failed, next_name)
            except Exception:
                logger.debug("fallback notification failed", exc_info=True)

    def _request_with_retry(
        self, provider: TranslationProvider, text: str, source: str, target: str
    ) -> str:
        chunks = self._chunk(text, provider.max_chars or TRANSLATE_MAX_CHARS)
        parts: list[str] = []
        for chunk in chunks:
            parts.append(self._single_call(provider, chunk, source, target))
        return " ".join(part.strip() for part in parts if part.strip())

    def _single_call(
        self, provider: TranslationProvider, text: str, source: str, target: str
    ) -> str:
        attempts = 1 + max(0, TRANSLATE_RETRY_ATTEMPTS)
        last: TranslationError | None = None
        for attempt in range(attempts):
            if self._should_cancel():
                raise TranslationCancelled()
            try:
                return provider.translate(text, source, target)
            except TransientTranslationError as error:
                last = error
                if error.code == TranslationErrorCode.CANCELLED:
                    raise
                if attempt + 1 < attempts:
                    delay = TRANSLATE_RETRY_BACKOFF * (2 ** attempt)
                    self._sleep(delay)
        assert last is not None
        raise last

    @staticmethod
    def _chunk(text: str, limit: int) -> list[str]:
        if len(text) <= limit:
            return [text]
        chunks: list[str] = []
        current = ""
        for piece in _SENTENCE_SPLIT.split(text):
            if piece is None:
                continue
            if current and len(current) + len(piece) + 1 > limit:
                chunks.append(current)
                current = piece
            else:
                current = f"{current} {piece}".strip() if current else piece
            while len(current) > limit:  # pathological single "sentence"
                chunks.append(current[:limit])
                current = current[limit:]
        if current:
            chunks.append(current)
        return chunks or [text]

    def _cached(self, provider: TranslationProvider, source: str, target: str, text: str) -> str | None:
        if self._cache is None:
            return None
        try:
            return self._cache.get(provider.name, source, target, text)
        except Exception:
            logger.debug("cache lookup failed", exc_info=True)
            return None

    def _store(
        self, provider: TranslationProvider, source: str, target: str,
        text: str, translated: str,
    ) -> None:
        if self._cache is None:
            return
        try:
            self._cache.put(provider.name, source, target, text, translated)
        except Exception:
            logger.debug("cache store failed", exc_info=True)
