"""Background translation pipeline.

Order: hash -> cache -> quota -> extract -> translate -> render ->
interleave -> encrypt -> store. UI only sees localized signal payloads.
"""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from PyQt6.QtCore import QObject, pyqtSignal

from app.config import Config
from app.constants import ENCRYPTION_VERSION, FREE_PAGE_LIMIT
from app.network import NetworkStatus
from licensing.limits import QuotaService
from pdf.extractor import ExtractionCancelled, NoTextFoundError, extract_models, sample_text
from pdf.interleaver import InterleaveError, build_interleaved
from pdf.loader import PdfOpenError, open_pdf_path
from pdf.metadata import apply_metadata, serialize
from pdf.translator_renderer import TranslationMap, build_translation_document
from security.encryption import EncryptionError
from security.hashing import document_cache_key, sha256_file
from storage.database import Database, DatabaseError
from storage.encrypted_document import DocumentStoreError, EncryptedDocumentStore
from storage.models import DocumentRecord, DocumentStatus
from storage.paths import AppPaths
from storage.repository import DocumentRepository
from translation.base import TranslationError
from translation.cache import TranslationCache
from translation.manager import TranslationCancelled, TranslationManager

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class TranslationJob:
    file_path: str
    original_filename: str
    source_language: str
    target_language: str
    is_premium: bool


class TranslationWorker(QObject):
    """Runs inside a QThread; communicates only via signals."""

    status_changed = pyqtSignal(str)                 # i18n key
    progress = pyqtSignal(int, int, int)             # percent, page, total pages
    info = pyqtSignal(str, str, str)                 # key, param1, param2
    finished_ok = pyqtSignal(str, str)               # document_id, "new"|"reused"
    failed = pyqtSignal(str, str, str)               # code, param1, param2
    cancelled = pyqtSignal()

    def __init__(
        self,
        paths: AppPaths,
        config: Config,
        db: Database,
        documents: DocumentRepository,
        quota: QuotaService,
        store: EncryptedDocumentStore,
        network: NetworkStatus,
        job: TranslationJob,
    ) -> None:
        super().__init__()
        self._paths = paths
        self._config = config
        self._db = db
        self._documents = documents
        self._quota = quota
        self._store = store
        self._network = network
        self._job = job
        self._cancel = False

    # ------------------------------------------------------------------ #
    def request_cancel(self) -> None:
        self._cancel = True

    def _should_cancel(self) -> bool:
        return self._cancel

    # ------------------------------------------------------------------ #
    def run(self) -> None:
        document_id: str | None = None
        quota_day: str | None = None
        consumed = False
        try:
            if not self._network.online:
                self.failed.emit("offline", "", "")
                return

            self.status_changed.emit("status_hashing")
            document_hash = sha256_file(self._job.file_path)
            cache_key = document_cache_key(
                document_hash, self._job.source_language, self._job.target_language
            )

            existing = self._documents.find_by_cache_key(cache_key)
            if existing is not None:
                self._documents.touch(existing.document_id)
                self.finished_ok.emit(existing.document_id, "reused")
                return

            self.status_changed.emit("status_opening")
            doc = open_pdf_path(self._job.file_path)
            try:
                page_count = doc.page_count

                if not self._job.is_premium and page_count > FREE_PAGE_LIMIT:
                    self.failed.emit("page_limit", str(page_count), str(FREE_PAGE_LIMIT))
                    return

                limit = self._quota.can_translate(self._job.is_premium, page_count)
                if not limit.allowed:
                    self.failed.emit(limit.code, "", "")
                    return

                quota_day = self._quota.consume()
                consumed = True

                document_id = secrets.token_hex(8)
                record = DocumentRecord(
                    document_id=document_id,
                    original_filename=self._job.original_filename,
                    document_hash=document_hash,
                    source_language=self._job.source_language,
                    target_language=self._job.target_language,
                    page_count=page_count,
                    created_at=_now_iso(),
                    last_opened_at=_now_iso(),
                    storage_path="",
                    status=DocumentStatus.PROCESSING.value,
                    encryption_version=ENCRYPTION_VERSION,
                    cache_key=cache_key,
                )
                self._documents.create(record)

                self.status_changed.emit("status_extracting")
                models = extract_models(doc, should_cancel=self._should_cancel)

                cache = TranslationCache(self._db)
                manager = TranslationManager(
                    cache=cache,
                    allow_fallback=bool(self._config.get("allow_provider_fallback", True)),
                    on_fallback=self._on_fallback,
                    should_cancel=self._should_cancel,
                )
                if not manager.available_providers():
                    self.failed.emit("provider_unavailable", "", "")
                    return

                total_blocks = sum(len(m.translatable_blocks) for m in models) or 1
                translations: TranslationMap = {}
                done = 0
                self.status_changed.emit("status_translating")
                for page_index, model in enumerate(models):
                    page_map: dict[int, str] = {}
                    for block in model.translatable_blocks:
                        if self._should_cancel():
                            raise ExtractionCancelled()
                        translated = manager.translate(
                            block.text, self._job.source_language, self._job.target_language
                        )
                        page_map[block.index] = translated
                        done += 1
                        percent = 5 + int(85 * done / total_blocks)
                        self.progress.emit(percent, page_index + 1, len(models))
                    translations[page_index] = page_map

                if self._should_cancel():
                    raise ExtractionCancelled()

                self.status_changed.emit("status_rendering")
                trans_doc = build_translation_document(doc, models, translations)
                try:
                    self.progress.emit(93, len(models), len(models))
                    self.status_changed.emit("status_interleaving")
                    interleaved = build_interleaved(doc, trans_doc)
                    apply_metadata(
                        interleaved,
                        self._job.original_filename,
                        self._job.source_language,
                        self._job.target_language,
                    )
                    pdf_bytes = serialize(interleaved)
                    interleaved.close()
                    trans_doc.close()
                finally:
                    doc.close()

                self.status_changed.emit("status_storing")
                path = self._store.save(document_id, pdf_bytes)
                self._documents.complete(document_id, str(path))
                consumed = False  # success: slot stays spent
                document_id = None
                self.progress.emit(100, len(models), len(models))
                self.finished_ok.emit(record.document_id, "new")
            except BaseException:
                if not doc.is_closed:
                    doc.close()
                raise
        except ExtractionCancelled:
            self._cleanup_partial(document_id)
            if consumed and quota_day:
                self._quota.refund(quota_day)
            self.cancelled.emit()
        except PdfOpenError as error:
            self._cleanup_partial(document_id)
            self._refund(consumed, quota_day)
            self.failed.emit(error.code, "", "")
        except NoTextFoundError:
            self._cleanup_partial(document_id)
            self._refund(consumed, quota_day)
            self.failed.emit("no_text", "", "")
        except TranslationCancelled:
            self._cleanup_partial(document_id)
            self._refund(consumed, quota_day)
            self.cancelled.emit()
        except TranslationError as error:
            self._cleanup_partial(document_id)
            self._refund(consumed, quota_day)
            logger.warning("translation failed: %s %s", error.code, error.detail)
            self.failed.emit(error.code, "", "")
        except (DocumentStoreError, EncryptionError) as error:
            self._cleanup_partial(document_id)
            self._refund(consumed, quota_day)
            self.failed.emit(getattr(error, "code", "disk"), "", "")
        except InterleaveError as error:
            self._cleanup_partial(document_id)
            self._refund(consumed, quota_day)
            self.failed.emit(str(error.code), "", "")
        except DatabaseError as error:
            self._cleanup_partial(document_id)
            self._refund(consumed, quota_day)
            self.failed.emit(error.code, "", "")
        except OSError as error:
            self._cleanup_partial(document_id)
            self._refund(consumed, quota_day)
            logger.exception("io failure during translation")
            self.failed.emit("disk", "", "")
        except Exception:
            self._cleanup_partial(document_id)
            self._refund(consumed, quota_day)
            logger.exception("unexpected translation failure")
            self.failed.emit("internal", "", "")

    # ------------------------------------------------------------------ #
    def _on_fallback(self, failed_provider: str, next_provider: str) -> None:
        self.info.emit("info_fallback", failed_provider, next_provider)

    def _refund(self, consumed: bool, quota_day: str | None) -> None:
        if consumed and quota_day:
            self._quota.refund(quota_day)

    def _cleanup_partial(self, document_id: str | None) -> None:
        if document_id:
            try:
                self._documents.delete(document_id)
            except DatabaseError:
                logger.warning("could not clean partial document row")
