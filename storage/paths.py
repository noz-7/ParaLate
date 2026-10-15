"""Platform-aware application data paths (Windows AppData / XDG)."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from app.constants import APP_SLUG

ENV_DATA_DIR = "PARA_LATE_DATA_DIR"

_SUBDIRS = ("config", "database", "documents", "cache", "logs", "temp")


def default_root() -> Path:
    """Resolve the per-user data root for this platform."""
    override = os.environ.get(ENV_DATA_DIR)
    if override:
        return Path(override).expanduser()
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"
        return root / APP_SLUG
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / APP_SLUG.lower()


def safe_join(base: Path, *parts: str) -> Path:
    """Join under *base* and reject anything escaping it (path traversal)."""
    try:
        candidate = base.joinpath(*parts).resolve()
        base_resolved = base.resolve()
        if os.path.commonpath([str(candidate), str(base_resolved)]) != str(base_resolved):
            raise ValueError("path escapes base directory")
    except ValueError as exc:
        raise ValueError("invalid path") from exc
    return candidate


@dataclass(frozen=True)
class AppPaths:
    root: Path

    @classmethod
    def default(cls) -> "AppPaths":
        return cls(root=default_root())

    @classmethod
    def at(cls, root: Path) -> "AppPaths":
        return cls(root=Path(root))

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def database_dir(self) -> Path:
        return self.root / "database"

    @property
    def documents_dir(self) -> Path:
        return self.root / "documents"

    @property
    def cache_dir(self) -> Path:
        return self.root / "cache"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def temp_dir(self) -> Path:
        return self.root / "temp"

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.json"

    @property
    def database_file(self) -> Path:
        return self.database_dir / "paralate.db"

    @property
    def log_file(self) -> Path:
        return self.logs_dir / "paralate.log"

    @property
    def master_key_file(self) -> Path:
        return self.config_dir / "master.key"

    def ensure(self) -> "AppPaths":
        for name in _SUBDIRS:
            (self.root / name).mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("posix"):
            self.root.chmod(0o700)
        return self
