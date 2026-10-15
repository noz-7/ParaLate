"""Application bootstrap: startup order, services wiring, event loop."""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

from app.constants import APP_NAME, APP_VERSION, ORG_NAME
from app.config import Config
from app.network import NetworkStatus
from app.services import AppServices
from ads.manager import AdManager
from localization import init_i18n
from storage.database import Database
from storage.encrypted_document import EncryptedDocumentStore
from storage.paths import AppPaths
from storage.repository import AppStateRepository, DocumentRepository, UsageRepository

logger = logging.getLogger(__name__)

_SECRET_ENV_NAMES = (
    "GOOGLE_TRANSLATE_API_KEY",
    "MICROSOFT_TRANSLATOR_API_KEY",
    "LIBRETRANSLATE_API_KEY",
)


class RedactionFilter(logging.Filter):
    """Never let secret values reach the log file."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        for name in _SECRET_ENV_NAMES:
            value = os.environ.get(name, "")
            if value and len(value) >= 8 and value in message:
                message = message.replace(value, "***")
                record.msg = message
                record.args = ()
        return True


def _setup_logging(paths: AppPaths) -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if root.handlers:
        return
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    redaction = RedactionFilter()
    try:
        paths.logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            paths.log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        file_handler.addFilter(redaction)
        root.addHandler(file_handler)
    except OSError:
        logging.getLogger(__name__).warning("log file unavailable; console only")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(logging.WARNING)
    console.addFilter(redaction)
    root.addHandler(console)


def _localization_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "localization"
    return Path(__file__).resolve().parent.parent / "localization"


def _application_icon_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "assets" / "icon.png"
    return Path(__file__).resolve().parent.parent / "icon.png"


def _register_windows_ui_font() -> None:
    if sys.platform != "win32":
        return
    from PyQt6.QtGui import QFontDatabase

    font_path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeui.ttf"
    if font_path.is_file():
        QFontDatabase.addApplicationFont(str(font_path))


def _purge_temp(paths: AppPaths) -> None:
    try:
        for entry in paths.temp_dir.iterdir():
            if entry.is_file():
                entry.unlink(missing_ok=True)
    except OSError:
        logger.debug("temp purge failed", exc_info=True)


def build_services(paths: AppPaths) -> AppServices:
    from security.encryption import DocumentCipher
    from licensing.license_manager import LicenseManager
    from licensing.limits import QuotaService

    config = Config(paths.config_file)
    db = Database(paths.database_file)
    db.initialize()

    cipher = DocumentCipher.load_or_create(paths)
    store = EncryptedDocumentStore(paths.documents_dir, cipher)
    state = AppStateRepository(db)
    documents = DocumentRepository(db)
    usage = UsageRepository(db)
    try:
        documents.cleanup_incomplete()
    except Exception:
        logger.warning("partial-document cleanup failed")
    quota = QuotaService(usage)
    license_manager = LicenseManager(state)
    ad_manager = AdManager(lambda: license_manager.is_premium)
    network = NetworkStatus()
    return AppServices(
        paths=paths,
        config=config,
        db=db,
        documents=documents,
        usage=usage,
        state=state,
        quota=quota,
        cipher=cipher,
        store=store,
        network=network,
        license=license_manager,
        ads=ad_manager,
    )


def run(argv: list[str]) -> int:
    paths = AppPaths.default().ensure()
    _setup_logging(paths)
    logger.info("%s %s starting", APP_NAME, APP_VERSION)

    services = build_services(paths)
    _purge_temp(paths)

    from PyQt6.QtGui import QFont, QIcon
    from PyQt6.QtWidgets import QApplication, QDialog

    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "NOZ7.ParaLate"
        )
    from ui.language_dialog import FirstRunDialog
    from ui.style import APP_QSS
    from ui.home_window import HomeWindow

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(QIcon(str(_application_icon_path())))
    _register_windows_ui_font()
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(APP_QSS)

    loc_dir = _localization_dir()
    saved_language = str(services.config.get("ui_language", "") or "tr")
    init_i18n(loc_dir, saved_language)

    if not services.config.get("first_run_completed", False):
        first_run = FirstRunDialog()
        if first_run.exec() != QDialog.DialogCode.Accepted:
            logger.info("first run dismissed; exiting")
            return 0
        services.config.set("ui_language", first_run.language)
        services.config.set("first_run_completed", True)
        init_i18n(loc_dir, first_run.language)

    from localization import get_i18n

    if get_i18n().language != saved_language:
        get_i18n().set_language(str(services.config.get("ui_language", "tr")))

    home = HomeWindow(services)
    home.show()

    exit_code = app.exec()

    logger.info("%s shutting down", APP_NAME)
    try:
        _purge_temp(paths)
        services.db.close()
    except Exception:
        logger.debug("shutdown cleanup failed", exc_info=True)
    return exit_code
