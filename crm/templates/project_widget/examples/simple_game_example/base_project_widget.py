"""Демо game: две вкладки внутри «Настройки» — CRM и отдельная «График + таблица»."""

import game_ui
from PyQt6.QtWidgets import QTabWidget

from crm.gui.project_settings_core import ProjectSettingsCore


def build(parent, project_id: str, main_window):
    tabs = QTabWidget(parent)
    core = ProjectSettingsCore(project_id, main_window, tabs)
    tabs.addTab(core, "Настройки CRM")
    tabs.addTab(game_ui.build_charts_tab(tabs), "График и таблица (demo)")
    return tabs
