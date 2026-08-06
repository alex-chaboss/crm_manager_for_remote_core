"""Демо site: точка входа — класс CRMProjectTab (без функции build)."""

import site_ui
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from crm.gui.project_settings_hint import ProjectSettingsHint


class CRMProjectTab(QWidget):
    """Загрузчик вызывает CRMProjectTab(project_id, main_window, parent), если нет callable build."""

    def __init__(self, project_id: str, main_window, parent=None):
        super().__init__(parent)
        self._project_id = project_id
        self._main = main_window
        lay = QVBoxLayout(self)
        self._hint = ProjectSettingsHint(project_id, main_window, self)
        lay.addWidget(self._hint, stretch=0)
        lay.addWidget(site_ui.build_site_demo_block(self), stretch=1)

    def apply_language(self) -> None:
        self._hint.apply_language()
