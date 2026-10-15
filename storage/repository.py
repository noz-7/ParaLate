"""Repositories: all SQL lives here, parameterized, never in UI code."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from storage.database import Database, DatabaseError
from storage.models import DailyUsage, DocumentRecord, DocumentStatus

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class DocumentRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, record: DocumentRecord) -> None:
        with self._db.session() as conn:
            conn.execute(
                """INSERT INTO documents
                   (document_id, original_filename, document_hash, source_language,
                    target_language, page_count, created_at, last_opened_at,
                    storage_path, status, encryption_version, cache_key)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.document_id,
                    record.original_filename,
                    record.document_hash,
                    record.source_language,
                    record.target_language,
                    record.page_count,
                    record.created_at,
                    record.last_opened_at,
                    record.storage_path,
                    record.status,
                    record.encryption_version,
                    record.cache_key,
                ),
            )

    def mark_completed(self, document_id: str) -> None:
        self._set_status(document_id, DocumentStatus.COMPLETED)

    def complete(self, document_id: str, storage_path: str) -> None:
        """Transition processing -> completed once the .plt exists on disk."""
        with self._db.session() as conn:
            conn.execute(
                "UPDATE documents SET status = ?, storage_path = ? WHERE document_id = ?",
                (DocumentStatus.COMPLETED.value, storage_path, document_id),
            )

    def cleanup_incomplete(self) -> int:
        """Remove rows left behind by crashes/kills (partial state)."""
        with self._db.session() as conn:
            cursor = conn.execute(
                "DELETE FROM documents WHERE status = ?",
                (DocumentStatus.PROCESSING.value,),
            )
            return int(cursor.rowcount or 0)

    def mark_failed(self, document_id: str) -> None:
        self._set_status(document_id, DocumentStatus.FAILED)

    def _set_status(self, document_id: str, status: DocumentStatus) -> None:
        with self._db.session() as conn:
            conn.execute(
                "UPDATE documents SET status = ? WHERE document_id = ?",
                (status.value, document_id),
            )

    def find_by_cache_key(self, cache_key: str) -> DocumentRecord | None:
        with self._db.session() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE cache_key = ? AND status = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (cache_key, DocumentStatus.COMPLETED.value),
            ).fetchone()
        return _row_to_document(row) if row else None

    def find_completed_by_id(self, document_id: str) -> DocumentRecord | None:
        with self._db.session() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE document_id = ? AND status = ?",
                (document_id, DocumentStatus.COMPLETED.value),
            ).fetchone()
        return _row_to_document(row) if row else None

    def list_completed(self) -> list[DocumentRecord]:
        with self._db.session() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE status = ? ORDER BY last_opened_at DESC",
                (DocumentStatus.COMPLETED.value,),
            ).fetchall()
        return [_row_to_document(row) for row in rows]

    def touch(self, document_id: str) -> None:
        with self._db.session() as conn:
            conn.execute(
                "UPDATE documents SET last_opened_at = ? WHERE document_id = ?",
                (_now_iso(), document_id),
            )

    def delete(self, document_id: str) -> None:
        """Deletes metadata only; daily usage is deliberately untouched."""
        with self._db.session() as conn:
            conn.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))

    def delete_completed(self) -> int:
        """Remove completed-document metadata without changing daily usage."""
        with self._db.session() as conn:
            cursor = conn.execute(
                "DELETE FROM documents WHERE status = ?",
                (DocumentStatus.COMPLETED.value,),
            )
            return int(cursor.rowcount or 0)

    def count_completed(self) -> int:
        with self._db.session() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM documents WHERE status = ?",
                (DocumentStatus.COMPLETED.value,),
            ).fetchone()
        return int(row["n"]) if row else 0


class UsageRepository:
    """Daily quota counter. Rows survive deletes and restarts by design."""

    KEY = "main"

    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self) -> DailyUsage | None:
        with self._db.session() as conn:
            row = conn.execute(
                "SELECT day, count FROM daily_usage WHERE key_id = ?", (self.KEY,)
            ).fetchone()
        return DailyUsage(day=row["day"], count=int(row["count"])) if row else None

    def set(self, day: str, count: int) -> None:
        with self._db.session() as conn:
            conn.execute(
                "INSERT INTO daily_usage (key_id, day, count) VALUES (?, ?, ?) "
                "ON CONFLICT(key_id) DO UPDATE SET day = excluded.day, count = excluded.count",
                (self.KEY, day, count),
            )


class TranslationCacheRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, cache_key: str) -> str | None:
        with self._db.session() as conn:
            row = conn.execute(
                "SELECT translated FROM translation_cache WHERE cache_key = ?", (cache_key,)
            ).fetchone()
        return str(row["translated"]) if row else None

    def put(
        self, cache_key: str, provider: str, source: str, target: str,
        source_hash: str, translated: str,
    ) -> None:
        with self._db.session() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO translation_cache
                   (cache_key, provider, source, target, source_hash, translated, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cache_key, provider, source, target, source_hash, translated, _now_iso()),
            )

    def prune(self, keep_last: int = 50000) -> None:
        with self._db.session() as conn:
            conn.execute(
                """DELETE FROM translation_cache WHERE cache_key NOT IN (
                       SELECT cache_key FROM translation_cache
                       ORDER BY created_at DESC LIMIT ?)""",
                (keep_last,),
            )


class AppStateRepository:
    """Small key/value store (license state, flags)."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, key: str) -> str | None:
        with self._db.session() as conn:
            row = conn.execute(
                "SELECT value FROM app_state WHERE key = ?", (key,)
            ).fetchone()
        return str(row["value"]) if row else None

    def set(self, key: str, value: str) -> None:
        with self._db.session() as conn:
            conn.execute(
                "INSERT INTO app_state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )


def _row_to_document(row) -> DocumentRecord:
    return DocumentRecord(
        document_id=row["document_id"],
        original_filename=row["original_filename"],
        document_hash=row["document_hash"],
        source_language=row["source_language"],
        target_language=row["target_language"],
        page_count=int(row["page_count"]),
        created_at=row["created_at"],
        last_opened_at=row["last_opened_at"],
        storage_path=row["storage_path"],
        status=row["status"],
        encryption_version=int(row["encryption_version"]),
        cache_key=row["cache_key"],
    )
