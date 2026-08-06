"""Подсказка открыть настройки проекта (⚙ на вкладке), если виджет без формы SSH."""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from crm.gui.theme import TEXT_DIM
from crm.i18n import tr


class ProjectSettingsHint(QWidget):
    def __init__(self, project_id: str, main_window: Any, parent=None):
        super().__init__(parent)
        self._project_id = project_id
        self._main = main_window
        lay = QVBoxLayout(self)
        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setStyleSheet(f"color: {TEXT_DIM}; padding: 12px;")
        lay.addWidget(self._label)
        lay.addStretch()
        self.apply_language()

    def apply_language(self) -> None:
        loc = self._main.current_locale()
        self._label.setText(tr(loc, "stub_open_settings", id=self._project_id))
