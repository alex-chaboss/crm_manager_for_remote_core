"""Модальное окно лога операции (clone, init, deploy, SSH)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from crm.gui.theme import BTN_DANGER, BTN_PRIMARY, BTN_SUCCESS, DIALOG_STYLE, LOG_VIEW_STYLE, TEXT_MUTED


class OperationLogDialog(QDialog):
    log_line = pyqtSignal(str, str)

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(640, 420)
        self.setStyleSheet(DIALOG_STYLE)
        self._running = True
        self._stopping = False
        self._status_running_text = ""
        self._status_stopping_text = ""
        self._status_done_text = ""
        self._status_cancelled_text = ""
        self._copy_selection_text = "Копировать выделение"
        self._export_text = "Сохранить в файл…"

        layout = QVBoxLayout(self)
        self._status = QLabel()
        self._status.setStyleSheet(f"color: {TEXT_MUTED};")
        layout.addWidget(self._status)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._log.setStyleSheet(LOG_VIEW_STYLE)
        layout.addWidget(self._log, stretch=1)

        row = QHBoxLayout()
        self._btn_copy = QPushButton()
        self._btn_copy.clicked.connect(self._copy_all)
        row.addWidget(self._btn_copy)

        self._btn_copy_sel = QPushButton()
        self._btn_copy_sel.clicked.connect(self._copy_selection)
        row.addWidget(self._btn_copy_sel)

        self._btn_export = QPushButton()
        self._btn_export.clicked.connect(self._export_log)
        row.addWidget(self._btn_export)

        self._btn_stop = QPushButton()
        row.addWidget(self._btn_stop)

        row.addStretch()
        self._btn_close = QPushButton()
        self._btn_close.clicked.connect(self.accept)
        row.addWidget(self._btn_close)

        layout.addLayout(row)
        self.log_line.connect(self._append_line)
        self._sync_action_buttons()

    def _sync_action_buttons(self) -> None:
        """Состояние и цвет кнопок: во время процесса — синие/красный стоп; после — серый стоп, зелёное закрыть."""
        running = self._running and not self._stopping
        self._btn_copy.setEnabled(True)
        self._btn_copy_sel.setEnabled(True)
        self._btn_export.setEnabled(True)
        self._btn_copy.setStyleSheet(BTN_PRIMARY)
        self._btn_copy_sel.setStyleSheet(BTN_PRIMARY)
        self._btn_export.setStyleSheet(BTN_PRIMARY)

        if running:
            self._btn_stop.setEnabled(True)
            self._btn_stop.setStyleSheet(BTN_DANGER)
            self._btn_close.setEnabled(False)
            self._btn_close.setStyleSheet(BTN_PRIMARY)
        else:
            self._btn_stop.setEnabled(False)
            self._btn_stop.setStyleSheet(BTN_PRIMARY)
            self._btn_close.setEnabled(True)
            self._btn_close.setStyleSheet(BTN_SUCCESS)

    def set_stop_handler(self, handler) -> None:
        self._btn_stop.clicked.connect(handler)

    def _append_line(self, text: str, level: str) -> None:
        prefix = ""
        if level == "error":
            prefix = "[ERROR] "
        elif level == "warn":
            prefix = "[WARN] "
        for line in text.splitlines() or [""]:
            self._log.appendPlainText(prefix + line)

    def _clipboard(self):
        return QApplication.clipboard()

    def _copy_all(self) -> None:
        self._clipboard().setText(self._log.toPlainText())

    def _copy_selection(self) -> None:
        cursor = self._log.textCursor()
        if not cursor.hasSelection():
            return
        text = cursor.selectedText().replace("\u2029", "\n")
        self._clipboard().setText(text)

    def _export_log(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default = str(Path.home() / f"crm_operation_{stamp}.log")
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._export_text,
            default,
            "Log (*.log);;Text (*.txt);;All (*)",
        )
        if path:
            Path(path).write_text(self._log.toPlainText(), encoding="utf-8")

    def set_ui_texts(
        self,
        *,
        status_running: str,
        status_stopping: str,
        status_done: str,
        status_cancelled: str,
        copy_all: str,
        copy_selection: str,
        export_log: str,
        stop: str,
        close: str,
    ) -> None:
        self._status_running_text = status_running
        self._status_stopping_text = status_stopping
        self._status_done_text = status_done
        self._status_cancelled_text = status_cancelled
        self._btn_copy.setText(copy_all)
        self._btn_copy_sel.setText(copy_selection)
        self._export_text = export_log
        self._btn_export.setText(export_log)
        self._btn_stop.setText(stop)
        self._btn_close.setText(close)
        self._status.setText(status_running)

    def mark_stopping(self) -> None:
        self._stopping = True
        self._sync_action_buttons()
        self._status.setText(self._status_stopping_text)

    def mark_finished(self, *, cancelled: bool = False) -> None:
        self._running = False
        self._stopping = False
        self._sync_action_buttons()
        self._status.setText(self._status_cancelled_text if cancelled else self._status_done_text)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._running and not self._stopping:
            event.ignore()
            return
        super().closeEvent(event)
