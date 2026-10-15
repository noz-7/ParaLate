"""First-run UI language selection and per-document language selection."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from app.constants import LANGUAGE_CHOICES, UI_LANGUAGES
from localization import get_i18n, tr


class FirstRunDialog(QDialog):
    """Language pick + brief information, deliberately minimal (no wizard)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("root")
        self.setWindowTitle("ParaLate")
        self.setMinimumWidth(420)
        self._language = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(14)

        title = QLabel("ParaLate")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(tr("first_run.subtitle"))
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        self._subtitle = subtitle
        layout.addWidget(subtitle)

        lang_label = QLabel(tr("first_run.choose_language"))
        lang_label.setObjectName("section")
        layout.addWidget(lang_label)

        self._lang_list = QListWidget()
        for code, name in UI_LANGUAGES:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, code)
            self._lang_list.addItem(item)
        self._lang_list.setCurrentRow(0)
        self._lang_list.currentRowChanged.connect(self._preview_language)
        layout.addWidget(self._lang_list)

        info = QFrame()
        info.setStyleSheet(
            "QFrame { background: #1c1f26; border: 1px solid #2e333e; border-radius: 8px; }"
        )
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(14, 12, 14, 12)
        self._info_text = QLabel(tr("first_run.info"))
        self._info_text.setWordWrap(True)
        self._info_text.setObjectName("dim")
        info_layout.addWidget(self._info_text)
        self._accept = QCheckBox(tr("first_run.accept"))
        info_layout.addWidget(self._accept)
        layout.addWidget(info)

        self._lang_label = lang_label
        self._continue = QPushButton(tr("common.continue"))
        self._continue.setObjectName("primary")
        self._continue.setEnabled(False)
        self._continue.clicked.connect(self._on_continue)
        layout.addWidget(self._continue)
        self._accept.toggled.connect(self._continue.setEnabled)

    def _preview_language(self, row: int) -> None:
        item = self._lang_list.item(row)
        if item is None:
            return
        code = str(item.data(Qt.ItemDataRole.UserRole))
        get_i18n().set_language(code)
        self._subtitle.setText(tr("first_run.subtitle"))
        self._lang_label.setText(tr("first_run.choose_language"))
        self._info_text.setText(tr("first_run.info"))
        self._accept.setText(tr("first_run.accept"))
        self._continue.setText(tr("common.continue"))

    def _on_continue(self) -> None:
        current = self._lang_list.currentItem()
        self._language = current.data(Qt.ItemDataRole.UserRole) if current else "tr"
        self.accept()

    @property
    def language(self) -> str:
        return self._language or "tr"


class LanguageDialog(QDialog):
    """Pick source (optional auto) and target language for one document."""

    def __init__(self, detected_source: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("root")
        self.setWindowTitle(tr("language.title"))
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        heading = QLabel(tr("language.heading"))
        heading.setObjectName("section")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        source_label = QLabel(tr("language.source"))
        source_label.setObjectName("dim")
        layout.addWidget(source_label)
        self._source = QComboBox()
        self._source.addItem(tr("language.auto"), "auto")
        for code, name in LANGUAGE_CHOICES:
            self._source.addItem(name, code)
        if detected_source:
            for index in range(self._source.count()):
                if self._source.itemData(index) == detected_source:
                    self._source.setCurrentIndex(index)
                    break
        layout.addWidget(self._source)

        target_label = QLabel(tr("language.target"))
        target_label.setObjectName("dim")
        layout.addWidget(target_label)
        self._target = QComboBox()
        for code, name in LANGUAGE_CHOICES:
            self._target.addItem(name, code)
        # default target: Turkish
        self._target.setCurrentIndex(max(0, self._target.findData("tr")))
        layout.addWidget(self._target)

        row = self._make_button_row()
        layout.addWidget(row)

        self._source.currentIndexChanged.connect(self._sync_target)
        self._sync_target()

    def _sync_target(self) -> None:
        """Never offer the same language as both source and target."""
        source = self._source.currentData()
        if source == "auto":
            return
        if self._target.currentData() == source:
            index = self._target.findData("tr" if source != "tr" else "en")
            if index >= 0:
                self._target.setCurrentIndex(index)

    def _make_button_row(self):
        from PyQt6.QtWidgets import QHBoxLayout

        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(tr("common.cancel"))
        cancel.clicked.connect(self.reject)
        ok = QPushButton(tr("common.ok"))
        ok.setObjectName("primary")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        container = QFrame()
        container.setLayout(row)
        return container

    @property
    def source_language(self) -> str:
        return str(self._source.currentData() or "auto")

    @property
    def target_language(self) -> str:
        return str(self._target.currentData() or "tr")
