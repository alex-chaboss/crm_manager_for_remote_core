"""Демо service: подсказка CRM + таблица метрик."""

import service_ui
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from crm.gui.project_settings_hint import ProjectSettingsHint


def build(parent, project_id: str, main_window):
    root = QWidget(parent)
    lay = QVBoxLayout(root)
    hint = ProjectSettingsHint(project_id, main_window, root)
    lay.addWidget(hint, stretch=0)
    lay.addWidget(service_ui.build_service_table(root), stretch=1)
    return root
