"""Premium benefits, offline activation, and Telegram contact."""
from __future__ import annotations

import logging

from PyQt6.QtCore import QByteArray, Qt, QThread, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from licensing.license_manager import LicenseManager
from localization import tr
from workers.license_worker import LicenseActivationWorker

logger = logging.getLogger(__name__)
_TELEGRAM_URL = "https://t.me/NOZ_7_T"
_TELEGRAM_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
<circle cx="12" cy="12" r="12" fill="#26A5E4"/>
<path fill="#fff" d="M18.8 6.2 16.5 18c-.2.8-.7 1-1.4.6l-3.8-2.8-1.9 1.8c-.2.2-.4.4-.8.4l.3-3.9 7.1-6.4c.3-.3-.1-.4-.5-.2l-8.8 5.5-3.8-1.2c-.8-.3-.8-.8.2-1.2L18 5.4c.7-.2 1.1.2.8.8z"/>
</svg>"""


class PremiumDialog(QDialog):
    def __init__(self, license_manager: LicenseManager, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("root")
        self.setWindowTitle("ParaLate")
        self.setMinimumWidth(440)
        self._license = license_manager
        self._activation_thread: QThread | None = None
        self._activation_worker: LicenseActivationWorker | None = None
        self._wait_dialog: QDialog | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(12)

        crown = QLabel("👑")
        crown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        crown.setStyleSheet("font-size: 34pt; background: transparent;")
        layout.addWidget(crown)

        heading = QLabel(tr("premium.heading"))
        heading.setObjectName("section")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)

        body = QLabel(tr("premium.body"))
        body.setWordWrap(True)
        body.setObjectName("dim")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(body)

        self._entitlement = QLabel("")
        self._entitlement.setObjectName("dim")
        self._entitlement.setWordWrap(True)
        self._entitlement.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._entitlement)
        self._update_entitlement()

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText(tr("premium.key_placeholder"))
        self._key_input.setMaxLength(160)
        self._key_input.setClearButtonEnabled(True)
        layout.addWidget(self._key_input)

        self._status = QLabel("")
        self._status.setObjectName("dim")
        self._status.setWordWrap(True)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        self._activate = QPushButton(tr("premium.activate"))
        self._activate.clicked.connect(self._on_activate)
        layout.addWidget(self._activate)

        contact = QHBoxLayout()
        contact.addStretch(1)
        icon = QSvgWidget()
        icon.load(QByteArray(_TELEGRAM_SVG))
        icon.setFixedSize(22, 22)
        contact.addWidget(icon)
        link = QLabel(f'<a href="{_TELEGRAM_URL}">t.me/NOZ_7_T</a>')
        link.setOpenExternalLinks(False)
        link.linkActivated.connect(self._open_contact)
        contact.addWidget(link)
        contact.addStretch(1)
        layout.addLayout(contact)

        self._contact_button = QPushButton(tr("premium.contact"))
        self._contact_button.setObjectName("primary")
        self._contact_button.clicked.connect(lambda: self._open_contact(_TELEGRAM_URL))
        layout.addWidget(self._contact_button)

        close = QPushButton(tr("common.close"))
        close.clicked.connect(self.reject)
        layout.addWidget(close)

    def _update_entitlement(self) -> None:
        info = self._license.info
        if self._license.is_premium:
            expiry = info.expires_at
            self._entitlement.setText(
                tr("premium.active_until", date=expiry)
            )
            self._key_input.setPlaceholderText(tr("premium.key_placeholder"))
        elif self._license.is_not_yet_valid:
            self._entitlement.setText(
                tr("premium.starts_on", date=info.starts_at)
            )
        elif self._license.is_expired:
            self._entitlement.setText(
                tr("premium.expired", date=info.expires_at)
            )
        else:
            self._entitlement.setText("")

    def _on_activate(self) -> None:
        if self._activation_thread is not None:
            return
        code = self._key_input.text()
        if not code.strip():
            self._status.setText(tr("premium.key_empty"))
            return

        wait = QDialog(self)
        wait.setWindowTitle("ParaLate")
        wait.setModal(True)
        wait.setWindowModality(Qt.WindowModality.WindowModal)
        wait.setFixedWidth(300)
        wait_layout = QVBoxLayout(wait)
        wait_layout.addWidget(QLabel(tr("premium.waiting")))
        self._wait_dialog = wait

        thread = QThread(self)
        worker = LicenseActivationWorker(self._license, code)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_activation_finished)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_activation_thread_finished)
        self._activation_thread = thread
        self._activation_worker = worker
        self._activate.setEnabled(False)
        wait.open()
        thread.start()

    def _on_activation_finished(self, info, error_code: str) -> None:
        if self._wait_dialog is not None:
            self._wait_dialog.accept()
            self._wait_dialog.deleteLater()
            self._wait_dialog = None
        if error_code:
            if error_code == "internal":
                message = tr("premium.error.activation")
            else:
                message = tr("premium.error.invalid_activation")
            QMessageBox.warning(self, tr("error.title"), message)
            return
        self._status.setText(tr("premium.success"))
        self._update_entitlement()
        QMessageBox.information(
            self,
            tr("premium.heading"),
            tr(
                "premium.success_until",
                start=info.starts_at,
                end=info.expires_at,
            ),
        )

    def _on_activation_thread_finished(self) -> None:
        self._activation_thread = None
        self._activation_worker = None
        self._activate.setEnabled(True)

    def _open_contact(self, url: str) -> None:
        if url != _TELEGRAM_URL:
            logger.warning("refused unexpected premium contact URL")
            return
        try:
            if not QDesktopServices.openUrl(QUrl(_TELEGRAM_URL)):
                logger.error("could not open configured Telegram contact URL")
                self._status.setText(tr("premium.contact_failed"))
        except Exception:
            logger.exception("failed to open Telegram contact")
            self._status.setText(tr("premium.contact_failed"))

    def closeEvent(self, event) -> None:  # noqa: N802
        thread = self._activation_thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(3000)
        super().closeEvent(event)
