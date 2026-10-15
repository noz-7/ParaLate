"""Timed, session-modal introduction to currently available Premium features."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from localization import tr
from ui.dialogs.premium_dialog import PremiumDialog


class PremiumPromoDialog(QDialog):
    def __init__(self, services, parent=None) -> None:
        super().__init__(parent)
        self._services = services
        self.setObjectName("root")
        self.setWindowTitle(tr("premium.heading"))
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(14)

        crown = QLabel("👑")
        crown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        crown.setStyleSheet("font-size: 32pt; background: transparent;")
        layout.addWidget(crown)

        heading = QLabel(tr("premium.promo_heading"))
        heading.setObjectName("section")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)

        benefits = QLabel(tr("premium.promo_benefits"))
        benefits.setWordWrap(True)
        benefits.setObjectName("dim")
        benefits.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(benefits)

        buttons = QHBoxLayout()
        activate = QPushButton(tr("premium.promo_activate"))
        activate.setObjectName("primary")
        activate.clicked.connect(self._activate)
        buttons.addWidget(activate)
        close = QPushButton(tr("premium.promo_close"))
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _activate(self) -> None:
        dialog = PremiumDialog(self._services.license, self)
        dialog.exec()
        if self._services.license.is_premium:
            self.accept()
