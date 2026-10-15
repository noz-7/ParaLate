"""SHA-256 hashing helpers. Identity of a PDF is its byte content."""
from __future__ import annotations

import hashlib

_CHUNK = 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    """Hash a file in chunks so large PDFs never load fully into memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def document_cache_key(document_hash: str, source_language: str, target_language: str) -> str:
    """Cache key: same bytes + same language pair == same document."""
    return f"{document_hash.lower()}|{source_language.lower()}|{target_language.lower()}"


def translation_cache_key(provider: str, source: str, target: str, text: str) -> str:
    """Key for the translation cache (provider participates, per spec)."""
    raw = f"{provider.lower()}|{source.lower()}|{target.lower()}|{text}"
    return sha256_text(raw)
