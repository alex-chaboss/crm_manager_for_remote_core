"""Демо service: одна панель — ядро CRM + таблица метрик, без внутренних вкладок."""

import service_ui
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from crm.gui.project_settings_core import ProjectSettingsCore


def build(parent, project_id: str, main_window):
    root = QWidget(parent)
    lay = QVBoxLayout(root)
    core = ProjectSettingsCore(project_id, main_window, root)
    lay.addWidget(core, stretch=1)
    lay.addWidget(service_ui.build_service_table(root), stretch=0)
    return root
