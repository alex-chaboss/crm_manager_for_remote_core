"""Полупрозрачный overlay при длительной операции."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from crm.gui.theme import PROJECT_PANEL_BG, TEXT_PRIMARY


class BusyOverlay(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet(f"background-color: rgba(28, 40, 51, 0.72);")
        lay = QVBoxLayout(self)
        lay.addStretch()
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 14px; background: transparent;")
        lay.addWidget(self._label)
        lay.addStretch()
        self.hide()

    def set_message(self, text: str) -> None:
        self._label.setText(text)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
