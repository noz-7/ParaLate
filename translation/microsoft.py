"""Microsoft Azure Translator adapter (requires key + region)."""
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

_ENDPOINT = "https://api.cognitive.microsoft.com/translator/v3.0/translate"
_DETECT_URL = "https://api.cognitive.microsoft.com/translator/v3.0/detect"


class MicrosoftTranslatorProvider(TranslationProvider):
    name = "microsoft"
    max_chars = 25000

    def __init__(self, api_key: str | None = None, region: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else get_secret("MICROSOFT_TRANSLATOR_API_KEY")
        self._region = region if region is not None else get_secret("MICROSOFT_TRANSLATOR_REGION")
        self._session = requests.Session()

    def is_available(self) -> bool:
        return bool(self._api_key and self._region)

    def _headers(self) -> dict[str, str]:
        headers = {"Ocp-Apim-Subscription-Key": self._api_key or ""}
        if self._region:
            headers["Ocp-Apim-Subscription-Region"] = self._region
        return headers

    def translate(self, text: str, source: str, target: str) -> str:
        if not self.is_available():
            raise FatalTranslationError(TranslationErrorCode.UNAVAILABLE, "microsoft not configured")
        params = [("api-version", "3.0"), ("to", target)]
        if source and source != "auto":
            params.append(("from", source))
        try:
            response = self._session.post(
                _ENDPOINT, params=params, headers=self._headers(), json=[{"Text": text}], timeout=20
            )
        except requests.RequestException as exc:
            raise TransientTranslationError(TranslationErrorCode.TIMEOUT, str(exc)) from exc
        if response.status_code in (401, 403):
            raise FatalTranslationError(TranslationErrorCode.AUTH, f"status {response.status_code}")
        if response.status_code == 429:
            raise TransientTranslationError(TranslationErrorCode.RATE_LIMITED, "429")
        if response.status_code >= 500:
            raise TransientTranslationError(TranslationErrorCode.UNAVAILABLE, str(response.status_code))
        if response.status_code != 200:
            raise TransientTranslationError(TranslationErrorCode.BAD_RESPONSE, str(response.status_code))
        try:
            return response.json()[0]["translations"][0]["text"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise TransientTranslationError(
                TranslationErrorCode.BAD_RESPONSE, "unexpected payload"
            ) from exc

    def detect(self, text: str) -> "object | None":
        if not self.is_available():
            return None
        from translation.base import DetectionResult

        try:
            response = self._session.post(
                _DETECT_URL, params=[("api-version", "3.0")],
                headers=self._headers(), json=[{"Text": text[:500]}], timeout=10,
            )
            if response.status_code != 200:
                return None
            first = response.json()[0]
            return DetectionResult(
                language=first["language"], confidence=float(first.get("score", 0.0))
            )
        except Exception:
            logger.debug("microsoft detection failed", exc_info=True)
            return None
