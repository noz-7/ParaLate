"""SQLite access. Every operation opens a short-lived connection so the
translation worker thread and the UI thread never share a connection."""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    document_id       TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    document_hash     TEXT NOT NULL,
    source_language   TEXT NOT NULL,
    target_language   TEXT NOT NULL,
    page_count        INTEGER NOT NULL,
    created_at        TEXT NOT NULL,
    last_opened_at    TEXT NOT NULL,
    storage_path      TEXT NOT NULL,
    status            TEXT NOT NULL,
    encryption_version INTEGER NOT NULL,
    cache_key         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_cache
    ON documents(document_hash, source_language, target_language);

CREATE TABLE IF NOT EXISTS daily_usage (
    key_id TEXT PRIMARY KEY,
    day    TEXT NOT NULL,
    count  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS translation_cache (
    cache_key   TEXT PRIMARY KEY,
    provider    TEXT NOT NULL,
    source      TEXT NOT NULL,
    target      TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    translated  TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class DatabaseError(Exception):
    """Raised when persistence fails; carries a user-safe message code."""

    def __init__(self, code: str = "database") -> None:
        super().__init__(code)
        self.code = code


class Database:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection, commit on success, always close."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._path), timeout=10.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=10000")
            conn.execute("PRAGMA foreign_keys=ON")
        except sqlite3.Error as exc:
            raise DatabaseError("database") from exc
        try:
            yield conn
            conn.commit()
        except DatabaseError:
            conn.rollback()
            raise
        except sqlite3.Error as exc:
            conn.rollback()
            logger.exception("database operation failed")
            raise DatabaseError("database") from exc
        finally:
            conn.close()

    def initialize(self) -> None:
        try:
            with self.session() as conn:
                conn.executescript(_SCHEMA)
        except DatabaseError:
            raise
        except sqlite3.Error as exc:
            raise DatabaseError("database") from exc

    def close(self) -> None:
        """Connections are per-operation; nothing persistent to close."""
