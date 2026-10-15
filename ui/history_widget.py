"""Home screen history: previously translated documents."""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from localization import tr
from storage.models import DocumentRecord

_LANGUAGE_NAMES = {
    "auto": "Auto",
    "tr": "Türkçe",
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "it": "Italiano",
    "pt": "Português",
    "ru": "Русский",
    "ja": "日本語",
    "zh-CN": "中文",
    "ko": "한국어",
    "ar": "العربية",
    "hi": "हिन्दी",
    "nl": "Nederlands",
    "pl": "Polski",
    "sv": "Svenska",
}


def _language_name(code: str) -> str:
    return _LANGUAGE_NAMES.get(code, code)


def _format_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        return iso[:10]


class HistoryWidget(QWidget):
    open_requested = pyqtSignal(str)     # document_id
    delete_requested = pyqtSignal(str)   # document_id
    clear_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        heading = QLabel(tr("history.title"))
        heading.setObjectName("section")
        header.addWidget(heading, 1)
        self._clear_button = QPushButton(tr("history.clear"))
        self._clear_button.clicked.connect(lambda: self.clear_requested.emit())
        header.addWidget(self._clear_button)
        layout.addLayout(header)

        self._list = QListWidget()
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._context_menu)
        self._list.itemDoubleClicked.connect(self._open_item)
        self._list.setMinimumHeight(180)
        layout.addWidget(self._list)

        self._empty = QLabel(tr("history.empty"))
        self._empty.setObjectName("dim")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty)

        self._records: dict[str, DocumentRecord] = {}

    def set_documents(self, records: list[DocumentRecord]) -> None:
        self._list.clear()
        self._records.clear()
        for record in records:
            self._records[record.document_id] = record
            item = QListWidgetItem(self._label_for(record))
            item.setData(Qt.ItemDataRole.UserRole, record.document_id)
            item.setToolTip(record.original_filename)
            self._list.addItem(item)
        self._empty.setVisible(not records)
        self._list.setVisible(bool(records))
        self._clear_button.setEnabled(bool(records))

    @staticmethod
    def _label_for(record: DocumentRecord) -> str:
        return (
            f"{record.original_filename}\n"
            f"{_language_name(record.source_language)} → {_language_name(record.target_language)}"
            f"   ·   {tr('history.pages', count=record.page_count)}"
            f"   ·   {tr('history.last_used', date=_format_date(record.last_opened_at))}"
        )

    def _context_menu(self, pos) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        document_id = str(item.data(Qt.ItemDataRole.UserRole))
        menu = QMenu(self)
        open_action = menu.addAction(tr("history.open"))
        delete_action = menu.addAction(tr("history.delete"))
        chosen = menu.exec(self._list.mapToGlobal(pos))
        if chosen is open_action:
            self._open_item(item)
        elif chosen is delete_action:
            self.delete_requested.emit(document_id)

    def _open_item(self, item: QListWidgetItem) -> None:
        document_id = item.data(Qt.ItemDataRole.UserRole)
        if document_id:
            self.open_requested.emit(str(document_id))
