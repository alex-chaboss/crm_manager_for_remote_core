"""Минимальный project-widget: контент проекта; настройки — через ⚙ на вкладке."""


def build(parent, project_id: str, main_window):
    from crm.gui.project_settings_hint import ProjectSettingsHint

    return ProjectSettingsHint(project_id, main_window, parent)
