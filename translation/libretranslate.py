"""LibreTranslate adapter (self-hosted or paid instance recommended)."""
from __future__ import annotations

import logging

import requests

from security.secrets import get_secret
from translation.base import (
    FatalTranslationError,
    TranslationError,
    TranslationErrorCode,
    TranslationProvider,
    TransientTranslationError,
)

logger = logging.getLogger(__name__)

_DEFAULT_URL = "https://libretranslate.com"


class LibreTranslateProvider(TranslationProvider):
    name = "libretranslate"
    max_chars = 4000

    def __init__(self, url: str | None = None, api_key: str | None = None) -> None:
        self._url = (url or get_secret("LIBRETRANSLATE_URL") or _DEFAULT_URL).rstrip("/")
        self._api_key = api_key if api_key is not None else get_secret("LIBRETRANSLATE_API_KEY")
        self._session = requests.Session()

    def is_available(self) -> bool:
        return bool(self._url)

    def translate(self, text: str, source: str, target: str) -> str:
        payload = {
            "q": text,
            "source": "auto" if not source or source == "auto" else source,
            "target": target,
            "format": "text",
        }
        if self._api_key:
            payload["api_key"] = self._api_key
        try:
            response = self._session.post(
                f"{self._url}/translate", json=payload, timeout=20
            )
        except requests.RequestException as exc:
            raise TransientTranslationError(TranslationErrorCode.TIMEOUT, str(exc)) from exc
        if response.status_code in (401, 403):
            raise FatalTranslationError(TranslationErrorCode.AUTH, str(response.status_code))
        if response.status_code == 400 and "api key" in response.text.lower():
            # public instance demanding a key: not fixable by retrying
            raise FatalTranslationError(TranslationErrorCode.AUTH, "api key required")
        if response.status_code == 429:
            raise TransientTranslationError(TranslationErrorCode.RATE_LIMITED, "429")
        if response.status_code >= 500 or response.status_code == 404:
            raise TransientTranslationError(
                TranslationErrorCode.UNAVAILABLE, str(response.status_code)
            )
        if response.status_code != 200:
            raise TransientTranslationError(TranslationErrorCode.BAD_RESPONSE, str(response.status_code))
        try:
            translated = response.json()["translatedText"]
        except (ValueError, KeyError, TypeError) as exc:
            raise TransientTranslationError(
                TranslationErrorCode.BAD_RESPONSE, "unexpected payload"
            ) from exc
        if not isinstance(translated, str):
            raise TransientTranslationError(TranslationErrorCode.BAD_RESPONSE, "non-string result")
        return translated
