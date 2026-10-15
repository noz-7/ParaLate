"""Offline license activation on a worker thread."""
from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal

from licensing.base import LicenseError
from licensing.license_manager import LicenseManager

logger = logging.getLogger(__name__)


class LicenseActivationWorker(QObject):
    finished = pyqtSignal(object, str)  # LicenseInfo or None, error code

    def __init__(self, manager: LicenseManager, code: str) -> None:
        super().__init__()
        self._manager = manager
        self._code = code

    def run(self) -> None:
        try:
            self.finished.emit(self._manager.activate(self._code), "")
        except LicenseError as error:
            self.finished.emit(None, error.code)
        except Exception:
            logger.exception("unexpected offline license activation failure")
            self.finished.emit(None, "internal")
