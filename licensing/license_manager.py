"""Persisted FREE/PREMIUM state with local Ed25519 license verification."""
from __future__ import annotations

import json
import logging
import threading
from datetime import date

from licensing.base import LicenseError, LicenseProvider
from licensing.offline_provider import OfflineLicenseProvider
from storage.models import LicenseInfo, LicenseTier
from storage.repository import AppStateRepository

logger = logging.getLogger(__name__)

_STATE_KEY = "license"
_DEFAULT_PROVIDERS: dict[str, LicenseProvider] = {
    OfflineLicenseProvider.name: OfflineLicenseProvider(),
}


class LicenseManager:
    def __init__(
        self,
        state: AppStateRepository,
        providers: dict[str, LicenseProvider] | None = None,
        default_provider: str = OfflineLicenseProvider.name,
    ) -> None:
        self._state = state
        self._providers = dict(providers or _DEFAULT_PROVIDERS)
        self._default_provider = default_provider
        self._lock = threading.RLock()
        self._info, self._last_seen = self._load()

    @property
    def info(self) -> LicenseInfo:
        self.is_premium
        return self._info

    @property
    def is_premium(self) -> bool:
        with self._lock:
            if not self._info.is_premium:
                return False
            today = date.today()
            if self._last_seen is not None and today < self._last_seen:
                logger.warning("system date moved behind the last observed license date")
                return False
            if self._last_seen != today:
                try:
                    self._persist(self._info, today)
                except Exception:
                    logger.exception("failed to persist offline license clock state")
                    return False
                self._last_seen = today
            if self._info.starts_at and today < date.fromisoformat(self._info.starts_at):
                return False
            if not self._info.expires_at or today >= date.fromisoformat(self._info.expires_at):
                return False
            return True

    @property
    def license_valid(self) -> bool:
        return self.is_premium

    @property
    def expires_at(self) -> str:
        return self._info.expires_at

    @property
    def is_expired(self) -> bool:
        return (
            self._info.is_premium
            and bool(self._info.expires_at)
            and date.today() >= date.fromisoformat(self._info.expires_at)
        )

    @property
    def starts_at(self) -> str:
        return self._info.starts_at

    @property
    def is_not_yet_valid(self) -> bool:
        return (
            self._info.is_premium
            and bool(self._info.starts_at)
            and date.today() < date.fromisoformat(self._info.starts_at)
        )

    def allows(self, feature: str) -> bool:
        if feature not in {"offline_open", "unlimited_pages", "download", "ad_free"}:
            raise ValueError(f"unknown premium feature: {feature}")
        return self.is_premium

    def activate(self, license_key: str) -> LicenseInfo:
        provider = self._providers.get(self._default_provider)
        if provider is None:
            raise LicenseError("provider_missing")
        if isinstance(provider, OfflineLicenseProvider):
            verified = provider.verify(license_key, activation_date=date.today())
        else:
            verified = provider.verify(license_key)
        if not verified.is_premium or not verified.expires_at or not verified.license_key:
            raise LicenseError("invalid")
        today = date.today()
        with self._lock:
            self._persist(verified, today)
            self._info = verified
            self._last_seen = today
        logger.info("license activated via %s", verified.provider)
        return verified

    def clear(self) -> None:
        """Downgrade back to FREE."""
        info = LicenseInfo(tier=LicenseTier.FREE)
        with self._lock:
            self._persist(info, None)
            self._info = info
            self._last_seen = None

    def reload(self) -> None:
        with self._lock:
            self._info, self._last_seen = self._load()

    def _load(self) -> tuple[LicenseInfo, date | None]:
        try:
            raw = self._state.get(_STATE_KEY)
            if not raw:
                return LicenseInfo(tier=LicenseTier.FREE), None
            data = json.loads(raw)
            if data.get("tier") != LicenseTier.PREMIUM.value:
                return LicenseInfo(tier=LicenseTier.FREE), None
            if data.get("version") != 1:
                raise ValueError("unsupported license state version")
            key = str(data["license_key"])
            start = date.fromisoformat(str(data["starts_at"]))
            last_seen = date.fromisoformat(str(data["last_seen"]))
            provider = self._providers.get(str(data["provider"]))
            if provider is None:
                raise ValueError("license provider is unavailable")
            if isinstance(provider, OfflineLicenseProvider):
                info = provider.verify(key, license_start=start)
            else:
                info = provider.verify(key)
            if (
                not info.is_premium
                or info.starts_at != start.isoformat()
                or info.provider != data["provider"]
            ):
                raise ValueError("persisted license does not verify")
            return info, last_seen
        except (LicenseError, ValueError, KeyError, TypeError) as error:
            logger.info("offline license state is invalid: %s", type(error).__name__)
            return LicenseInfo(tier=LicenseTier.FREE), None
        except Exception:
            logger.exception("failed to load offline license state; using FREE")
            return LicenseInfo(tier=LicenseTier.FREE), None

    def _persist(self, info: LicenseInfo, last_seen: date | None) -> None:
        if not info.is_premium:
            self._state.set(_STATE_KEY, json.dumps({"version": 1, "tier": "FREE"}))
            return
        payload = json.dumps(
            {
                "version": 1,
                "tier": info.tier.value,
                "provider": info.provider,
                "license_key": info.license_key,
                "starts_at": info.starts_at,
                "expires_at": info.expires_at,
                "duration": info.duration,
                "last_seen": (last_seen or date.today()).isoformat(),
            },
            separators=(",", ":"),
        )
        self._state.set(_STATE_KEY, payload)
