"""Модальные настройки проекта (⚙ на вкладке)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStyle,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from crm.boss_server_bind import boss_server_bind_warning
from crm.command_lists import (
    LOCAL_PREFIX,
    LOCAL_SH_PREFIX,
    SERVER_PREFIX,
    SERVER_SH_PREFIX,
    run_merged_command_list,
)
from crm.config_store import (
    build_ssh_restart_command,
    effective_ssh_config,
    load_project,
    merge_command_lists,
    save_project,
    validate_deploy_ssh,
)
from crm.core_tree import (
    collapse_stale_build_artifacts,
    collect_checked_paths,
    populate_core_tree,
    set_all_checked,
)
from crm.deploy_ops import run_deploy_job
from crm.git_clone import (
    clone_into_project_core,
    extract_git_url_token,
    project_core_has_content,
    project_core_has_git,
)
from crm.gui.command_list_editor import CommandListEditor
from crm.gui.operation_runner import OperationRunner
from crm.gui.theme import (
    BTN_PRIMARY,
    BTN_SUCCESS,
    CHECKBOX_STYLE,
    COMMON_EDIT_STYLE,
    DIALOG_STYLE,
    TEXT_DIM,
    style_ssh_field,
    themed_message_box,
)
from crm.i18n import tr
from crm.operation_cancel import CancelToken
from crm.paths import project_dir
from crm.secret_markers import extract_markers, load_secrets_file, make_masked_log
from crm.server_init import probe_server_init_paths, run_server_init_job
from crm.sync_deploy import copy_core_paths_to_targets

if TYPE_CHECKING:
    from crm.gui.main_window import MainWindow


class ProjectSettingsDialog(QDialog):
    def __init__(self, project_id: str, main_window: "MainWindow", parent=None):
        super().__init__(parent)
        self._project_id = project_id
        self._main = main_window
        self._loading = False
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(500)
        self._debounce.timeout.connect(self._flush_autosave)
        self._secrets_from_file: dict[str, str] = {}
        self.setMinimumSize(720, 560)
        self.setStyleSheet(DIALOG_STYLE)

        root = QVBoxLayout(self)
        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        self._page_settings = QWidget()
        self._build_settings_page()
        self._tabs.addTab(self._page_settings, "")

        self._page_core = QWidget()
        self._build_core_page()
        self._tab_core_index = 1
        self._tabs.addTab(self._page_core, "")

        btn_row = QHBoxLayout()
        self.btn_save = QPushButton()
        self.btn_save.setStyleSheet(BTN_PRIMARY)
        self.btn_save.clicked.connect(self._save_clicked)
        btn_row.addWidget(self.btn_save)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self._connect_autosave()
        self._load()
        self._refresh_core_tab_visibility()
        self.apply_language()

    def _build_settings_page(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(CHECKBOX_STYLE)
        inner = QWidget()
        lay = QVBoxLayout(inner)

        self.source_url = QLineEdit()
        self.source_url.setStyleSheet(COMMON_EDIT_STYLE)
        self._lbl_source_url = QLabel()
        clone_form = QFormLayout()
        clone_form.addRow(self._lbl_source_url, self.source_url)
        lay.addLayout(clone_form)

        clone_row = QHBoxLayout()
        self.btn_clone = QPushButton()
        self.btn_clone.setStyleSheet(BTN_SUCCESS)
        self.btn_clone.clicked.connect(self._on_clone)
        clone_row.addWidget(self.btn_clone)
        lay.addLayout(clone_row)

        self._lbl_secrets_file = QLabel()
        self.secrets_file_path = QLineEdit()
        self.secrets_file_path.setReadOnly(True)
        self.secrets_file_path.setStyleSheet(COMMON_EDIT_STYLE)
        self.btn_secrets_browse = QPushButton()
        self.btn_secrets_browse.clicked.connect(self._on_secrets_browse)
        self.btn_secrets_refresh = QToolButton()
        self.btn_secrets_refresh.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.btn_secrets_refresh.clicked.connect(self._on_secrets_refresh)
        secrets_row = QHBoxLayout()
        secrets_row.addWidget(self.secrets_file_path, stretch=1)
        secrets_row.addWidget(self.btn_secrets_browse)
        secrets_row.addWidget(self.btn_secrets_refresh)
        secrets_form = QFormLayout()
        secrets_form.addRow(self._lbl_secrets_file, secrets_row)
        lay.addLayout(secrets_form)

        form = QFormLayout()
        self.server_base = QLineEdit()
        self.server_name = QLineEdit()
        self.server_branch = QLineEdit()
        self.server_alias = QLineEdit()
        for w in (self.server_base, self.server_name, self.server_branch, self.server_alias):
            w.setStyleSheet(COMMON_EDIT_STYLE)
        self._lbl_server_base = QLabel()
        self._lbl_server_name = QLabel()
        self._lbl_server_branch = QLabel()
        self._lbl_server_alias = QLabel()
        form.addRow(self._lbl_server_base, self.server_base)
        form.addRow(self._lbl_server_name, self.server_name)
        form.addRow(self._lbl_server_branch, self.server_branch)
        form.addRow(self._lbl_server_alias, self.server_alias)
        lay.addLayout(form)

        self.auto_sync = QCheckBox()
        lay.addWidget(self.auto_sync)

        form2 = QFormLayout()
        self.rsc_override = QLineEdit()
        self.bs_override = QLineEdit()
        self.p_host = QLineEdit()
        self.p_port = QLineEdit()
        self.p_work = QLineEdit()
        self.p_restart = QLineEdit()
        self.p_timeout = QSpinBox()
        self.p_timeout.setRange(0, 3600)
        for w in (self.rsc_override, self.bs_override, self.p_host, self.p_port, self.p_work, self.p_restart):
            w.setStyleSheet(COMMON_EDIT_STYLE)
        self.p_timeout.setStyleSheet(COMMON_EDIT_STYLE)
        self._lbl_rsc = QLabel()
        self._lbl_bs = QLabel()
        self._lbl_ph = QLabel()
        self._lbl_pp = QLabel()
        self._lbl_pw = QLabel()
        self._lbl_prs = QLabel()
        self._lbl_pto = QLabel()
        form2.addRow(self._lbl_rsc, self.rsc_override)
        form2.addRow(self._lbl_bs, self.bs_override)
        form2.addRow(self._lbl_ph, self.p_host)
        form2.addRow(self._lbl_pp, self.p_port)
        form2.addRow(self._lbl_pw, self.p_work)
        form2.addRow(self._lbl_prs, self.p_restart)
        form2.addRow(self._lbl_pto, self.p_timeout)
        lay.addLayout(form2)

        self._paths_label = QLabel()
        self._paths_label.setWordWrap(True)
        self._paths_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
        lay.addWidget(self._paths_label)

        self.merge_global_cmds = QCheckBox()
        lay.addWidget(self.merge_global_cmds)

        self._lbl_pre_init = QLabel()
        lay.addWidget(self._lbl_pre_init)
        self.pre_init = CommandListEditor()
        lay.addWidget(self.pre_init)
        self._lbl_post_init = QLabel()
        lay.addWidget(self._lbl_post_init)
        self.post_init = CommandListEditor()
        lay.addWidget(self.post_init)

        self.btn_init = QPushButton()
        self.btn_init.setStyleSheet(BTN_SUCCESS)
        self.btn_init.clicked.connect(self._on_init)
        lay.addWidget(self.btn_init)

        self._lbl_pre_deploy = QLabel()
        lay.addWidget(self._lbl_pre_deploy)
        self.pre_deploy = CommandListEditor()
        lay.addWidget(self.pre_deploy)
        self._lbl_post_deploy = QLabel()
        lay.addWidget(self._lbl_post_deploy)
        self.post_deploy = CommandListEditor()
        lay.addWidget(self.post_deploy)

        self.btn_deploy = QPushButton()
        self.btn_deploy.setStyleSheet(BTN_PRIMARY)
        self.btn_deploy.clicked.connect(self._on_deploy)
        lay.addWidget(self.btn_deploy)

        self.btn_test_pre_deploy = QPushButton()
        self.btn_test_pre_deploy.setStyleSheet(BTN_PRIMARY)
        self.btn_test_pre_deploy.clicked.connect(self._on_test_pre_deploy)
        lay.addWidget(self.btn_test_pre_deploy)

        self._lbl_cmd_hint = QLabel()
        self._lbl_cmd_hint.setWordWrap(True)
        self._lbl_cmd_hint.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
        lay.addWidget(self._lbl_cmd_hint)

        lay.addStretch()
        scroll.setWidget(inner)
        page_lay = QVBoxLayout(self._page_settings)
        page_lay.addWidget(scroll)

    def _build_core_page(self) -> None:
        lay = QVBoxLayout(self._page_core)
        self.btn_select_all = QPushButton()
        self.btn_select_all.setStyleSheet(BTN_PRIMARY)
        self.btn_select_all.clicked.connect(self._select_all_tree)
        lay.addWidget(self.btn_select_all)
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setStyleSheet(CHECKBOX_STYLE)
        lay.addWidget(self._tree)
        self.btn_apply_core = QPushButton()
        self.btn_apply_core.setStyleSheet(BTN_PRIMARY)
        self.btn_apply_core.clicked.connect(self._apply_core_copy)
        lay.addWidget(self.btn_apply_core)

    def _connect_autosave(self) -> None:
        for w in (
            self.server_base,
            self.server_name,
            self.server_branch,
            self.server_alias,
            self.source_url,
            self.rsc_override,
            self.bs_override,
            self.p_host,
            self.p_port,
            self.p_work,
            self.p_restart,
        ):
            w.textChanged.connect(self._schedule_autosave)
        self.auto_sync.toggled.connect(self._schedule_autosave)
        self.merge_global_cmds.toggled.connect(self._schedule_autosave)
        self.p_timeout.valueChanged.connect(self._schedule_autosave)
        for editor in (self.pre_init, self.post_init, self.pre_deploy, self.post_deploy):
            editor.commands_changed.connect(self._schedule_autosave)
        self._tree.itemChanged.connect(self._on_tree_item_changed)

    def _schedule_autosave(self) -> None:
        if self._loading:
            return
        self._debounce.start()

    def _flush_autosave(self) -> None:
        save_project(self._project_id, self._collect())
        self._main.show_saved_toast()

    def _on_tree_item_changed(self, _item, column: int) -> None:
        if column == 0:
            self._schedule_autosave()

    def closeEvent(self, event) -> None:
        if self._debounce.isActive():
            self._debounce.stop()
            self._flush_autosave()
        super().closeEvent(event)

    def _collect(self) -> dict:
        return {
            "server_base_path": self.server_base.text().strip(),
            "server_project_name": self.server_name.text().strip(),
            "server_git_branch": self.server_branch.text().strip(),
            "server_remote_alias": self.server_alias.text().strip(),
            "source_git_url": self.source_url.text().strip(),
            "secrets_file_path": self.secrets_file_path.text().strip(),
            "auto_sync_enabled": self.auto_sync.isChecked(),
            "merge_global_commands": self.merge_global_cmds.isChecked(),
            "remote_server_core": self.rsc_override.text().strip(),
            "boss_server": self.bs_override.text().strip(),
            "ssh_host": self.p_host.text().strip(),
            "ssh_port": self.p_port.text().strip(),
            "ssh_work_dir": self.p_work.text().strip(),
            "ssh_restart_command": self.p_restart.text().strip(),
            "ssh_command_timeout_sec": int(self.p_timeout.value()),
            "pre_init_commands": self.pre_init.get_commands(),
            "post_init_commands": self.post_init.get_commands(),
            "pre_deploy_commands": self.pre_deploy.get_commands(),
            "post_deploy_commands": self.post_deploy.get_commands(),
            "core_sync_paths": self._selected_tree_paths(),
        }

    def _load(self) -> None:
        self._loading = True
        p = load_project(self._project_id)
        self.server_base.setText(str(p.get("server_base_path") or ""))
        self.server_name.setText(str(p.get("server_project_name") or self._project_id))
        self.server_branch.setText(str(p.get("server_git_branch") or "master"))
        self.server_alias.setText(str(p.get("server_remote_alias") or ""))
        self.source_url.setText(str(p.get("source_git_url") or ""))
        self.secrets_file_path.setText(str(p.get("secrets_file_path") or ""))
        self.auto_sync.setChecked(bool(p.get("auto_sync_enabled")))
        self.merge_global_cmds.setChecked(bool(p.get("merge_global_commands")))
        self.rsc_override.setText(str(p.get("remote_server_core") or ""))
        self.bs_override.setText(str(p.get("boss_server") or ""))
        self.p_host.setText(str(p.get("ssh_host") or ""))
        self.p_port.setText(str(p.get("ssh_port") or ""))
        self.p_work.setText(str(p.get("ssh_work_dir") or ""))
        self.p_restart.setText(str(p.get("ssh_restart_command") or ""))
        to = int(p.get("ssh_command_timeout_sec") or 0)
        self.p_timeout.setValue(to if to > 0 else 0)
        self.pre_init.set_commands(list(p.get("pre_init_commands") or []))
        self.post_init.set_commands(list(p.get("post_init_commands") or []))
        self.pre_deploy.set_commands(list(p.get("pre_deploy_commands") or []))
        self.post_deploy.set_commands(list(p.get("post_deploy_commands") or []))
        core = project_dir(self._project_id) / "project_core"
        raw_paths = list(p.get("core_sync_paths") or [])
        cleaned_paths = collapse_stale_build_artifacts(core, raw_paths)
        if cleaned_paths != raw_paths:
            p = dict(p)
            p["core_sync_paths"] = cleaned_paths
            save_project(self._project_id, p)
        self._populate_tree(set(cleaned_paths))
        self._update_paths_label()
        self._loading = False
        self._reload_secrets_file(show_success=False)

    def _msg(self, icon: QMessageBox.Icon, text: str) -> None:
        themed_message_box(self, icon, tr(self._main.current_locale(), "dlg_crm_title"), text)

    def _confirm(self, message_key: str, *, accept_key: str = "btn_continue") -> bool:
        loc = self._main.current_locale()
        box = QMessageBox(
            QMessageBox.Icon.Question,
            tr(loc, "dlg_crm_title"),
            tr(loc, message_key),
            QMessageBox.StandardButton.NoButton,
            self,
        )
        box.setStyleSheet(DIALOG_STYLE)
        accept = box.addButton(tr(loc, accept_key), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr(loc, "btn_cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is accept

    def _resolve_clone_url(self, raw: str) -> str | None:
        """URL для git clone; None — пользователь отменил."""
        loc = self._main.current_locale()
        token = extract_git_url_token(raw)
        if token:
            return token
        box = QMessageBox(
            QMessageBox.Icon.Warning,
            tr(loc, "dlg_crm_title"),
            tr(loc, "msg_clone_url_no_git_token"),
            QMessageBox.StandardButton.NoButton,
            self,
        )
        box.setStyleSheet(DIALOG_STYLE)
        ignore = box.addButton(tr(loc, "btn_ignore"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr(loc, "btn_cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is ignore:
            return raw
        return None

    def _save_clicked(self) -> None:
        save_project(self._project_id, self._collect())
        self._main.show_saved_toast()
        self._msg(QMessageBox.Icon.Information, tr(self._main.current_locale(), "msg_saved_project"))

    def _update_paths_label(self) -> None:
        cfg = effective_ssh_config(self._project_id, project_dir(self._project_id))
        loc = self._main.current_locale()
        self._paths_label.setText(
            f"{tr(loc, 'paths_source')} <code>{cfg['remote_server_core_path']}</code><br>"
            f"{tr(loc, 'paths_boss')} <code>{cfg['boss_server_path']}</code>"
        )

    def _refresh_core_tab_visibility(self) -> None:
        has = project_core_has_content(self._project_id)
        self._tabs.setTabVisible(self._tab_core_index, has)

    def _populate_tree(self, selected: set[str]) -> None:
        core = project_dir(self._project_id) / "project_core"
        cleaned = set(collapse_stale_build_artifacts(core, list(selected)))
        self._tree.blockSignals(True)
        try:
            populate_core_tree(self._tree, core, cleaned)
        finally:
            self._tree.blockSignals(False)

    def _selected_tree_paths(self) -> list[str]:
        core = project_dir(self._project_id) / "project_core"
        return collapse_stale_build_artifacts(core, collect_checked_paths(self._tree))

    def _select_all_tree(self) -> None:
        set_all_checked(self._tree, True)

    def _run_operation(self, title: str, job, *, refresh_core: bool = False) -> None:
        def after() -> None:
            if refresh_core:
                self._refresh_core_tab_visibility()
                p = load_project(self._project_id)
                self._populate_tree(set(p.get("core_sync_paths") or []))

        OperationRunner.run(
            self._main,
            title,
            job,
            block_widgets=[self],
            on_finished=after if refresh_core else None,
        )

    def _apply_core_copy(self) -> None:
        save_project(self._project_id, self._collect())
        cfg = effective_ssh_config(self._project_id, project_dir(self._project_id))
        paths = self._selected_tree_paths()
        loc = self._main.current_locale()
        if not paths:
            self._msg(QMessageBox.Icon.Warning, tr(loc, "msg_no_paths_selected"))
            return

        def job(log, cancel):
            err = copy_core_paths_to_targets(
                cfg["project_core_path"],
                paths,
                cfg["remote_server_core_path"],
                cfg["boss_server_path"],
            )
            if err:
                return False, err
            return True, tr(loc, "msg_core_copied")

        self._run_operation(tr(loc, "op_title_apply_core"), job)

    # --- secret markers ---------------------------------------------------

    def _collect_commands_for_scan(
        self,
        list_keys: list[str],
        *,
        include_restart: bool = False,
    ) -> list[str]:
        """Собирает все команды из указанных списков для сканирования маркеров."""
        save_project(self._project_id, self._collect())
        result: list[str] = []
        for key in list_keys:
            result.extend(merge_command_lists(self._project_id, key))
        if include_restart:
            cfg = effective_ssh_config(self._project_id, project_dir(self._project_id))
            restart = build_ssh_restart_command(cfg)
            if restart.strip() and restart.strip() != "true":
                result.append(restart)
        return result

    def _reload_secrets_file(self, *, show_success: bool) -> bool:
        """Читает файл по пути в поле; обновляет ``_secrets_from_file``. True — файл прочитан."""
        loc = self._main.current_locale()
        path_s = self.secrets_file_path.text().strip()
        if not path_s:
            self._secrets_from_file = {}
            if show_success:
                self._msg(QMessageBox.Icon.Information, tr(loc, "msg_secrets_no_path"))
            return False
        path = Path(path_s)
        if not path.is_file():
            self._secrets_from_file = {}
            if show_success:
                self._msg(
                    QMessageBox.Icon.Warning,
                    tr(loc, "msg_secrets_file_missing", path=path_s),
                )
            return False
        try:
            secrets, warnings = load_secrets_file(path)
        except OSError:
            self._secrets_from_file = {}
            if show_success:
                self._msg(
                    QMessageBox.Icon.Warning,
                    tr(loc, "msg_secrets_file_missing", path=path_s),
                )
            return False
        self._secrets_from_file = secrets
        if show_success:
            if warnings:
                self._msg(
                    QMessageBox.Icon.Warning,
                    tr(
                        loc,
                        "msg_secrets_parse_warnings",
                        count=len(secrets),
                        warnings="\n".join(warnings),
                    ),
                )
            else:
                self._msg(
                    QMessageBox.Icon.Information,
                    tr(loc, "msg_secrets_loaded", count=len(secrets)),
                )
        return True

    def _on_secrets_browse(self) -> None:
        loc = self._main.current_locale()
        start = self.secrets_file_path.text().strip() or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr(loc, "lbl_secrets_file"),
            start,
            tr(loc, "dlg_secrets_file_filter"),
        )
        if not path:
            return
        self.secrets_file_path.setText(path)
        self._schedule_autosave()
        self._reload_secrets_file(show_success=True)

    def _on_secrets_refresh(self) -> None:
        loc = self._main.current_locale()
        if not self.secrets_file_path.text().strip():
            self._msg(QMessageBox.Icon.Information, tr(loc, "msg_secrets_no_path"))
            return
        self._reload_secrets_file(show_success=True)

    def _prompt_missing_secrets(self, markers: list[str]) -> dict[str, str] | None:
        """Запрашивает значения только для переданных имён маркеров."""
        if not markers:
            return {}
        loc = self._main.current_locale()
        secrets: dict[str, str] = {}
        for name in markers:
            text, ok = QInputDialog.getText(
                self,
                tr(loc, "secret_input_title"),
                tr(loc, "secret_input_label", marker=name),
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                self._msg(QMessageBox.Icon.Information, tr(loc, "secret_cancelled"))
                return None
            secrets[name] = text
        return secrets

    def _resolve_secrets(self, commands: list[str]) -> dict[str, str] | None:
        """Файл секретов (RAM) → алерты для недостающих маркеров."""
        markers = extract_markers(commands)
        if not markers:
            return {}

        loc = self._main.current_locale()
        path_s = self.secrets_file_path.text().strip()
        if path_s and not Path(path_s).is_file():
            self._msg(
                QMessageBox.Icon.Warning,
                tr(loc, "warn_secrets_file_missing_on_op", path=path_s),
            )
            self._secrets_from_file = {}

        secrets: dict[str, str] = {}
        missing: list[str] = []
        for name in markers:
            val = self._secrets_from_file.get(name, "")
            if val:
                secrets[name] = val
            else:
                missing.append(name)

        if not missing:
            return secrets

        prompted = self._prompt_missing_secrets(missing)
        if prompted is None:
            return None
        secrets.update(prompted)
        return secrets

    # --- end secret markers ------------------------------------------------

    def _on_clone(self) -> None:
        save_project(self._project_id, self._collect())
        raw = self.source_url.text().strip()
        loc = self._main.current_locale()
        if not raw:
            self._msg(QMessageBox.Icon.Warning, tr(loc, "err_clone_url_empty"))
            return
        url = self._resolve_clone_url(raw)
        if not url:
            return
        if project_core_has_git(self._project_id):
            if not self._confirm("msg_clone_existing_git"):
                return
        if project_core_has_content(self._project_id):
            if not self._confirm("msg_clone_replace"):
                return

        def job(log, cancel):
            return clone_into_project_core(self._project_id, url, log=log, cancel=cancel)

        self._run_operation(tr(loc, "op_title_clone"), job, refresh_core=True)

    def _confirm_server_init_recreate(self, paths: list[str]) -> bool:
        """True — пересоздать на сервере; False — отмена."""
        loc = self._main.current_locale()
        text = tr(loc, "msg_init_server_exists", paths="\n".join(paths))
        box = QMessageBox(
            QMessageBox.Icon.Warning,
            tr(loc, "dlg_crm_title"),
            text,
            QMessageBox.StandardButton.NoButton,
            self,
        )
        box.setStyleSheet(DIALOG_STYLE)
        recreate = box.addButton(tr(loc, "btn_recreate"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(tr(loc, "btn_cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is recreate:
            return True
        return False

    def _on_init(self) -> None:
        save_project(self._project_id, self._collect())
        loc = self._main.current_locale()
        cfg = effective_ssh_config(self._project_id, project_dir(self._project_id))
        ok, err = validate_deploy_ssh(cfg)
        if not ok:
            self._msg(
                QMessageBox.Icon.Warning,
                tr(loc, "err_ssh_host_required") if err == "host_empty" else tr(loc, "err_ssh_port_invalid"),
            )
            return
        if not (cfg.get("server_base_path") or "").strip():
            self._msg(QMessageBox.Icon.Warning, tr(loc, "err_server_base_empty"))
            return

        probe_ok, existing, probe_err = probe_server_init_paths(cfg, CancelToken())
        if not probe_ok:
            self._msg(QMessageBox.Icon.Warning, tr(loc, "msg_init_server_probe_failed", detail=probe_err))
            return
        recreate_remote = False
        if existing:
            if not self._confirm_server_init_recreate(existing):
                return
            recreate_remote = True

        warn = boss_server_bind_warning(cfg["boss_server_path"])
        if warn:
            box = QMessageBox(QMessageBox.Icon.Question, tr(loc, "dlg_crm_title"), warn, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self)
            box.setStyleSheet(DIALOG_STYLE)
            if box.exec() != QMessageBox.StandardButton.Yes:
                return

        recreate_flag = recreate_remote

        cmds = self._collect_commands_for_scan(["pre_init_commands", "post_init_commands"])
        secrets = self._resolve_secrets(cmds)
        if secrets is None:
            return

        def job(log, cancel):
            safe_log = make_masked_log(log, secrets)
            return run_server_init_job(
                self._project_id,
                safe_log,
                cancel,
                recreate_remote=recreate_flag,
                secrets=secrets,
            )

        self._run_operation(tr(loc, "op_title_init"), job)

    def _on_deploy(self) -> None:
        save_project(self._project_id, self._collect())
        loc = self._main.current_locale()
        cfg = effective_ssh_config(self._project_id, project_dir(self._project_id))
        ok, err = validate_deploy_ssh(cfg)
        if not ok:
            self._msg(
                QMessageBox.Icon.Warning,
                tr(loc, "err_ssh_host_required") if err == "host_empty" else tr(loc, "err_ssh_port_invalid"),
            )
            return

        cmds = self._collect_commands_for_scan(
            ["pre_deploy_commands", "post_deploy_commands"],
            include_restart=True,
        )
        secrets = self._resolve_secrets(cmds)
        if secrets is None:
            return

        def job(log, cancel):
            safe_log = make_masked_log(log, secrets)
            return run_deploy_job(self._project_id, safe_log, cancel, secrets=secrets)

        self._run_operation(tr(loc, "op_title_deploy"), job)

    def _on_test_pre_deploy(self) -> None:
        save_project(self._project_id, self._collect())
        loc = self._main.current_locale()
        cfg = effective_ssh_config(self._project_id, project_dir(self._project_id))
        ok, err = validate_deploy_ssh(cfg)
        if not ok:
            self._msg(
                QMessageBox.Icon.Warning,
                tr(loc, "err_ssh_host_required") if err == "host_empty" else tr(loc, "err_ssh_port_invalid"),
            )
            return

        cmds = self._collect_commands_for_scan(["pre_deploy_commands"])
        secrets = self._resolve_secrets(cmds)
        if secrets is None:
            return

        def job(log, cancel):
            safe_log = make_masked_log(log, secrets)
            return run_merged_command_list(
                self._project_id,
                "pre_deploy_commands",
                cfg,
                safe_log,
                cancel,
                local_cwd=project_dir(self._project_id),
                secrets=secrets,
            )

        self._run_operation(tr(loc, "op_title_test_pre_deploy"), job)

    def apply_language(self) -> None:
        loc = self._main.current_locale()
        self.setWindowTitle(tr(loc, "dlg_project_settings_title", id=self._project_id))
        self._tabs.setTabText(0, tr(loc, "tab_settings"))
        self._tabs.setTabText(self._tab_core_index, tr(loc, "tab_from_core"))
        self._lbl_server_base.setText(tr(loc, "lbl_server_base"))
        self._lbl_server_name.setText(tr(loc, "lbl_server_project_name"))
        self._lbl_server_branch.setText(tr(loc, "lbl_server_git_branch"))
        self._lbl_server_alias.setText(tr(loc, "lbl_server_remote_alias"))
        self._lbl_source_url.setText(tr(loc, "lbl_source_git_url"))
        self.btn_clone.setText(tr(loc, "btn_clone"))
        self._lbl_secrets_file.setText(tr(loc, "lbl_secrets_file"))
        self.btn_secrets_browse.setText(tr(loc, "btn_secrets_browse"))
        self.btn_secrets_refresh.setToolTip(tr(loc, "tooltip_secrets_refresh"))
        self.auto_sync.setText(tr(loc, "chk_auto_sync"))
        self.merge_global_cmds.setText(tr(loc, "chk_merge_global_commands"))
        self._lbl_rsc.setText(tr(loc, "lbl_rsc"))
        self._lbl_bs.setText(tr(loc, "lbl_bs"))
        self._lbl_ph.setText(tr(loc, "lbl_p_host"))
        self._lbl_pp.setText(tr(loc, "lbl_p_port"))
        self._lbl_pw.setText(tr(loc, "lbl_p_work"))
        self._lbl_prs.setText(tr(loc, "lbl_p_restart"))
        self._lbl_pto.setText(tr(loc, "lbl_p_timeout"))
        self.p_timeout.setSpecialValueText(tr(loc, "spin_timeout_use_global"))
        self._lbl_pre_init.setText(tr(loc, "lbl_pre_init_cmds"))
        self._lbl_post_init.setText(tr(loc, "lbl_post_init_cmds"))
        self._lbl_pre_deploy.setText(tr(loc, "lbl_pre_deploy_cmds"))
        self._lbl_post_deploy.setText(tr(loc, "lbl_post_deploy_cmds"))
        self.btn_init.setText(tr(loc, "btn_init_server"))
        self.btn_deploy.setText(tr(loc, "btn_deploy"))
        self.btn_save.setText(tr(loc, "btn_save_project"))
        self.btn_select_all.setText(tr(loc, "btn_select_all"))
        self.btn_apply_core.setText(tr(loc, "btn_apply_core"))
        self.btn_test_pre_deploy.setText(tr(loc, "btn_test_pre_deploy"))
        self._lbl_cmd_hint.setText(
            tr(
                loc,
                "hint_command_lists",
                local_sh_prefix=LOCAL_SH_PREFIX,
                local_prefix=LOCAL_PREFIX,
                server_sh_prefix=SERVER_SH_PREFIX,
                server_prefix=SERVER_PREFIX,
            )
        )
        self._update_paths_label()

    def mark_ssh_field_error(self, host: bool, port: bool) -> None:
        style_ssh_field(self.p_host, host)
        style_ssh_field(self.p_port, port)

    def clear_ssh_field_error(self) -> None:
        style_ssh_field(self.p_host, False)
        style_ssh_field(self.p_port, False)
