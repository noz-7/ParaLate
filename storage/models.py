"""Domain models. UI never touches SQL directly."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DocumentStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class LicenseTier(str, Enum):
    FREE = "FREE"
    PREMIUM = "PREMIUM"


@dataclass
class DocumentRecord:
    document_id: str
    original_filename: str
    document_hash: str
    source_language: str
    target_language: str
    page_count: int
    created_at: str
    last_opened_at: str
    storage_path: str
    status: str
    encryption_version: int
    cache_key: str

    @property
    def is_completed(self) -> bool:
        return self.status == DocumentStatus.COMPLETED.value


@dataclass
class DailyUsage:
    day: str
    count: int


@dataclass
class LicenseInfo:
    tier: LicenseTier
    provider: str = ""
    activated_at: str = ""
    fingerprint: str = ""
    starts_at: str = ""
    expires_at: str = ""
    duration: str = ""
    license_version: int = 0
    license_key: str = ""

    @property
    def is_premium(self) -> bool:
        return self.tier == LicenseTier.PREMIUM


@dataclass
class LimitResult:
    allowed: bool
    code: str = ""
    params: dict[str, str] = field(default_factory=dict)
