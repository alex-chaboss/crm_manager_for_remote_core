"""Минимальный project-widget: только стандартное ядро вкладки «Настройки»."""


def build(parent, project_id: str, main_window):
    from crm.gui.project_settings_core import ProjectSettingsCore

    return ProjectSettingsCore(project_id, main_window, parent)
