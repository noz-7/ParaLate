"""JSON configuration with defaults, atomic writes and dotted keys."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from app.constants import ALLOW_PROVIDER_FALLBACK, DEFAULT_TRANSLATION_PROVIDER

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict[str, Any] = {
    "ui_language": "",
    "theme": "dark",
    "first_run_completed": False,
    "translation_provider": DEFAULT_TRANSLATION_PROVIDER,
    "allow_provider_fallback": ALLOW_PROVIDER_FALLBACK,
    "viewer": {
        "zoom": 1.0,
        "fullscreen": False,
    },
}


class Config:
    """Loads config.json, creating it with defaults on first use."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        self._data = _deep_merge({}, DEFAULT_CONFIG)
        if self._path.exists():
            try:
                loaded = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._data = _deep_merge(self._data, loaded)
                else:
                    logger.warning("config root is not an object, using defaults")
            except (OSError, json.JSONDecodeError):
                logger.exception("failed to read config, using defaults")
        else:
            self.save()

    def get(self, dotted_key: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted_key: str, value: Any) -> None:
        parts = dotted_key.split(".")
        node = self._data
        for part in parts[:-1]:
            child = node.get(part)
            if not isinstance(child, dict):
                child = {}
                node[part] = child
            node = child
        node[parts[-1]] = value
        self.save()

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(self._data, indent=2, ensure_ascii=False)
            fd, tmp_name = tempfile.mkstemp(
                dir=str(self._path.parent), prefix=".config-", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                os.replace(tmp_name, self._path)
            except BaseException:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
        except OSError:
            logger.exception("failed to save config")


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base
