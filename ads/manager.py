"""Ad manager: chooses the provider from the current license tier."""
from __future__ import annotations

from typing import Callable

from ads.base import AdInfo, AdProvider

_HOUSE_ADS = {
    "home": [
        AdInfo(
            title="ParaLate Premium",
            body="Sınırsız çeviri, sınırsız sayfa, reklamsız deneyim.",
            action="Detaylar",
        ),
        AdInfo(
            title="Derslerini iki dilde oku",
            body="Orijinal ve çeviri sayfaları yan yana — tek PDF, tek görüntüleyici.",
        ),
    ],
    "viewer": [
        AdInfo(
            title="Reklamsız okuma",
            body="Premium ile reklamlar tamamen kalkar.",
            action="Detaylar",
        ),
    ],
}


class DesktopAdProvider(AdProvider):
    """Static, offline house ads served in reserved UI strips."""

    name = "desktop"

    def __init__(self) -> None:
        self._cursor = 0

    def get_ad(self, context: str) -> AdInfo | None:
        ads = _HOUSE_ADS.get(context) or _HOUSE_ADS["home"]
        ad = ads[self._cursor % len(ads)]
        self._cursor += 1
        return ad


class DisabledAdProvider(AdProvider):
    name = "disabled"

    def get_ad(self, context: str) -> AdInfo | None:
        return None


class AdManager:
    """Single entry point for the UI; reflects license state live."""

    def __init__(self, is_premium: Callable[[], bool]) -> None:
        self._is_premium = is_premium
        self._free_provider: AdProvider = DesktopAdProvider()
        self._premium_provider: AdProvider = DisabledAdProvider()

    @property
    def enabled(self) -> bool:
        return not self._is_premium()

    def get_ad(self, context: str) -> AdInfo | None:
        provider = self._premium_provider if self._is_premium() else self._free_provider
        return provider.get_ad(context)
