"""Dark theme: single stylesheet, muted professional palette."""
from __future__ import annotations

COLORS = {
    "window": "#14161a",
    "surface": "#1c1f26",
    "surface_alt": "#232730",
    "border": "#2e333e",
    "text": "#e6e9ef",
    "text_dim": "#9aa3b2",
    "accent": "#4f8cff",
    "accent_hover": "#6ba0ff",
    "danger": "#e5534b",
    "canvas": "#0f1115",
    "page_gap": "#0f1115",
    "page_border": "#3a3f4a",
}

APP_QSS = f"""
* {{
    font-family: "Segoe UI", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 10pt;
    color: {COLORS['text']};
    outline: none;
}}
QMainWindow, QDialog, QWidget#root {{
    background: {COLORS['window']};
}}
QLabel {{
    background: transparent;
}}
QLabel#title {{
    font-size: 30pt;
    font-weight: 700;
}}
QLabel#subtitle {{
    color: {COLORS['text_dim']};
    font-size: 12pt;
}}
QLabel#section {{
    font-size: 13pt;
    font-weight: 600;
}}
QLabel#badge {{
    background: {COLORS['surface_alt']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 9pt;
    font-weight: 600;
}}
QLabel#badgePremium {{
    background: #3a2f14;
    border: 1px solid #6b5a24;
    color: #e8c76a;
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 9pt;
    font-weight: 600;
}}
QLabel#dim {{
    color: {COLORS['text_dim']};
}}
QPushButton {{
    background: {COLORS['surface_alt']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 7px 14px;
    min-height: 20px;
}}
QPushButton:hover {{
    background: #2b303b;
    border-color: #3c4250;
}}
QPushButton:pressed {{
    background: #20242d;
}}
QPushButton:disabled {{
    color: #6a7180;
    background: {COLORS['surface']};
}}
QPushButton#primary {{
    background: {COLORS['accent']};
    border: 1px solid {COLORS['accent']};
    color: #ffffff;
    font-weight: 600;
    padding: 11px 22px;
    font-size: 12pt;
}}
QPushButton#primary:hover {{
    background: {COLORS['accent_hover']};
    border-color: {COLORS['accent_hover']};
}}
QPushButton#primary:pressed {{
    background: #3f74db;
}}
QPushButton#toolbar {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 4px 8px;
}}
QPushButton#toolbar:hover {{
    background: {COLORS['surface_alt']};
    border-color: {COLORS['border']};
}}
QPushButton#ghost {{
    background: transparent;
    border: 1px solid {COLORS['border']};
}}
QListWidget {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 4px;
}}
QListWidget::item {{
    padding: 10px 12px;
    border-radius: 6px;
    margin: 2px;
}}
QListWidget::item:hover {{
    background: {COLORS['surface_alt']};
}}
QListWidget::item:selected {{
    background: #263248;
    border: 1px solid #34507e;
}}
QLineEdit, QComboBox {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {COLORS['accent']};
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: {COLORS['accent']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLORS['text_dim']};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {COLORS['surface_alt']};
    border: 1px solid {COLORS['border']};
    selection-background-color: #263248;
}}
QProgressBar {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    height: 16px;
    text-align: center;
    font-size: 9pt;
}}
QProgressBar::chunk {{
    background: {COLORS['accent']};
    border-radius: 5px;
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: {COLORS['window']};
    width: 12px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #3a4050;
    border-radius: 6px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: #4a5164;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {COLORS['window']};
    height: 12px;
}}
QScrollBar::handle:horizontal {{
    background: #3a4050;
    border-radius: 6px;
    min-width: 32px;
}}
QToolBar {{
    background: {COLORS['surface']};
    border-bottom: 1px solid {COLORS['border']};
    spacing: 8px;
    padding: 5px 8px;
}}
QToolButton {{
    background: transparent;
    border: none;
    border-radius: 5px;
    padding: 5px 8px;
}}
QToolButton:hover {{
    background: {COLORS['surface_alt']};
}}
QToolTip {{
    background: {COLORS['surface_alt']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    padding: 4px 8px;
}}
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    background: {COLORS['surface']};
}}
QCheckBox::indicator:checked {{
    background: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}
QMessageBox {{
    background: {COLORS['surface']};
}}
QStatusBar {{
    background: {COLORS['surface']};
    border-top: 1px solid {COLORS['border']};
}}
"""
