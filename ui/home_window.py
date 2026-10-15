"""Welcome/Home screen: select a PDF, open history, license state, ads."""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.constants import FREE_PAGE_LIMIT
from localization import tr
from pdf.loader import PdfOpenError, open_pdf_path
from ui.ad_banner import AdBanner
from ui.dialogs.premium_dialog import PremiumDialog
from ui.dialogs.premium_promo import PremiumPromoDialog
from ui.history_widget import HistoryWidget
from ui.language_dialog import LanguageDialog
from ui.pdf_viewer import ViewerWindow
from ui.translation_window import TranslationDialog
from workers.pdf_worker import LoadDocumentWorker
from workers.translation_worker import TranslationJob

logger = logging.getLogger(__name__)
_PREMIUM_PROMO_INTERVAL_MS = 7 * 60 * 1000


class HomeWindow(QMainWindow):
    def __init__(self, services) -> None:
        super().__init__()
        self._services = services
        self._viewers: list[ViewerWindow] = []  # keep references to viewer windows
        self._load_thread: QThread | None = None
        self._load_worker: LoadDocumentWorker | None = None
        self._promotion: PremiumPromoDialog | None = None
        self._promotion_viewer: ViewerWindow | None = None
        self._promo_seen: set[int] = set()
        self._promo_due = False
        self._closing = False

        self.setObjectName("root")
        self.setWindowTitle("ParaLate")
        self.resize(940, 720)

        # Tab widget as central widget
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._promo_timer = QTimer(self)
        self._promo_timer.setSingleShot(True)
        self._promo_timer.setInterval(_PREMIUM_PROMO_INTERVAL_MS)
        self._promo_timer.timeout.connect(self._on_promo_timeout)
        self.setCentralWidget(self._tabs)

        # Keep home and history as permanent tabs; viewer tabs are added after them.
        home_page = self._create_home_page()
        self._tabs.addTab(home_page, tr("home.tab_title"))
        self._history = HistoryWidget()
        self._history.open_requested.connect(self._open_document)
        self._history.delete_requested.connect(self._delete_document)
        self._history.clear_requested.connect(self._clear_history)
        self._tabs.addTab(self._history, tr("history.tab_title"))

        self._refresh_all()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _create_home_page(self) -> QWidget:
        """Create the home page widget (welcome/select/ads)."""
        page = QWidget()
        page.setObjectName("home_page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 28, 36, 24)
        layout.setSpacing(14)

        # --- header --- #
        header = QHBoxLayout()
        brand_box = QVBoxLayout()
        brand_box.setSpacing(2)
        title = QLabel("ParaLate")
        title.setObjectName("title")
        brand_box.addWidget(title)
        subtitle = QLabel(tr("welcome.subtitle"))
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        brand_box.addWidget(subtitle)
        header.addLayout(brand_box, 1)

        self._badge = QLabel("")
        header.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignTop)

        self._premium_button = QPushButton(tr("home.premium_button"))
        self._premium_button.clicked.connect(self._show_premium)
        header.addWidget(self._premium_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        # --- primary action --- #
        select = QPushButton(tr("welcome.select_button"))
        select.setObjectName("primary")
        select.setCursor(Qt.CursorShape.PointingHandCursor)
        select.clicked.connect(self._select_pdf)
        select.setFixedHeight(52)
        layout.addWidget(select)

        self._hint = QLabel(tr("home.select_hint", limit=FREE_PAGE_LIMIT))
        self._hint.setObjectName("dim")
        layout.addWidget(self._hint)

        # --- ad strip (reserved area, never over content) --- #
        self._banner = AdBanner(self._services.ads, "home")
        layout.addWidget(self._banner)

        return page

    # ------------------------------------------------------------------ #
    def _refresh_all(self) -> None:
        self._refresh_badge()
        self._refresh_history()
        self._banner.refresh()

    def _refresh_badge(self) -> None:
        premium = self._services.license.is_premium
        self._badge.setText("👑 PREMIUM" if premium else "FREE")
        self._badge.setObjectName("badgePremium" if premium else "badge")
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)
        self._premium_button.setVisible(not premium)
        if premium and hasattr(self, "_promo_timer"):
            self._promo_timer.stop()
            self._promo_due = False

    def _refresh_history(self) -> None:
        try:
            records = self._services.documents.list_completed()
        except Exception:
            logger.exception("history load failed")
            self._history.set_documents([])
            self._show_error("database")
            return
        self._history.set_documents(records)

    # ------------------------------------------------------------------ #
    # select + translate flow
    # ------------------------------------------------------------------ #
    def _select_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("home.select_title"), "", tr("home.pdf_filter")
        )
        if not path:
            return

        # Cheap validation + FREE page-limit pre-check before any dialog.
        try:
            doc = open_pdf_path(path)
            page_count = doc.page_count
            doc.close()
        except PdfOpenError as error:
            self._show_error(error.code)
            return
        if (
            not self._services.license.allows("unlimited_pages")
            and page_count > FREE_PAGE_LIMIT
        ):
            self._show_error("page_limit", str(page_count), str(FREE_PAGE_LIMIT))
            return
        if not self._services.network.online:
            self._show_error("offline")
            return

        language = LanguageDialog(parent=self)
        if language.exec() != LanguageDialog.DialogCode.Accepted:
            return

        filename = path.replace("\\", "/").rsplit("/", 1)[-1]
        job = TranslationJob(
            file_path=path,
            original_filename=filename,
            source_language=language.source_language,
            target_language=language.target_language,
            is_premium=self._services.license.is_premium,
        )
        progress = TranslationDialog(self._services, job, self)
        progress.start()

        self._refresh_all()
        if progress.outcome == "ok":
            self._open_document(progress.document_id)
        elif progress.outcome == "failed":
            self._show_error(progress.error_code, *progress.error_params)

    # ------------------------------------------------------------------ #
    # history actions
    # ------------------------------------------------------------------ #
    def _open_document(self, document_id: str) -> None:
        for index in range(2, self._tabs.count()):
            viewer = self._tabs.widget(index)
            if isinstance(viewer, ViewerWindow) and viewer._document_id == document_id:
                self._tabs.setCurrentIndex(index)
                return
        if self._load_thread is not None and self._load_thread.isRunning():
            return  # a document is already being loaded
        record = self._services.documents.find_completed_by_id(document_id)
        if record is None:
            self._show_error("missing_document")
            self._refresh_history()
            return
        if (
            not self._services.license.allows("offline_open")
            and not self._services.network.online
        ):
            self._show_error("offline")
            return

        try:
            self._services.documents.touch(document_id)
        except Exception:
            logger.warning("touch failed")

        self._load_thread = QThread(self)
        self._load_worker = LoadDocumentWorker(
            self._services.store, document_id, record.storage_path
        )
        self._load_worker.moveToThread(self._load_thread)
        self._load_thread.started.connect(self._load_worker.run)
        self._load_worker.loaded.connect(self._on_document_loaded)
        self._load_worker.failed.connect(self._on_document_load_failed)
        self._load_worker.loaded.connect(self._load_thread.quit)
        self._load_worker.failed.connect(self._load_thread.quit)
        self._load_thread.finished.connect(self._load_worker.deleteLater)
        self._load_thread.start()

    def _on_document_loaded(self, document_id: str, data: bytes) -> None:
        record = self._services.documents.find_completed_by_id(document_id)
        title = record.original_filename if record else "ParaLate"
        try:
            viewer = ViewerWindow(self._services, document_id, title, data)
        except PdfOpenError as error:
            self._show_error(error.code)
            return
        self._viewers.append(viewer)
        # Add viewer as a new tab
        tab_index = self._tabs.addTab(viewer, f"{tr('viewer.tab_prefix')} {title}")
        self._tabs.setCurrentIndex(tab_index)
        # Connect tab close event? Already handled by tabCloseRequested
        viewer.destroyed.connect(lambda *_: self._prune_viewers())

    def _on_document_load_failed(self, document_id: str, code: str) -> None:
        self._show_error(code)

    def _prune_viewers(self) -> None:
        self._viewers = [v for v in self._viewers if v is not None]

    def _on_tab_changed(self, index: int) -> None:
        widget = self._tabs.widget(index)
        if not isinstance(widget, ViewerWindow):
            if not any(isinstance(self._tabs.widget(i), ViewerWindow)
                       for i in range(2, self._tabs.count())):
                self._promo_timer.stop()
                self._promo_due = False
            return
        if self._closing or self._services.license.is_premium:
            self._promo_timer.stop()
            return
        identity = id(widget)
        if identity not in self._promo_seen:
            self._promo_seen.add(identity)
            self._show_premium_promo(widget)
        elif self._promo_due:
            self._show_premium_promo(widget)

    def _show_premium_promo(self, viewer: ViewerWindow) -> None:
        if self._services.license.is_premium:
            return
        if self._promotion is not None:
            self._promo_due = True
            return
        self._promo_timer.stop()
        self._promo_due = False
        dialog = PremiumPromoDialog(self._services, viewer)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.finished.connect(self._on_premium_promo_finished)
        self._promotion = dialog
        self._promotion_viewer = viewer
        viewer.set_premium_promo_blocked(True)
        dialog.open()

    def _on_premium_promo_finished(self, _result: int) -> None:
        viewer = self._promotion_viewer
        self._promotion = None
        self._promotion_viewer = None
        if viewer is not None:
            try:
                viewer.set_premium_promo_blocked(False)
            except RuntimeError:
                logger.debug("promo closed after viewer teardown")
        if self._closing:
            return
        self._refresh_badge()
        if self._services.license.is_premium:
            self._promo_timer.stop()
            self._promo_due = False
            return
        has_viewer = any(
            isinstance(self._tabs.widget(i), ViewerWindow)
            for i in range(2, self._tabs.count())
        )
        if has_viewer:
            self._promo_timer.start()

    def _on_promo_timeout(self) -> None:
        widget = self._tabs.currentWidget()
        if isinstance(widget, ViewerWindow):
            self._show_premium_promo(widget)
        else:
            self._promo_due = True

    def _delete_document(self, document_id: str) -> None:
        confirm = QMessageBox.question(
            self,
            tr("history.delete_title"),
            tr("history.delete_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        record = self._services.documents.find_completed_by_id(document_id)
        if record is not None:
            self._services.store.delete(record.storage_path)
        try:
            self._services.documents.delete(document_id)
        except Exception:
            logger.exception("delete failed")
            self._show_error("database")
        # NOTE: deleting never refunds the daily quota (by design).
        self._refresh_history()

    def _clear_history(self) -> None:
        confirm = QMessageBox.question(
            self,
            tr("history.clear_title"),
            tr("history.clear_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            records = self._services.documents.list_completed()
            self._services.documents.delete_completed()
        except Exception:
            logger.exception("history clear failed")
            self._show_error("database")
            return
        for record in records:
            self._services.store.delete(record.storage_path)
        self._refresh_history()

    # ------------------------------------------------------------------ #
    def _show_premium(self) -> None:
        dialog = PremiumDialog(self._services.license, self)
        dialog.exec()
        self._refresh_all()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._closing = True
        self._promo_timer.stop()
        if self._promotion is not None:
            self._promotion.close()
            self._promotion = None
        # Never destroy a running QThread (would abort the process).
        if self._load_thread is not None and self._load_thread.isRunning():
            self._load_thread.quit()
            self._load_thread.wait(3000)
        super().closeEvent(event)

    def _show_error(self, code: str, p1: str = "", p2: str = "") -> None:
        title = tr("error.title")
        key = f"error.{code}"
        params = {}
        if p1:
            params["p1"] = p1
        if p2:
            params["p2"] = p2
        message = tr(key, **params)
        if message == key:
            logger.warning("unmapped error code: %s", code)
            message = tr("error.internal")
        QMessageBox.critical(self, title, message)

    def _close_tab(self, index: int) -> None:
        if index < 2:
            # Home and history are permanent tabs.
            return
        widget = self._tabs.widget(index)
        if isinstance(widget, ViewerWindow):
            self._promo_seen.discard(id(widget))
        self._tabs.removeTab(index)
        widget.deleteLater()
        # Also remove from _viewers list if present
        if isinstance(widget, ViewerWindow) and widget in self._viewers:
            self._viewers.remove(widget)