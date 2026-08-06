"""Запуск длительных операций: блокировка MainWindow, модалка лога, отмена."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QWidget

from crm.gui.operation_log_dialog import OperationLogDialog
from crm.gui.theme import themed_message_box
from crm.i18n import tr
from crm.operation_cancel import CancelToken, OperationCancelledError

if TYPE_CHECKING:
    from crm.gui.main_window import MainWindow

logger = logging.getLogger(__name__)

JobFn = Callable[[Callable[[str, str], None], CancelToken], tuple[bool, str]]


class _JobThread(QThread):
    finished_result = pyqtSignal(bool, str)

    def __init__(self, fn: JobFn, cancel: CancelToken, log_fn: Callable[[str, str], None]):
        super().__init__()
        self._fn = fn
        self._cancel = cancel
        self._log_fn = log_fn

    def run(self) -> None:
        try:
            ok, msg = self._fn(self._log_fn, self._cancel)
            self.finished_result.emit(ok, msg)
        except OperationCancelledError:
            self.finished_result.emit(False, "cancelled")
        except Exception as e:
            logger.exception("JobThread")
            self.finished_result.emit(False, str(e))


class OperationRunner:
    _busy = False
    _current_title = ""

    @classmethod
    def is_busy(cls) -> bool:
        return cls._busy

    @classmethod
    def run(
        cls,
        main_window: "MainWindow",
        title: str,
        job: JobFn,
        *,
        block_widgets: list[QWidget] | None = None,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        if cls._busy:
            loc = main_window.current_locale()
            themed_message_box(
                main_window,
                QMessageBox.Icon.Warning,
                tr(loc, "dlg_crm_title"),
                tr(loc, "op_busy_already", title=cls._current_title),
            )
            return

        loc = main_window.current_locale()
        dlg = OperationLogDialog(title, main_window)
        dlg.set_ui_texts(
            status_running=tr(loc, "op_status_running"),
            status_stopping=tr(loc, "op_status_stopping"),
            status_done=tr(loc, "op_status_done"),
            status_cancelled=tr(loc, "op_status_cancelled"),
            copy_all=tr(loc, "op_log_copy_all"),
            copy_selection=tr(loc, "op_log_copy_selection"),
            export_log=tr(loc, "op_log_export"),
            stop=tr(loc, "op_log_stop"),
            close=tr(loc, "op_log_close"),
        )

        cancel = CancelToken()
        cls._busy = True
        cls._current_title = title
        main_window.setEnabled(False)
        dlg.setEnabled(True)
        main_window.set_busy_overlay(True, tr(loc, "progress_busy"))
        main_window.set_progress(True)
        blocked = block_widgets or []
        for w in blocked:
            w.setEnabled(False)

        def log_append(text: str, level: str = "info") -> None:
            dlg.log_line.emit(text, level)

        def on_stop() -> None:
            cancel.request_cancel()
            dlg.mark_stopping()
            log_append(tr(loc, "op_log_cancel_requested"), "warn")

        dlg.set_stop_handler(on_stop)

        thread = _JobThread(job, cancel, log_append)

        def on_done(ok: bool, msg: str) -> None:
            cancelled = msg == "cancelled"
            if cancelled:
                log_append(tr(loc, "op_log_cancelled"), "warn")
            elif ok:
                log_append(tr(loc, "log_ok") + msg, "info")
            else:
                log_append(tr(loc, "log_err") + msg, "error")
            dlg.mark_finished(cancelled=cancelled)
            thread.deleteLater()

        thread.finished_result.connect(on_done)
        thread.start()
        dlg.exec()
        cls._busy = False
        cls._current_title = ""
        main_window.set_busy_overlay(False)
        main_window.setEnabled(True)
        main_window.set_progress(False)
        for w in blocked:
            w.setEnabled(True)
        if on_finished:
            on_finished()
