"""Signed, offline-verifiable, time-limited premium licenses."""
from __future__ import annotations

import calendar
import re
import zlib
from datetime import date, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from licensing.base import LicenseError, LicenseProvider
from licensing.public_key import LICENSE_PUBLIC_KEY
from storage.models import LicenseInfo, LicenseTier

_KEY_RE = re.compile(r"^([0-9A-Fa-f]{8})-([0-9A-Fa-f]{8})-([0-9A-Fa-f]{8})-([0-9A-Fa-f]{128})$")
_DURATIONS = {
    "7gün": ("days", 7),
    "14gün": ("days", 14),
    "1ay": ("months", 1),
    "3ay": ("months", 3),
    "6ay": ("months", 6),
    "1yıl": ("years", 1),
}
_SIGNING_CONTEXT = b"ParaLate premium license v1"


def crc32_text(text: str) -> str:
    return f"{zlib.crc32(text.encode('utf-8')) & 0xFFFFFFFF:08X}"


def format_license_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def add_membership_period(start: date, duration: str) -> date:
    kind, amount = _DURATIONS[duration]
    if kind == "days":
        return start + timedelta(days=amount)
    if kind == "years":
        year = start.year + amount
        return start.replace(year=year, day=min(start.day, calendar.monthrange(year, start.month)[1]))
    month_index = start.year * 12 + start.month - 1 + amount
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return start.replace(
        year=year,
        month=month,
        day=min(start.day, calendar.monthrange(year, month)[1]),
    )


class OfflineLicenseProvider(LicenseProvider):
    """Verify CRC-checked license fields and an Ed25519 issuer signature."""

    name = "offline-ed25519"

    def __init__(self, public_key: bytes = LICENSE_PUBLIC_KEY) -> None:
        self._public_key = Ed25519PublicKey.from_public_bytes(public_key)

    def verify(
        self,
        license_key: str,
        activation_date: date | None = None,
        license_start: date | None = None,
    ) -> LicenseInfo:
        compact = "".join(license_key.split()).upper()
        match = _KEY_RE.fullmatch(compact)
        if match is None:
            raise LicenseError("invalid")

        start_crc, duration_crc, expiry_crc, signature_text = match.groups()
        if license_start is not None:
            starts = [license_start]
        else:
            reference = activation_date or date.today()
            starts = [
                reference + timedelta(days=offset)
                for offset in range(-2, 3)
            ]
        start = next(
            (candidate for candidate in starts
             if crc32_text(format_license_date(candidate)) == start_crc),
            None,
        )
        if start is None:
            raise LicenseError("invalid")

        duration = next(
            (value for value in _DURATIONS if crc32_text(value) == duration_crc),
            None,
        )
        if duration is None:
            raise LicenseError("invalid")
        expiry = add_membership_period(start, duration)
        if crc32_text(format_license_date(expiry)) != expiry_crc:
            raise LicenseError("invalid")

        payload = self._signed_payload(start, duration, start_crc, duration_crc, expiry_crc)
        try:
            signature = bytes.fromhex(signature_text)
            if len(signature) != 64:
                raise ValueError("invalid signature length")
            self._public_key.verify(signature, payload)
        except (InvalidSignature, ValueError):
            raise LicenseError("invalid") from None

        if activation_date is not None and expiry <= activation_date:
            raise LicenseError("expired")

        return LicenseInfo(
            tier=LicenseTier.PREMIUM,
            provider=self.name,
            activated_at=format_license_date(start),
            fingerprint=f"{start_crc}-{duration_crc}-{expiry_crc}",
            starts_at=start.isoformat(),
            expires_at=expiry.isoformat(),
            duration=duration,
            license_version=1,
            license_key=compact,
        )

    @staticmethod
    def _signed_payload(
        start: date,
        duration: str,
        start_crc: str,
        duration_crc: str,
        expiry_crc: str,
    ) -> bytes:
        return b"|".join(
            (_SIGNING_CONTEXT, start.isoformat().encode("ascii"),
             duration.encode("utf-8"), start_crc.encode("ascii"),
             duration_crc.encode("ascii"), expiry_crc.encode("ascii"))
        )
