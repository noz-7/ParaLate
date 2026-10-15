"""API key lookup: environment/.env first, OS keyring as fallback.

Keys are never logged and never written into config.json.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from app.constants import KEYRING_SERVICE

logger = logging.getLogger(__name__)

_ENV_LOADED = False


def load_env(env_file: Path | None = None) -> None:
    """Load .env into the process environment (no overwrite of real env)."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    try:
        from dotenv import load_dotenv

        target = env_file if env_file else Path.cwd() / ".env"
        if target.exists():
            load_dotenv(target, override=False)
    except Exception:
        logger.debug("dotenv load skipped", exc_info=True)
    _ENV_LOADED = True


def get_secret(name: str) -> str | None:
    """Return a secret from the environment or the OS keyring, else None."""
    value = os.environ.get(name, "").strip()
    if value:
        return value
    try:
        import keyring

        stored = keyring.get_password(KEYRING_SERVICE, name)
        if stored:
            return stored
    except Exception:
        logger.debug("keyring read failed for %s", name, exc_info=True)
    return None


def set_secret(name: str, value: str) -> bool:
    """Persist a secret into the OS keyring (production path)."""
    try:
        import keyring

        keyring.set_password(KEYRING_SERVICE, name, value)
        return True
    except Exception:
        logger.warning("keyring write failed for %s", name, exc_info=True)
        return False


def mask_secret(value: str) -> str:
    """Safe representation for diagnostics: never the raw key."""
    if not value:
        return ""
    return f"{value[:4]}{'*' * 6}"
