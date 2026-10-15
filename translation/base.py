"""Provider abstraction. UI and PDF code only ever see this interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class TranslationErrorCode:
    """Stable codes; the UI maps them to localized messages."""

    OFFLINE = "offline"
    UNAVAILABLE = "provider_unavailable"
    RATE_LIMITED = "rate_limited"
    AUTH = "auth_error"
    TIMEOUT = "timeout"
    BAD_RESPONSE = "bad_response"
    CANCELLED = "cancelled"
    NOT_SUPPORTED = "not_supported"


class TranslationError(Exception):
    """Base error. `code` is UI-safe; `detail` is for logs only."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


class TransientTranslationError(TranslationError):
    """Recoverable (network blip, 5xx): eligible for retry/fallback."""


class FatalTranslationError(TranslationError):
    """Not recoverable by retrying (auth, unsupported language)."""


@dataclass(frozen=True)
class DetectionResult:
    language: str
    confidence: float = 0.0


class TranslationProvider(ABC):
    """Common interface: translator.translate(text, source, target)."""

    name: str = "base"
    max_chars: int = 3500

    @abstractmethod
    def is_available(self) -> bool:
        """Cheap check: credentials/server configured? No network call."""

    @abstractmethod
    def translate(self, text: str, source: str, target: str) -> str:
        """Translate one chunk. Raises TranslationError subclasses on failure."""

    def detect(self, text: str) -> DetectionResult | None:
        """Optional source-language detection."""
        return None

    def __repr__(self) -> str:  # never leak credentials
        return f"<{type(self).__name__} name={self.name!r}>"
