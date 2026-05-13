"""Стандартная вкладка «Настройки» проекта: форма, пути, деплой, лог."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable

from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from crm.config_store import (
    GLOBAL_DEFAULTS,
    effective_ssh_config,
    load_project,
    save_project,
    validate_deploy_ssh,
)
from crm.i18n import tr
from crm.paths import project_dir
from crm.ssh_ops import ssh_restart_from_config
from crm.sync_deploy import sync_and_push

logger = logging.getLogger(__name__)

COMMON_EDIT_STYLE = """
QLineEdit, QSpinBox {
    padding: 4px 6px;
    border: 1px solid #5D6D7E;
    border-radius: 3px;
    background-color: #2C3E50;
    color: #ECF0F1;
    min-height: 22px;
}
"""

ERROR_EDIT_STYLE = """
QLineEdit, QSpinBox {
    padding: 4px 6px;
    border: 2px solid #E74C3C;
    border-radius: 3px;
    background-color: #2C3E50;
    color: #ECF0F1;
    min-height: 22px;
}
"""


def style_ssh_field(w: QLineEdit | QSpinBox, error: bool) -> None:
    w.setStyleSheet(ERROR_EDIT_STYLE if error else COMMON_EDIT_STYLE)


class OpWorker(QThread):
    finished_msg = pyqtSignal(bool, str)

    def __init__(self, fn: Callable[[], tuple[bool, str]], parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            ok, msg = self._fn()
            self.finished_msg.emit(ok, msg)
        except Exception as e:
            logger.exception("OpWorker")
            self.finished_msg.emit(False, str(e))


class ProjectSettingsCore(QWidget):
    """Форма профиля проекта, пути, кнопки Sync/SSH, лог операций."""

    def __init__(self, project_id: str, main_window: Any, parent=None):
        super().__init__(parent)
        self._project_id = project_id
        self._main = main_window
        self._worker: OpWorker | None = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(500)
        self._debounce.timeout.connect(self._flush_autosave)

        self.setStyleSheet("QWidget { background-color: #1C2833; } QLabel { color: #BDC3C7; }")
        s_layout = QVBoxLayout(self)
        form = QFormLayout()
        self.rsc_override = QLineEdit()
        self.bs_override = QLineEdit()
        self.p_host = QLineEdit()
        self.p_port = QLineEdit()
        self.p_work = QLineEdit()
        self.p_remote = QLineEdit()
        self.p_branch = QLineEdit()
        self.p_restart = QLineEdit()
        self.p_timeout = QSpinBox()
        self.p_timeout.setRange(0, 3600)
        self._lbl_rsc = QLabel()
        self._lbl_bs = QLabel()
        self._lbl_ph = QLabel()
        self._lbl_pp = QLabel()
        self._lbl_pw = QLabel()
        self._lbl_pr = QLabel()
        self._lbl_pb = QLabel()
        self._lbl_prs = QLabel()
        self._lbl_pto = QLabel()
        for lbl in (
            self._lbl_rsc,
            self._lbl_bs,
            self._lbl_ph,
            self._lbl_pp,
            self._lbl_pw,
            self._lbl_pr,
            self._lbl_pb,
            self._lbl_prs,
            self._lbl_pto,
        ):
            lbl.setWordWrap(True)
        for w in (
            self.rsc_override,
            self.bs_override,
            self.p_host,
            self.p_port,
            self.p_work,
            self.p_remote,
            self.p_branch,
            self.p_restart,
        ):
            w.setStyleSheet(COMMON_EDIT_STYLE)
        self.p_timeout.setStyleSheet(COMMON_EDIT_STYLE)
        form.addRow(self._lbl_rsc, self.rsc_override)
        form.addRow(self._lbl_bs, self.bs_override)
        form.addRow(self._lbl_ph, self.p_host)
        form.addRow(self._lbl_pp, self.p_port)
        form.addRow(self._lbl_pw, self.p_work)
        form.addRow(self._lbl_pr, self.p_remote)
        form.addRow(self._lbl_pb, self.p_branch)
        form.addRow(self._lbl_prs, self.p_restart)
        form.addRow(self._lbl_pto, self.p_timeout)
        s_layout.addLayout(form)

        paths = QLabel()
        paths.setWordWrap(True)
        paths.setStyleSheet("color: #7F8C8D; font-size: 11px;")
        self._paths_label = paths
        s_layout.addWidget(paths)

        btn_row = QHBoxLayout()
        self.btn_save = QPushButton()
        self.btn_sync = QPushButton()
        self.btn_ssh = QPushButton()
        for b in (self.btn_save, self.btn_sync, self.btn_ssh):
            b.setStyleSheet(
                "QPushButton { background-color: #3498DB; color: white; padding: 6px 10px; border-radius: 4px; }"
                "QPushButton:disabled { background-color: #7F8C8D; }"
            )
        self.btn_save.clicked.connect(self._save_project_clicked)
        self.btn_sync.clicked.connect(self._run_sync)
        self.btn_ssh.clicked.connect(self._run_ssh)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_sync)
        btn_row.addWidget(self.btn_ssh)
        s_layout.addLayout(btn_row)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(120)
        self.log.setStyleSheet(
            "QTextEdit { background: #273746; color: #ECF0F1; border: 1px solid #34495E; font-family: monospace; }"
        )
        self._log_caption = QLabel()
        s_layout.addWidget(self._log_caption)
        s_layout.addWidget(self.log)

        for w in (
            self.rsc_override,
            self.bs_override,
            self.p_host,
            self.p_port,
            self.p_work,
            self.p_remote,
            self.p_branch,
            self.p_restart,
        ):
            w.textChanged.connect(self._schedule_autosave)
        self.p_timeout.valueChanged.connect(self._schedule_autosave)
        self.p_host.textChanged.connect(self._on_ssh_field_edited)
        self.p_port.textChanged.connect(self._on_ssh_field_edited)

        self._load_profile(block_signals=True)
        self._update_paths_label()
        self.apply_language()

    def _on_ssh_field_edited(self) -> None:
        self._main.clear_ssh_error_marks()

    def _schedule_autosave(self) -> None:
        self._debounce.start()

    def _flush_autosave(self) -> None:
        save_project(self._project_id, self._collect_updates())
        self._update_paths_label()
        self._main.show_saved_toast()

    def _collect_updates(self) -> dict:
        return {
            "remote_server_core": self.rsc_override.text().strip(),
            "boss_server": self.bs_override.text().strip(),
            "ssh_host": self.p_host.text().strip(),
            "ssh_port": self.p_port.text().strip(),
            "ssh_work_dir": self.p_work.text().strip(),
            "ssh_git_remote": self.p_remote.text().strip(),
            "ssh_git_branch": self.p_branch.text().strip(),
            "ssh_restart_command": self.p_restart.text().strip(),
            "ssh_command_timeout_sec": int(self.p_timeout.value()),
        }

    def _root(self):
        return project_dir(self._project_id)

    def _log(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[{ts}] {text}")

    def _load_profile(self, block_signals: bool = False) -> None:
        widgets = (
            self.rsc_override,
            self.bs_override,
            self.p_host,
            self.p_port,
            self.p_work,
            self.p_remote,
            self.p_branch,
            self.p_restart,
            self.p_timeout,
        )
        if block_signals:
            for w in widgets:
                w.blockSignals(True)
        p = load_project(self._project_id)
        self.rsc_override.setText(str(p.get("remote_server_core") or ""))
        self.bs_override.setText(str(p.get("boss_server") or ""))
        self.p_host.setText(str(p.get("ssh_host") or ""))
        self.p_port.setText(str(p.get("ssh_port") or ""))
        self.p_work.setText(str(p.get("ssh_work_dir") or ""))
        self.p_remote.setText(str(p.get("ssh_git_remote") or ""))
        self.p_branch.setText(str(p.get("ssh_git_branch") or ""))
        self.p_restart.setText(str(p.get("ssh_restart_command") or ""))
        to = int(p.get("ssh_command_timeout_sec") or 0)
        self.p_timeout.setValue(to if to > 0 else 0)
        if block_signals:
            for w in widgets:
                w.blockSignals(False)

    def _save_project_clicked(self) -> None:
        save_project(self._project_id, self._collect_updates())
        self._update_paths_label()
        loc = self._main.current_locale()
        self._log(tr(loc, "log_profile_saved"))
        QMessageBox.information(self, tr(loc, "dlg_crm_title"), tr(loc, "msg_saved_project"))

    def apply_language(self) -> None:
        loc = self._main.current_locale()
        self._lbl_rsc.setText(tr(loc, "lbl_rsc"))
        self._lbl_bs.setText(tr(loc, "lbl_bs"))
        self._lbl_ph.setText(tr(loc, "lbl_p_host"))
        self._lbl_pp.setText(tr(loc, "lbl_p_port"))
        self._lbl_pw.setText(tr(loc, "lbl_p_work"))
        self._lbl_pr.setText(tr(loc, "lbl_p_remote"))
        self._lbl_pb.setText(tr(loc, "lbl_p_branch"))
        self._lbl_prs.setText(tr(loc, "lbl_p_restart"))
        self._lbl_pto.setText(tr(loc, "lbl_p_timeout"))
        self.p_timeout.setSpecialValueText(tr(loc, "spin_timeout_use_global"))

        self.btn_save.setText(tr(loc, "btn_save_project"))
        self.btn_sync.setText(tr(loc, "btn_sync"))
        self.btn_ssh.setText(tr(loc, "btn_ssh"))
        self._log_caption.setText(tr(loc, "log_caption"))
        self.rsc_override.setToolTip(tr(loc, "tt_rsc"))
        self.bs_override.setToolTip(tr(loc, "tt_bs"))
        self.p_host.setToolTip(tr(loc, "tt_p_host"))
        self.p_port.setToolTip(tr(loc, "tt_p_port"))
        self.p_work.setToolTip(tr(loc, "tt_p_work"))
        self.p_remote.setToolTip(tr(loc, "tt_p_remote"))
        self.p_branch.setToolTip(tr(loc, "tt_p_branch"))
        self.p_restart.setToolTip(tr(loc, "tt_p_restart"))
        self.p_timeout.setToolTip(tr(loc, "tt_p_timeout"))
        self.btn_save.setToolTip(tr(loc, "tt_btn_save_project"))
        self.btn_sync.setToolTip(tr(loc, "tt_btn_sync"))
        self.btn_ssh.setToolTip(tr(loc, "tt_btn_ssh"))
        self._update_paths_label()

    def _update_paths_label(self) -> None:
        cfg = effective_ssh_config(self._project_id, self._root())
        loc = self._main.current_locale()
        self._paths_label.setText(
            f"{tr(loc, 'paths_source')} <code>{cfg['remote_server_core_path']}</code><br>"
            f"{tr(loc, 'paths_boss')} <code>{cfg['boss_server_path']}</code>"
        )

    def mark_ssh_field_error(self, host: bool, port: bool) -> None:
        style_ssh_field(self.p_host, host)
        style_ssh_field(self.p_port, port)

    def clear_ssh_field_error(self) -> None:
        style_ssh_field(self.p_host, False)
        style_ssh_field(self.p_port, False)

    def _busy(self, busy: bool) -> None:
        self.btn_sync.setEnabled(not busy)
        self.btn_ssh.setEnabled(not busy)
        self.btn_save.setEnabled(not busy)
        self._main.set_progress(busy)

    def _run_sync(self) -> None:
        cfg = effective_ssh_config(self._project_id, self._root())
        src = cfg["remote_server_core_path"]
        dst = cfg["boss_server_path"]
        loc = self._main.current_locale()
        self._log(tr(loc, "log_sync", src=src, dst=dst))

        def job():
            return sync_and_push(src, dst)

        self._start_worker(job)

    def _run_ssh(self) -> None:
        cfg = effective_ssh_config(self._project_id, self._root())
        loc = self._main.current_locale()
        ok, err = validate_deploy_ssh(cfg)
        if not ok:
            self._main.clear_ssh_error_marks()
            if err == "host_empty":
                QMessageBox.warning(self, tr(loc, "dlg_crm_title"), tr(loc, "err_ssh_host_required"))
                self._main.set_ssh_deploy_error_marks(host=True, project_id=self._project_id)
            else:
                QMessageBox.warning(self, tr(loc, "dlg_crm_title"), tr(loc, "err_ssh_port_invalid"))
                self._main.set_ssh_deploy_error_marks(port=True, project_id=self._project_id)
            return

        def job():
            return ssh_restart_from_config(cfg)

        self._log(tr(loc, "log_ssh_start"))
        self._start_worker(job)

    def _start_worker(self, fn: Callable[[], tuple[bool, str]]) -> None:
        if self._worker and self._worker.isRunning():
            loc = self._main.current_locale()
            self._log(tr(loc, "log_wait_op"))
            return
        self._busy(True)
        self._worker = OpWorker(fn, self)
        self._worker.finished_msg.connect(self._on_op_done)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_op_done(self, ok: bool, msg: str) -> None:
        self._busy(False)
        loc = self._main.current_locale()
        self._log((tr(loc, "log_ok") if ok else tr(loc, "log_err")) + msg)
        title = tr(loc, "dlg_crm_title")
        if ok:
            QMessageBox.information(self, title, msg)
        else:
            QMessageBox.critical(self, title, msg)
