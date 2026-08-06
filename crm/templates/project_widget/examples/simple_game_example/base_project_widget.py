"""Демо game: вкладка CRM (подсказка) + «График + таблица»."""

import game_ui
from PyQt6.QtWidgets import QTabWidget

from crm.gui.project_settings_hint import ProjectSettingsHint


def build(parent, project_id: str, main_window):
    tabs = QTabWidget(parent)
    hint = ProjectSettingsHint(project_id, main_window, tabs)
    tabs.addTab(hint, "CRM")
    tabs.addTab(game_ui.build_charts_tab(tabs), "График и таблица (demo)")
    return tabs
