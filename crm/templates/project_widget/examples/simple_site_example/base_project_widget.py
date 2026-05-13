"""Демо site: точка входа — класс CRMProjectTab (без функции build)."""

import site_ui
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from crm.gui.project_settings_core import ProjectSettingsCore


class CRMProjectTab(QWidget):
    """Загрузчик вызывает CRMProjectTab(project_id, main_window, parent), если нет callable build."""

    def __init__(self, project_id: str, main_window, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        core = ProjectSettingsCore(project_id, main_window, self)
        lay.addWidget(core, stretch=1)
        lay.addWidget(site_ui.build_site_demo_block(self), stretch=0)
