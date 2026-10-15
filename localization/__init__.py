"""Localization: JSON string tables with fallback to the key itself."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_LANGUAGE = "tr"

_instance: "I18n | None" = None


class I18n:
    def __init__(self, language_dir: Path, language: str = "") -> None:
        self._dir = language_dir
        self._language = ""
        self._strings: dict[str, str] = {}
        self._fallback: dict[str, str] = {}
        self.set_language(language or _DEFAULT_LANGUAGE)

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, code: str) -> None:
        if not self._fallback:
            self._fallback = self._load(_DEFAULT_LANGUAGE)
        self._language = code
        self._strings = self._load(code) if code != _DEFAULT_LANGUAGE else dict(self._fallback)
        if code != _DEFAULT_LANGUAGE and not self._strings:
            logger.warning("no strings for language %s, using fallback", code)
            self._strings = dict(self._fallback)

    def t(self, key: str, **kwargs: object) -> str:
        text = self._strings.get(key) or self._fallback.get(key) or key
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError):
                logger.debug("i18n placeholder mismatch for %s", key)
        return text

    def _load(self, code: str) -> dict[str, str]:
        path = self._dir / f"{code}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except FileNotFoundError:
            logger.warning("language file missing: %s", path)
            return {}
        except (OSError, json.JSONDecodeError):
            logger.exception("failed to load language file %s", path)
            return {}


def init_i18n(language_dir: Path, language: str) -> I18n:
    global _instance
    _instance = I18n(language_dir, language)
    return _instance


def get_i18n() -> I18n:
    global _instance
    if _instance is None:
        _instance = I18n(Path(__file__).parent, _DEFAULT_LANGUAGE)
    return _instance


def tr(key: str, **kwargs: object) -> str:
    """Shortcut used across the UI."""
    return get_i18n().t(key, **kwargs)
