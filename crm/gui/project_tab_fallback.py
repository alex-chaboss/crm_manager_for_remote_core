"""Стандартная трёхвкладочная панель проекта (fallback), если project-widget не загрузился."""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from crm.gui.project_settings_core import ProjectSettingsCore
from crm.i18n import tr

_PANEL_BG = "#1C2833"


class LegacyProjectTabsWidget(QWidget):
    """Настройки / Метрики / Health: первая вкладка — только ProjectSettingsCore (без повторного загрузчика)."""

    def __init__(self, project_id: str, main_window: Any, parent=None):
        super().__init__(parent)
        self._project_id = project_id
        self._main = main_window
        self.setStyleSheet(f"background-color: {_PANEL_BG};")

        outer = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #34495E; background: #1C2833; }"
            "QTabBar::tab { background: #2C3E50; color: #ECF0F1; padding: 6px 12px; }"
            "QTabBar::tab:selected { background: #3498DB; }"
        )

        settings = QWidget()
        settings.setStyleSheet("QWidget { background-color: #1C2833; }")
        s_layout = QVBoxLayout(settings)
        self._core = ProjectSettingsCore(project_id, main_window, settings)
        s_layout.addWidget(self._core)

        self._tabs.addTab(settings, "")
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
        self._tabs.setTabText(0, tr(loc, "tab_settings"))
        self._tabs.setTabText(1, tr(loc, "tab_metrics"))
        self._tabs.setTabText(2, tr(loc, "tab_health"))
        self._tabs.tabBar().setTabToolTip(0, tr(loc, "tt_tab_settings"))
        self._tabs.tabBar().setTabToolTip(1, tr(loc, "tt_tab_metrics"))
        self._tabs.tabBar().setTabToolTip(2, tr(loc, "tt_tab_health"))
        self._stub_m.setText(f"<i>{tr(loc, 'stub_metrics')}</i>")
        self._stub_h.setText(f"<i>{tr(loc, 'stub_health')}</i>")
        self._core.apply_language()

    def mark_ssh_field_error(self, host: bool, port: bool) -> None:
        self._core.mark_ssh_field_error(host, port)

    def clear_ssh_field_error(self) -> None:
        self._core.clear_ssh_field_error()
