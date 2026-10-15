"""License provider abstraction. No provider is hard-coded into the app."""
from __future__ import annotations

from abc import ABC, abstractmethod

from storage.models import LicenseInfo


class LicenseError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class LicenseProvider(ABC):
    """Validates a license key and returns its entitlement information."""

    name: str = "base"

    @abstractmethod
    def verify(self, license_key: str) -> LicenseInfo:
        """Raise LicenseError when the key is invalid/unverifiable."""
