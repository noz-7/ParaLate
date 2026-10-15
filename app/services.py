"""Shared service container: built once at startup, passed to the UI."""
from __future__ import annotations

from dataclasses import dataclass

from app.config import Config
from app.network import NetworkStatus
from ads.manager import AdManager
from licensing.license_manager import LicenseManager
from licensing.limits import QuotaService
from security.encryption import DocumentCipher
from storage.database import Database
from storage.encrypted_document import EncryptedDocumentStore
from storage.paths import AppPaths
from storage.repository import AppStateRepository, DocumentRepository, UsageRepository


@dataclass
class AppServices:
    paths: AppPaths
    config: Config
    db: Database
    documents: DocumentRepository
    usage: UsageRepository
    state: AppStateRepository
    quota: QuotaService
    cipher: DocumentCipher
    store: EncryptedDocumentStore
    network: NetworkStatus
    license: LicenseManager
    ads: AdManager
