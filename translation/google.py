"""Google Translate adapter.

Uses the official Cloud Translation v2 API when GOOGLE_TRANSLATE_API_KEY is
set; otherwise falls back to the public Google Translate web endpoint
(client=gtx), which needs no key but is rate limited.
"""
from __future__ import annotations

import logging

import requests

from security.secrets import get_secret
from translation.base import (
    DetectionResult,
    FatalTranslationError,
    TranslationError,
    TranslationErrorCode,
    TranslationProvider,
    TransientTranslationError,
)

logger = logging.getLogger(__name__)

_API_URL = "https://translation.googleapis.com/language/translate/v2"
_GTX_URL = "https://translate.googleapis.com/translate_a/single"
_GTX_CLIENT = "gtx"


def _map_http_error(status: int, detail: str) -> TranslationError:
    if status in (401, 403):
        return FatalTranslationError(TranslationErrorCode.AUTH, detail)
    if status == 429:
        return TransientTranslationError(TranslationErrorCode.RATE_LIMITED, detail)
    if status >= 500:
        return TransientTranslationError(TranslationErrorCode.UNAVAILABLE, detail)
    return TransientTranslationError(TranslationErrorCode.BAD_RESPONSE, detail)


class GoogleTranslateProvider(TranslationProvider):
    name = "google"
    max_chars = 4500

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else get_secret("GOOGLE_TRANSLATE_API_KEY")
        self._session = requests.Session()

    def is_available(self) -> bool:
        return True  # public endpoint works without a key

    def translate(self, text: str, source: str, target: str) -> str:
        if self._api_key:
            return self._translate_api(text, source, target)
        return self._translate_gtx(text, source, target)

    def detect(self, text: str) -> DetectionResult | None:
        if self._api_key:
            return self._detect_api(text)
        return self._detect_gtx(text)

    # --- keyless web endpoint ------------------------------------------- #
    def _translate_gtx(self, text: str, source: str, target: str) -> str:
        params = {
            "client": _GTX_CLIENT,
            "sl": source if source and source != "auto" else "auto",
            "tl": target,
            "dt": "t",
            "q": text,
        }
        try:
            response = self._session.get(_GTX_URL, params=params, timeout=20)
        except requests.RequestException as exc:
            raise TransientTranslationError(TranslationErrorCode.TIMEOUT, str(exc)) from exc
        if response.status_code != 200:
            raise _map_http_error(response.status_code, f"gtx status {response.status_code}")
        try:
            data = response.json()
            sentences = data[0]
            return "".join(part[0] for part in sentences if part and part[0])
        except (ValueError, IndexError, TypeError, KeyError) as exc:
            raise TransientTranslationError(
                TranslationErrorCode.BAD_RESPONSE, "unexpected gtx payload"
            ) from exc

    def _detect_gtx(self, text: str) -> DetectionResult | None:
        params = {"client": _GTX_CLIENT, "sl": "auto", "tl": "en", "dt": "t", "q": text[:500]}
        try:
            response = self._session.get(_GTX_URL, params=params, timeout=10)
            if response.status_code != 200:
                return None
            detected = response.json()[2]
            if isinstance(detected, str) and detected:
                return DetectionResult(language=detected, confidence=0.9)
        except Exception:
            logger.debug("gtx detection failed", exc_info=True)
        return None

    # --- official API ------------------------------------------------------ #
    def _translate_api(self, text: str, source: str, target: str) -> str:
        payload = {"q": text, "target": target, "format": "text"}
        if source and source != "auto":
            payload["source"] = source
        try:
            response = self._session.post(
                _API_URL,
                params={"key": self._api_key},
                json=payload,
                timeout=20,
            )
        except requests.RequestException as exc:
            raise TransientTranslationError(TranslationErrorCode.TIMEOUT, str(exc)) from exc
        if response.status_code not in (200, 201):
            raise _map_http_error(response.status_code, f"v2 status {response.status_code}")
        try:
            return response.json()["data"]["translations"][0]["translatedText"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise TransientTranslationError(
                TranslationErrorCode.BAD_RESPONSE, "unexpected v2 payload"
            ) from exc

    def _detect_api(self, text: str) -> DetectionResult | None:
        try:
            response = self._session.post(
                _API_URL + "/detect",
                params={"key": self._api_key},
                json={"q": text[:500]},
                timeout=10,
            )
            if response.status_code not in (200, 201):
                return None
            first = response.json()["data"]["detections"][0][0]
            return DetectionResult(
                language=first["language"], confidence=float(first.get("confidence", 0.0))
            )
        except Exception:
            logger.debug("v2 detection failed", exc_info=True)
            return None
