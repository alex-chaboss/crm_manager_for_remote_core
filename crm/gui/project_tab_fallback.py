"""Стандартная трёхвкладочная панель проекта (fallback), если project-widget не загрузился."""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from crm.gui.project_settings_hint import ProjectSettingsHint
from crm.i18n import tr

_PANEL_BG = "#1C2833"


class LegacyProjectTabsWidget(QWidget):
    """Метрики / Health — заглушки; настройки деплоя — ⚙ на вкладке проекта."""

    def __init__(self, project_id: str, main_window: Any, parent=None):
        super().__init__(parent)
        self._project_id = project_id
        self._main = main_window
        self.setStyleSheet(f"background-color: {_PANEL_BG};")

        outer = QVBoxLayout(self)
        self._hint = ProjectSettingsHint(project_id, main_window, self)
        outer.addWidget(self._hint)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #34495E; background: #1C2833; }"
            "QTabBar::tab { background: #2C3E50; color: #ECF0F1; padding: 6px 12px; }"
            "QTabBar::tab:selected { background: #3498DB; }"
        )

        stub_m = QWidget()
        stub_m.setStyleSheet(f"background-color: {_PANEL_BG};")
        stub_m_l = QVBoxLayout(stub_m)
        self._stub_m = QLabel()
        stub_m_l.addWidget(self._stub_m)
        self._tabs.addTab(stub_m, "")
        stub_h = QWidget()
        stub_h.setStyleSheet(f"background-color: {_PANEL_BG};")
        stub_h_l = QVBoxLayout(stub_h)
        self._stub_h = QLabel()
        stub_h_l.addWidget(self._stub_h)
        self._tabs.addTab(stub_h, "")

        outer.addWidget(self._tabs)

    def apply_language(self) -> None:
        loc = self._main.current_locale()
        self._hint.apply_language()
        self._tabs.setTabText(0, tr(loc, "tab_metrics"))
        self._tabs.setTabText(1, tr(loc, "tab_health"))
        self._tabs.tabBar().setTabToolTip(0, tr(loc, "tt_tab_metrics"))
        self._tabs.tabBar().setTabToolTip(1, tr(loc, "tt_tab_health"))
        self._stub_m.setText(f"<i>{tr(loc, 'stub_metrics')}</i>")
        self._stub_h.setText(f"<i>{tr(loc, 'stub_health')}</i>")
