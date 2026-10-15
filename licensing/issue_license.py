"""Issue a signed offline license; keep the private key outside the app bundle."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from licensing.offline_provider import (
    OfflineLicenseProvider,
    _DURATIONS,
    add_membership_period,
    crc32_text,
    format_license_date,
)


def issue_license(start: date, duration: str, private_key_path: Path) -> str:
    if duration not in _DURATIONS:
        raise ValueError("unsupported membership duration")
    private_key = serialization.load_pem_private_key(
        private_key_path.read_bytes(),
        password=None,
    )
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("issuer key must be Ed25519")

    expires = add_membership_period(start, duration)
    parts = (
        crc32_text(format_license_date(start)),
        crc32_text(duration),
        crc32_text(format_license_date(expires)),
    )
    payload = OfflineLicenseProvider._signed_payload(
        start, duration, *parts
    )
    signature = private_key.sign(payload).hex().upper()
    return "-".join((*parts, signature))

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--key", required=True, type=Path,
        help="offline issuer private PEM (never distribute with the app)",
    )
    parser.add_argument("--start", type=date.fromisoformat, default=date.today())
    parser.add_argument("--duration", choices=tuple(_DURATIONS), required=True)
    args = parser.parse_args()
    print(issue_license(args.start, args.duration, args.key))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
