"""Translation progress UI: background thread, live progress, Durdur."""
from __future__ import annotations

import logging

from PyQt6.QtCore import QThread, Qt
from PyQt6.QtWidgets import QDialog, QLabel, QProgressBar, QPushButton, QVBoxLayout

from localization import tr
from workers.translation_worker import TranslationJob, TranslationWorker

logger = logging.getLogger(__name__)


class TranslationDialog(QDialog):
    """Owns the worker thread; closes with a machine-readable outcome."""

    def __init__(self, services, job: TranslationJob, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("root")
        self.setWindowTitle("ParaLate")
        self.setMinimumWidth(460)
        self.setModal(True)

        self.document_id: str = ""
        self.outcome = ""            # "ok" | "failed" | "cancelled"
        self.error_code = ""
        self.error_params: tuple[str, str] = ("", "")

        self._thread = QThread(self)
        self._worker = TranslationWorker(
            paths=services.paths,
            config=services.config,
            db=services.db,
            documents=services.documents,
            quota=services.quota,
            store=services.store,
            network=services.network,
            job=job,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(12)

        self._title = QLabel(tr("progress.title"))
        self._title.setObjectName("section")
        self._title.setWordWrap(True)
        layout.addWidget(self._title)

        self._filename = QLabel(job.original_filename)
        self._filename.setObjectName("dim")
        self._filename.setWordWrap(True)
        layout.addWidget(self._filename)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        layout.addWidget(self._bar)

        self._page_label = QLabel(tr("progress.page", page=0, total=0))
        self._page_label.setObjectName("dim")
        layout.addWidget(self._page_label)

        self._status = QLabel(tr("status_hashing"))
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._info = QLabel("")
        self._info.setObjectName("dim")
        self._info.setWordWrap(True)
        self._info.hide()
        layout.addWidget(self._info)

        self._cancel = QPushButton(tr("progress.stop"))
        self._cancel.clicked.connect(self._on_cancel)
        layout.addWidget(self._cancel)

        self._worker.status_changed.connect(self._on_status)
        self._worker.progress.connect(self._on_progress)
        self._worker.info.connect(self._on_info)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        self._thread.start()
        self.exec()

    def _shutdown(self) -> None:
        if self._worker is not None:
            try:
                self._worker.finished_ok.disconnect()
                self._worker.failed.disconnect()
                self._worker.cancelled.disconnect()
            except TypeError:
                pass
        self._thread.quit()
        self._thread.wait(3000)

    # ------------------------------------------------------------------ #
    def _on_cancel(self) -> None:
        self._cancel.setEnabled(False)
        self._status.setText(tr("status_cancelling"))
        self._worker.request_cancel()

    def _on_status(self, key: str) -> None:
        self._status.setText(tr(key))

    def _on_progress(self, percent: int, page: int, total: int) -> None:
        self._bar.setValue(percent)
        self._page_label.setText(tr("progress.page", page=page, total=total))

    def _on_info(self, key: str, p1: str, p2: str) -> None:
        if key == "info_fallback":
            self._info.setText(tr(key, first=p1, second=p2))
            self._info.show()

    def _on_finished(self, document_id: str, kind: str) -> None:
        self.document_id = document_id
        self.outcome = "ok" if kind == "new" else "reused"
        self._bar.setValue(100)
        self._finish()

    def _on_failed(self, code: str, p1: str, p2: str) -> None:
        self.outcome = "failed"
        self.error_code = code
        self.error_params = (p1, p2)
        self._finish()

    def _on_cancelled(self) -> None:
        self.outcome = "cancelled"
        self._finish()

    def _finish(self) -> None:
        self._shutdown()
        self.done(QDialog.DialogCode.Accepted if self.outcome == "ok" else QDialog.DialogCode.Rejected)

    # ------------------------------------------------------------------ #
    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._thread.isRunning():
            event.ignore()
            self._on_cancel()
            return
        super().closeEvent(event)

    def reject(self) -> None:
        if self._thread.isRunning():
            self._on_cancel()
            return
        super().reject()
