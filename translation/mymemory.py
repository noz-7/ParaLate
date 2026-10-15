"""MyMemory Translation API adapter (free, keyless, rate limited).

Used as a keyless fallback when the primary Google endpoint is unavailable.
Best for sentence-level text; single words may return translation-memory
matches of varying quality.
"""
from __future__ import annotations

import logging

import requests

from translation.base import (
    DetectionResult,
    TranslationError,
    TranslationErrorCode,
    TranslationProvider,
    TransientTranslationError,
)

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.mymemory.translated.net/get"


class MyMemoryProvider(TranslationProvider):
    name = "mymemory"
    max_chars = 450  # API limit is 500 bytes per query

    def __init__(self) -> None:
        self._session = requests.Session()

    def is_available(self) -> bool:
        return True

    def translate(self, text: str, source: str, target: str) -> str:
        source_code = "autodetect" if not source or source == "auto" else source
        params = {"q": text, "langpair": f"{source_code}|{target}"}
        try:
            response = self._session.get(_ENDPOINT, params=params, timeout=20)
        except requests.RequestException as exc:
            raise TransientTranslationError(TranslationErrorCode.TIMEOUT, str(exc)) from exc
        if response.status_code == 429:
            raise TransientTranslationError(TranslationErrorCode.RATE_LIMITED, "429")
        if response.status_code >= 500:
            raise TransientTranslationError(
                TranslationErrorCode.UNAVAILABLE, str(response.status_code)
            )
        if response.status_code != 200:
            raise TransientTranslationError(
                TranslationErrorCode.BAD_RESPONSE, str(response.status_code)
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise TransientTranslationError(
                TranslationErrorCode.BAD_RESPONSE, "non-json"
            ) from exc
        if data.get("quotaFinished") or int(data.get("responseStatus") or 200) == 429:
            raise TransientTranslationError(TranslationErrorCode.RATE_LIMITED, "quota")
        status = int(data.get("responseStatus") or 200)
        if status >= 500:
            raise TransientTranslationError(TranslationErrorCode.UNAVAILABLE, str(status))
        if status != 200:
            raise TransientTranslationError(TranslationErrorCode.BAD_RESPONSE, str(status))
        translated = (data.get("responseData") or {}).get("translatedText")
        if not isinstance(translated, str) or not translated:
            raise TransientTranslationError(TranslationErrorCode.BAD_RESPONSE, "empty result")
        return translated

    def detect(self, text: str) -> DetectionResult | None:
        try:
            response = self._session.get(
                _ENDPOINT,
                params={"q": text[:400], "langpair": "autodetect|en"},
                timeout=10,
            )
            if response.status_code != 200:
                return None
            language = (response.json().get("responseData") or {}).get("detectedLanguage")
            if isinstance(language, str) and language:
                return DetectionResult(language=language, confidence=0.8)
        except Exception:
            logger.debug("mymemory detection failed", exc_info=True)
        return None
