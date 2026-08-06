"""Главное окно: слева глобальный CRM, справа вкладки проектов."""

from __future__ import annotations

import logging
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from crm import __version__
from crm.config_store import GLOBAL_DEFAULTS, load_global, save_global
from crm.command_lists import LOCAL_PREFIX, LOCAL_SH_PREFIX, SERVER_PREFIX, SERVER_SH_PREFIX
from crm.gui.command_list_editor import CommandListEditor
from crm.gui.busy_overlay import BusyOverlay
from crm.gui.theme import BTN_PRIMARY, COMMON_EDIT_STYLE, TAB_PROJECT_STYLE, style_ssh_field, themed_message_box
from crm.gui.project_settings_dialog import ProjectSettingsDialog
from crm.i18n import normalize_locale, tr
from crm.project_init import create_project_skeleton, list_project_ids
from crm.project_widget_loader import load_project_tab

logger = logging.getLogger(__name__)

PROJECT_PANEL_BG = "#1C2833"


class _GlobalPanel(QWidget):
    """Левая колонка: глобальные настройки SSH/таймаут."""

    def __init__(self, main_window: "MainWindow", parent=None):
        super().__init__(parent)
        self._main = main_window
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(500)
        self._debounce.timeout.connect(self._flush_autosave)

        self.setStyleSheet("QWidget { background-color: #1C2833; } QLabel { color: #BDC3C7; }")
        layout = QVBoxLayout(self)
        self._title = QLabel()
        self._title.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._title)

        form = QFormLayout()
        self.host = QLineEdit()
        self.port = QLineEdit()
        self.work = QLineEdit()
        self.remote = QLineEdit()
        self.branch = QLineEdit()
        self.restart = QLineEdit()
        self.timeout = QSpinBox()
        self.timeout.setRange(30, 3600)
        self.timeout.setSuffix(" с")
        for w in (self.host, self.port, self.work, self.remote, self.branch, self.restart, self.timeout):
            w.setStyleSheet(COMMON_EDIT_STYLE)
        self._lbl_host = QLabel()
        self._lbl_port = QLabel()
        self._lbl_work = QLabel()
        self._lbl_remote = QLabel()
        self._lbl_branch = QLabel()
        self._lbl_restart = QLabel()
        self._lbl_timeout = QLabel()
        for lbl in (
            self._lbl_host,
            self._lbl_port,
            self._lbl_work,
            self._lbl_remote,
            self._lbl_branch,
            self._lbl_restart,
            self._lbl_timeout,
        ):
            lbl.setWordWrap(True)
        form.addRow(self._lbl_host, self.host)
        form.addRow(self._lbl_port, self.port)
        form.addRow(self._lbl_work, self.work)
        form.addRow(self._lbl_remote, self.remote)
        form.addRow(self._lbl_branch, self.branch)
        form.addRow(self._lbl_restart, self.restart)
        form.addRow(self._lbl_timeout, self.timeout)
        layout.addLayout(form)

        self.server_base = QLineEdit()
        self.server_base.setStyleSheet(COMMON_EDIT_STYLE)
        self._lbl_server_base = QLabel()
        form.addRow(self._lbl_server_base, self.server_base)

        self._lbl_g_cmd_hint = QLabel()
        self._lbl_g_cmd_hint.setWordWrap(True)
        self._lbl_g_cmd_hint.setStyleSheet("color: #95A5A6; font-size: 11px;")
        layout.addWidget(self._lbl_g_cmd_hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_inner = QWidget()
        scroll_lay = QVBoxLayout(scroll_inner)
        self._lbl_g_pre_init = QLabel()
        scroll_lay.addWidget(self._lbl_g_pre_init)
        self.g_pre_init = CommandListEditor()
        scroll_lay.addWidget(self.g_pre_init)
        self._lbl_g_post_init = QLabel()
        scroll_lay.addWidget(self._lbl_g_post_init)
        self.g_post_init = CommandListEditor()
        scroll_lay.addWidget(self.g_post_init)
        self._lbl_g_pre_deploy = QLabel()
        scroll_lay.addWidget(self._lbl_g_pre_deploy)
        self.g_pre_deploy = CommandListEditor()
        scroll_lay.addWidget(self.g_pre_deploy)
        self._lbl_g_post_deploy = QLabel()
        scroll_lay.addWidget(self._lbl_g_post_deploy)
        self.g_post_deploy = CommandListEditor()
        scroll_lay.addWidget(self.g_post_deploy)
        scroll.setWidget(scroll_inner)
        layout.addWidget(scroll, stretch=1)

        self.save_btn = QPushButton()
        self.save_btn.clicked.connect(self._save_clicked)
        self.save_btn.setStyleSheet(BTN_PRIMARY)
        layout.addWidget(self.save_btn)

        self._about = QLabel()
        self._about.setTextFormat(Qt.TextFormat.RichText)
        self._about.setWordWrap(True)
        layout.addWidget(self._about)

        self._connect_autosave()
        self.host.textChanged.connect(self._on_ssh_field_edited)
        self.port.textChanged.connect(self._on_ssh_field_edited)
        self._load(block_signals=True)
        self.apply_language()

    def _on_ssh_field_edited(self) -> None:
        self._main.clear_ssh_error_marks()

    def _connect_autosave(self) -> None:
        for w in (self.host, self.port, self.work, self.remote, self.branch, self.restart, self.server_base):
            w.textChanged.connect(self._schedule_autosave)
        self.timeout.valueChanged.connect(self._schedule_autosave)
        for editor in (
            self.g_pre_init,
            self.g_post_init,
            self.g_pre_deploy,
            self.g_post_deploy,
        ):
            editor.commands_changed.connect(self._schedule_autosave)

    def _schedule_autosave(self) -> None:
        self._debounce.start()

    def _flush_autosave(self) -> None:
        save_global(self._collect_updates())
        self._main.show_saved_toast()

    def _collect_updates(self) -> dict:
        return {
            "ssh_host": self.host.text().strip(),
            "ssh_port": self.port.text().strip(),
            "ssh_work_dir": self.work.text().strip(),
            "ssh_git_remote": self.remote.text().strip() or GLOBAL_DEFAULTS["ssh_git_remote"],
            "ssh_git_branch": self.branch.text().strip() or GLOBAL_DEFAULTS["ssh_git_branch"],
            "ssh_restart_command": self.restart.text().strip() or GLOBAL_DEFAULTS["ssh_restart_command"],
            "ssh_command_timeout_sec": int(self.timeout.value()),
            "server_base_path": self.server_base.text().strip(),
            "pre_init_commands": self.g_pre_init.get_commands(),
            "post_init_commands": self.g_post_init.get_commands(),
            "pre_deploy_commands": self.g_pre_deploy.get_commands(),
            "post_deploy_commands": self.g_post_deploy.get_commands(),
        }

    def _load(self, block_signals: bool = False) -> None:
        widgets = (
            self.host,
            self.port,
            self.work,
            self.remote,
            self.branch,
            self.restart,
            self.timeout,
        )
        if block_signals:
            for w in widgets:
                w.blockSignals(True)
        g = load_global()
        self.host.setText(str(g.get("ssh_host") or ""))
        self.port.setText(str(g.get("ssh_port") or ""))
        self.work.setText(str(g.get("ssh_work_dir") or ""))
        self.remote.setText(str(g.get("ssh_git_remote") or GLOBAL_DEFAULTS["ssh_git_remote"]))
        self.branch.setText(str(g.get("ssh_git_branch") or GLOBAL_DEFAULTS["ssh_git_branch"]))
        self.restart.setText(str(g.get("ssh_restart_command") or GLOBAL_DEFAULTS["ssh_restart_command"]))
        self.timeout.setValue(int(g.get("ssh_command_timeout_sec") or GLOBAL_DEFAULTS["ssh_command_timeout_sec"]))
        self.server_base.setText(str(g.get("server_base_path") or ""))
        self.g_pre_init.set_commands(list(g.get("pre_init_commands") or []))
        self.g_post_init.set_commands(list(g.get("post_init_commands") or []))
        self.g_pre_deploy.set_commands(list(g.get("pre_deploy_commands") or []))
        self.g_post_deploy.set_commands(list(g.get("post_deploy_commands") or []))
        if block_signals:
            for w in widgets:
                w.blockSignals(False)

    def _save_clicked(self) -> None:
        save_global(self._collect_updates())
        loc = self._main.current_locale()
        QMessageBox.information(self, tr(loc, "dlg_crm_title"), tr(loc, "msg_saved_global"))

    def apply_language(self) -> None:
        loc = self._main.current_locale()
        self._title.setText(f"<b style='color:#2ECC71'>{tr(loc, 'title_global')}</b>")
        self._lbl_host.setText(tr(loc, "lbl_ssh_host"))
        self._lbl_port.setText(tr(loc, "lbl_ssh_port"))
        self._lbl_work.setText(tr(loc, "lbl_ssh_work"))
        self._lbl_remote.setText(tr(loc, "lbl_git_remote"))
        self._lbl_branch.setText(tr(loc, "lbl_git_branch"))
        self._lbl_restart.setText(tr(loc, "lbl_restart"))
        self._lbl_timeout.setText(tr(loc, "lbl_timeout"))
        self._lbl_server_base.setText(tr(loc, "lbl_server_base_global"))
        self._lbl_g_pre_init.setText(tr(loc, "lbl_pre_init_cmds_global"))
        self._lbl_g_post_init.setText(tr(loc, "lbl_post_init_cmds_global"))
        self._lbl_g_pre_deploy.setText(tr(loc, "lbl_pre_deploy_cmds_global"))
        self._lbl_g_post_deploy.setText(tr(loc, "lbl_post_deploy_cmds_global"))
        self._lbl_g_cmd_hint.setText(
            tr(
                loc,
                "hint_command_lists",
                local_sh_prefix=LOCAL_SH_PREFIX,
                local_prefix=LOCAL_PREFIX,
                server_sh_prefix=SERVER_SH_PREFIX,
                server_prefix=SERVER_PREFIX,
            )
        )
        self.save_btn.setText(tr(loc, "btn_save_global"))
        self._about.setText(
            f"<span style='color:#95A5A6'>CRM Remote Core v{__version__}<br>"
            f"{tr(loc, 'about_footer')}</span>"
        )
        self.host.setToolTip(tr(loc, "tt_ssh_host"))
        self.port.setToolTip(tr(loc, "tt_ssh_port"))
        self.work.setToolTip(tr(loc, "tt_ssh_work"))
        self.remote.setToolTip(tr(loc, "tt_git_remote"))
        self.branch.setToolTip(tr(loc, "tt_git_branch"))
        self.restart.setToolTip(tr(loc, "tt_restart"))
        self.timeout.setToolTip(tr(loc, "tt_timeout"))
        self.save_btn.setToolTip(tr(loc, "tt_btn_save_global"))

    def mark_ssh_field_error(self, host: bool, port: bool) -> None:
        style_ssh_field(self.host, host)
        style_ssh_field(self.port, port)

    def clear_ssh_field_error(self) -> None:
        style_ssh_field(self.host, False)
        style_ssh_field(self.port, False)


class _ProjectInner(QWidget):
    """Область одного проекта: целиком из project-widget или fallback (Настройки / Метрики / Health)."""

    def __init__(self, project_id: str, main_window: "MainWindow", parent=None):
        super().__init__(parent)
        self._project_id = project_id
        self._main = main_window
        self.setObjectName("ProjectInner")
        self.setStyleSheet(f"#ProjectInner {{ background-color: {PROJECT_PANEL_BG}; }}")

        outer = QVBoxLayout(self)
        self._root = load_project_tab(project_id, main_window, self)
        outer.addWidget(self._root)
        self.apply_language()

    def apply_language(self) -> None:
        root = self._root
        if hasattr(root, "apply_language") and callable(getattr(root, "apply_language")):
            root.apply_language()

    def mark_ssh_field_error(self, host: bool, port: bool) -> None:
        pass

    def clear_ssh_field_error(self) -> None:
        pass


class MainWindow(QMainWindow):
    """Окно со сплиттером: глобал | проекты."""

    def __init__(self, parent=None):
        super().__init__(parent)
        g0 = load_global()
        self._locale = normalize_locale(g0.get("ui_locale"))

        self.setWindowTitle(tr(self._locale, "window_title"))
        self.resize(1100, 640)
        self.setStyleSheet("QMainWindow#MainWindow { background-color: #1C2833; }")
        self.setObjectName("MainWindow")

        central = QWidget()
        self.setCentralWidget(central)
        self._busy_overlay = BusyOverlay(central)
        self._busy_overlay.hide()
        root = QVBoxLayout(central)
        split = QSplitter(Qt.Orientation.Horizontal)
        self._global_panel = _GlobalPanel(self)
        split.addWidget(self._global_panel)

        right_wrap = QWidget()
        right_wrap.setStyleSheet(f"background-color: {PROJECT_PANEL_BG};")
        rw = QVBoxLayout(right_wrap)
        hdr_row = QHBoxLayout()
        self._hdr_projects = QLabel()
        self._hdr_projects.setTextFormat(Qt.TextFormat.RichText)
        hdr_row.addWidget(self._hdr_projects)
        hdr_row.addStretch()
        self._lang_label = QLabel()
        self._lang_label.setStyleSheet("color: #BDC3C7;")
        self._lang_combo = QComboBox()
        self._lang_combo.addItem(tr(self._locale, "lang_ru"), "ru")
        self._lang_combo.addItem(tr(self._locale, "lang_en"), "en")
        self._lang_combo.currentIndexChanged.connect(self._on_locale_combo)
        hdr_row.addWidget(self._lang_label)
        hdr_row.addWidget(self._lang_combo)
        self.plus_btn = QToolButton()
        self.plus_btn.setText("+")
        self.plus_btn.clicked.connect(self._on_new_project)
        self.plus_btn.setStyleSheet(
            "QToolButton { background: #27AE60; color: white; font-weight: bold; "
            "padding: 4px 10px; border-radius: 3px; }"
        )
        hdr_row.addWidget(self.plus_btn)
        rw.addLayout(hdr_row)

        self._proj_tabs = QTabWidget()
        self._proj_tabs.setStyleSheet(TAB_PROJECT_STYLE)
        rw.addWidget(self._proj_tabs)

        self._progress = QLabel("")
        self._progress.setStyleSheet("color: #F39C12;")
        rw.addWidget(self._progress)

        self._saved_toast = QLabel("")
        self._saved_toast.setStyleSheet("color: #2ECC71; font-size: 11px;")
        rw.addWidget(self._saved_toast)
        self._saved_flash = QTimer(self)
        self._saved_flash.setSingleShot(True)
        self._saved_flash.setInterval(1600)
        self._saved_flash.timeout.connect(lambda: self._saved_toast.setText(""))

        split.addWidget(right_wrap)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([320, 780])
        root.addWidget(split)

        self._reload_project_tabs()
        self.apply_language()

    def current_locale(self) -> str:
        return self._locale

    def _on_locale_combo(self) -> None:
        raw = self._lang_combo.currentData()
        if raw is None:
            return
        self._locale = normalize_locale(str(raw))
        save_global({"ui_locale": self._locale})
        self.apply_language()

    def apply_language(self) -> None:
        loc = self._locale
        self.setWindowTitle(tr(loc, "window_title"))
        self._hdr_projects.setText(f"<b style='color:#2ECC71'>{tr(loc, 'title_projects')}</b>")
        self._lang_label.setText(tr(loc, "lang_ui"))
        self._lang_combo.blockSignals(True)
        self._lang_combo.setItemText(0, tr(loc, "lang_ru"))
        self._lang_combo.setItemText(1, tr(loc, "lang_en"))
        for i in range(self._lang_combo.count()):
            if normalize_locale(str(self._lang_combo.itemData(i))) == loc:
                self._lang_combo.setCurrentIndex(i)
                break
        self._lang_combo.blockSignals(False)
        self.plus_btn.setToolTip(tr(loc, "tt_plus"))
        self._global_panel.apply_language()
        for i in range(self._proj_tabs.count()):
            inner = self._project_inner_at(i)
            if inner:
                inner.apply_language()

    def _project_inner_at(self, index: int) -> _ProjectInner | None:
        w = self._proj_tabs.widget(index)
        if isinstance(w, QScrollArea):
            iw = w.widget()
            if isinstance(iw, _ProjectInner):
                return iw
        return None

    def set_busy_overlay(self, visible: bool, message: str = "") -> None:
        central = self.centralWidget()
        if central is None:
            return
        if visible:
            self._busy_overlay.set_message(message or tr(self._locale, "progress_busy"))
            self._busy_overlay.setGeometry(central.rect())
            self._busy_overlay.show()
            self._busy_overlay.raise_()
        else:
            self._busy_overlay.hide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        central = self.centralWidget()
        if central and self._busy_overlay.isVisible():
            self._busy_overlay.setGeometry(central.rect())

    def set_progress(self, busy: bool) -> None:
        loc = self._locale
        self._progress.setText(tr(loc, "progress_busy") if busy else "")

    def show_saved_toast(self) -> None:
        self.flash_saved_toast()

    def flash_saved_toast(self) -> None:
        self._saved_toast.setText(tr(self._locale, "saved_toast"))
        self._saved_flash.stop()
        self._saved_flash.start()

    def clear_ssh_error_marks(self) -> None:
        self._global_panel.clear_ssh_field_error()
        for i in range(self._proj_tabs.count()):
            inner = self._project_inner_at(i)
            if inner:
                inner.clear_ssh_field_error()

    def set_ssh_deploy_error_marks(self, *, host: bool = False, port: bool = False, project_id: str = "") -> None:
        # project_id: подсветка полей проекта — в ProjectSettingsDialog при валидации Deploy/Init
        _ = project_id
        self._global_panel.mark_ssh_field_error(host=host, port=port)

    def open_project_settings(self, project_id: str) -> None:
        dlg = ProjectSettingsDialog(project_id, self, self)
        dlg.exec()

    def _attach_tab_gear(self, tab_index: int, project_id: str) -> None:
        btn = QToolButton()
        btn.setText("⚙")
        btn.setToolTip(tr(self._locale, "tt_project_settings_gear"))
        btn.setStyleSheet(
            "QToolButton { background: transparent; color: #ECF0F1; padding: 2px 6px; border: none; }"
            "QToolButton:hover { color: #2ECC71; }"
        )
        btn.clicked.connect(lambda _checked=False, pid=project_id: self.open_project_settings(pid))
        self._proj_tabs.tabBar().setTabButton(
            tab_index,
            QTabBar.ButtonPosition.RightSide,
            btn,
        )

    def _reload_project_tabs(self) -> None:
        self._proj_tabs.clear()
        for pid in list_project_ids():
            inner = _ProjectInner(pid, self)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(inner)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setStyleSheet(
                f"QScrollArea {{ border: none; background: {PROJECT_PANEL_BG}; }}"
                f"QScrollArea > QWidget > QWidget {{ background: {PROJECT_PANEL_BG}; }}"
            )
            pal = scroll.viewport().palette()
            pal.setColor(QPalette.ColorRole.Window, QColor(PROJECT_PANEL_BG))
            pal.setColor(QPalette.ColorRole.Base, QColor(PROJECT_PANEL_BG))
            scroll.viewport().setPalette(pal)
            scroll.viewport().setAutoFillBackground(True)
            scroll.viewport().setStyleSheet(f"background-color: {PROJECT_PANEL_BG};")
            idx = self._proj_tabs.addTab(scroll, pid)
            self._attach_tab_gear(idx, pid)

    def _on_new_project(self) -> None:
        loc = self._locale
        name, ok = QInputDialog.getText(
            self,
            tr(loc, "dlg_new_project_title"),
            tr(loc, "dlg_new_project_label"),
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        try:
            create_project_skeleton(name)
        except FileExistsError:
            QMessageBox.warning(self, tr(loc, "dlg_crm_title"), tr(loc, "msg_project_exists", name=name))
            return
        except ValueError as e:
            QMessageBox.warning(self, tr(loc, "dlg_crm_title"), str(e))
            return
        self._reload_project_tabs()
        self.apply_language()
        for i in range(self._proj_tabs.count()):
            if self._proj_tabs.tabText(i) == name:
                self._proj_tabs.setCurrentIndex(i)
                break
        QMessageBox.information(self, tr(loc, "dlg_crm_title"), tr(loc, "msg_project_created", name=name))
