"""Document metadata and serialization helpers."""
from __future__ import annotations

import logging

import pymupdf

from app.constants import APP_NAME, APP_VERSION

logger = logging.getLogger(__name__)


def apply_metadata(
    doc: pymupdf.Document, original_filename: str, source: str, target: str
) -> None:
    try:
        meta = dict(doc.metadata or {})
        meta["title"] = original_filename
        meta["producer"] = f"{APP_NAME} {APP_VERSION}"
        meta["creator"] = APP_NAME
        meta["subject"] = f"{source} -> {target}"
        doc.set_metadata(meta)
    except Exception:
        logger.debug("failed to set metadata", exc_info=True)


def serialize(doc: pymupdf.Document) -> bytes:
    """Compact PDF bytes; font subsetting attempted but never required."""
    try:
        doc.subset_fonts()
    except Exception:
        logger.debug("font subsetting skipped", exc_info=True)
    return doc.tobytes(garbage=4, deflate=True)
