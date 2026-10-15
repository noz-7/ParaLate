"""Reserved ad strip: its own layout area, never over document content."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from ads.manager import AdManager
from localization import tr


def _safe_url(url: str) -> bool:
    if not url:
        return False
    parsed = QUrl(url)
    return parsed.scheme() in ("http", "https") and parsed.host() != ""


class AdBanner(QFrame):
    def __init__(self, ad_manager: AdManager, context: str, parent=None) -> None:
        super().__init__(parent)
        self._ads = ad_manager
        self._context = context
        self.setObjectName("banner")
        self.setStyleSheet(
            "#banner { background: #1c1f26; border: 1px solid #2e333e; border-radius: 8px; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)

        self._text = QLabel("")
        self._text.setWordWrap(False)
        self._text.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._text, 1)

        self._action = QPushButton("")
        self._action.setObjectName("toolbar")
        self._action.clicked.connect(self._on_action)
        self._action.hide()
        layout.addWidget(self._action)

        self._url = ""
        self.refresh()

    def refresh(self) -> None:
        """Re-read the ad for the current license state (premium hides it)."""
        ad = self._ads.get_ad(self._context)
        if ad is None:
            self.hide()
            return
        self._url = ad.url if _safe_url(ad.url) else ""
        body = f"{ad.title} — {ad.body}"
        self._text.setText(f"{tr('ad.label')}  ·  {body}")
        if ad.action and self._url:
            self._action.setText(ad.action)
            self._action.show()
        else:
            self._action.hide()
        self.show()

    def _on_action(self) -> None:
        if _safe_url(self._url):
            QDesktopServices.openUrl(QUrl(self._url))
