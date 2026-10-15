"""Interleave engine: original and translated pages into ONE document.

Physical order: Original1, Translation1, Original2, Translation2, ...
The viewer pairs pages (2k-1, 2k) as [Original | Translation].
"""
from __future__ import annotations

import logging

import pymupdf

logger = logging.getLogger(__name__)


class InterleaveError(Exception):
    def __init__(self, code: str = "interleave") -> None:
        super().__init__(code)
        self.code = code


def build_interleaved(
    orig_doc: pymupdf.Document, trans_doc: pymupdf.Document
) -> pymupdf.Document:
    if orig_doc.page_count != trans_doc.page_count:
        raise InterleaveError("page_mismatch")
    out = pymupdf.open()
    try:
        for index in range(orig_doc.page_count):
            out.insert_pdf(orig_doc, from_page=index, to_page=index)
            out.insert_pdf(trans_doc, from_page=index, to_page=index)
    except Exception as exc:
        out.close()
        logger.exception("interleave failed")
        raise InterleaveError("interleave") from exc
    return out


def is_interleaved(page_count: int) -> bool:
    return page_count > 0 and page_count % 2 == 0


def spread_of_page(page_number: int) -> int:
    """0-based physical page index -> 0-based spread index."""
    return page_number // 2
