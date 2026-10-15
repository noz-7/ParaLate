"""Opening PDFs from paths or bytes with user-safe error codes."""
from __future__ import annotations

import logging

import pymupdf

logger = logging.getLogger(__name__)


class PdfOpenError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def open_pdf_path(path: str) -> pymupdf.Document:
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        logger.warning("failed to open pdf %s: %s", path, exc)
        raise PdfOpenError("corrupt_pdf") from exc
    _check(doc, path)
    return doc


def open_pdf_bytes(data: bytes) -> pymupdf.Document:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        logger.warning("failed to open pdf bytes: %s", exc)
        raise PdfOpenError("corrupt_pdf") from exc
    _check(doc, "<memory>")
    return doc


def _check(doc: pymupdf.Document, label: str) -> None:
    if doc.is_encrypted and doc.needs_pass:
        doc.close()
        raise PdfOpenError("password_pdf")
    if doc.page_count == 0:
        doc.close()
        raise PdfOpenError("corrupt_pdf")
    if doc.needs_pass:
        doc.close()
        raise PdfOpenError("password_pdf")
