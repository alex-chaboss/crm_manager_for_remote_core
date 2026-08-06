"""Единая тёмная тема CRM Remote Core."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QApplication, QLineEdit, QMessageBox, QSpinBox

_GUI_DIR = Path(__file__).resolve().parent
_CHECKBOX_CHECKED_ICON = (_GUI_DIR / "checkbox_checked.svg").as_posix()

PROJECT_PANEL_BG = "#1C2833"
PANEL_BG_ALT = "#273746"
BORDER_COLOR = "#34495E"
TEXT_PRIMARY = "#ECF0F1"
TEXT_MUTED = "#BDC3C7"
TEXT_DIM = "#7F8C8D"
ACCENT_BLUE = "#3498DB"
ACCENT_GREEN = "#27AE60"
ACCENT_ORANGE = "#F39C12"
ERROR_RED = "#E74C3C"
BTN_DISABLED = "#7F8C8D"

COMMON_EDIT_STYLE = f"""
QLineEdit, QSpinBox, QComboBox {{
    padding: 4px 6px;
    border: 1px solid #5D6D7E;
    border-radius: 3px;
    background-color: #2C3E50;
    color: {TEXT_PRIMARY};
    min-height: 22px;
}}
"""

ERROR_EDIT_STYLE = f"""
QLineEdit, QSpinBox {{
    padding: 4px 6px;
    border: 2px solid {ERROR_RED};
    border-radius: 3px;
    background-color: #2C3E50;
    color: {TEXT_PRIMARY};
    min-height: 22px;
}}
"""

BTN_PRIMARY = f"""
QPushButton {{
    background-color: {ACCENT_BLUE};
    color: white;
    padding: 6px 12px;
    border-radius: 4px;
    border: none;
}}
QPushButton:disabled {{ background-color: {BTN_DISABLED}; }}
"""

BTN_DANGER = f"""
QPushButton {{
    background-color: {ERROR_RED};
    color: white;
    padding: 6px 12px;
    border-radius: 4px;
    border: none;
}}
QPushButton:disabled {{ background-color: {BTN_DISABLED}; }}
"""

BTN_SUCCESS = f"""
QPushButton {{
    background-color: {ACCENT_GREEN};
    color: white;
    padding: 6px 12px;
    border-radius: 4px;
    border: none;
}}
QPushButton:disabled {{ background-color: {BTN_DISABLED}; }}
"""

LOG_VIEW_STYLE = f"""
QPlainTextEdit {{
    background: {PANEL_BG_ALT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR};
    font-family: monospace;
    font-size: 12px;
}}
"""

# Базовые стили чекбоксов CRM: QCheckBox и индикаторы QTreeWidget/QTreeView.
_CHECK_INDICATOR = f"""
    width: 18px;
    height: 18px;
    border: 2px solid #FFFFFF;
    border-radius: 3px;
    background-color: #2C3E50;
"""
_CHECK_INDICATOR_CHECKED = f"""
    border: 2px solid #FFFFFF;
    background-color: #2C3E50;
    image: url({_CHECKBOX_CHECKED_ICON});
"""

CHECKBOX_STYLE = f"""
QCheckBox {{
    color: {TEXT_MUTED};
    spacing: 8px;
}}
QCheckBox::indicator {{
{_CHECK_INDICATOR}
}}
QCheckBox::indicator:hover {{
    border-color: {TEXT_PRIMARY};
}}
QCheckBox::indicator:checked {{
{_CHECK_INDICATOR_CHECKED}
}}
QCheckBox::indicator:disabled {{
    border-color: {TEXT_DIM};
    background-color: {PROJECT_PANEL_BG};
}}
QCheckBox:disabled {{
    color: {TEXT_DIM};
}}
QTreeWidget::indicator, QTreeView::indicator {{
{_CHECK_INDICATOR}
}}
QTreeWidget::indicator:hover, QTreeView::indicator:hover {{
    border-color: {TEXT_PRIMARY};
}}
QTreeWidget::indicator:checked, QTreeView::indicator:checked {{
{_CHECK_INDICATOR_CHECKED}
}}
QTreeWidget::indicator:disabled, QTreeView::indicator:disabled {{
    border-color: {TEXT_DIM};
    background-color: {PROJECT_PANEL_BG};
}}
"""

DIALOG_STYLE = f"""
QDialog {{
    background-color: {PROJECT_PANEL_BG};
}}
QLabel {{
    color: {TEXT_MUTED};
}}
QTabWidget::pane {{
    border: 1px solid {BORDER_COLOR};
    background: {PROJECT_PANEL_BG};
}}
QTabBar::tab {{
    background: #2C3E50;
    color: {TEXT_PRIMARY};
    padding: 6px 12px;
}}
QTabBar::tab:selected {{
    background: {ACCENT_BLUE};
}}
QTreeWidget {{
    background: #2C3E50;
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR};
}}
""" + CHECKBOX_STYLE

LIST_WIDGET_STYLE = f"""
QListWidget {{
    background: #2C3E50;
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR};
    min-height: 72px;
}}
"""

TAB_PROJECT_STYLE = f"""
QTabWidget::pane {{ border: 1px solid {BORDER_COLOR}; background: {PROJECT_PANEL_BG}; }}
QTabBar::tab {{ background: #2C3E50; color: {TEXT_PRIMARY}; padding: 8px 14px; }}
QTabBar::tab:selected {{ background: {ACCENT_GREEN}; }}
"""


def style_ssh_field(w: QLineEdit | QSpinBox, error: bool) -> None:
    w.setStyleSheet(ERROR_EDIT_STYLE if error else COMMON_EDIT_STYLE)


MESSAGE_BOX_STYLE = f"""
QMessageBox {{
    background-color: {PROJECT_PANEL_BG};
}}
QMessageBox QLabel {{
    color: {TEXT_MUTED};
    min-width: 280px;
}}
QPushButton {{
    background-color: {ACCENT_BLUE};
    color: white;
    padding: 6px 14px;
    border-radius: 4px;
    min-width: 72px;
}}
"""


def apply_app_theme(app: QApplication) -> None:
    app.setStyleSheet(
        f"QWidget {{ background-color: {PROJECT_PANEL_BG}; color: {TEXT_MUTED}; }} "
        + CHECKBOX_STYLE
        + MESSAGE_BOX_STYLE
    )


def themed_message_box(parent, icon: QMessageBox.Icon, title: str, text: str) -> int:
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStyleSheet(MESSAGE_BOX_STYLE)
    return box.exec()
