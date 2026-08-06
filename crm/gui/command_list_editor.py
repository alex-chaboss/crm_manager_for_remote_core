"""Редактор списка shell-команд (по одной на строку / элемент списка)."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget

from crm.gui.theme import BTN_PRIMARY, COMMON_EDIT_STYLE, LIST_WIDGET_STYLE


class CommandListEditor(QWidget):
    commands_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setStyleSheet(LIST_WIDGET_STYLE)
        lay.addWidget(self.list)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setStyleSheet(COMMON_EDIT_STYLE)
        row.addWidget(self.input, stretch=1)
        self.btn_add = QPushButton("+")
        self.btn_add.setStyleSheet(BTN_PRIMARY)
        self.btn_add.clicked.connect(self._add)
        row.addWidget(self.btn_add)
        self.btn_remove = QPushButton("−")
        self.btn_remove.setStyleSheet(BTN_PRIMARY)
        self.btn_remove.clicked.connect(self._remove)
        row.addWidget(self.btn_remove)
        self.btn_up = QPushButton("↑")
        self.btn_up.setStyleSheet(BTN_PRIMARY)
        self.btn_up.clicked.connect(self._move_up)
        row.addWidget(self.btn_up)
        self.btn_down = QPushButton("↓")
        self.btn_down.setStyleSheet(BTN_PRIMARY)
        self.btn_down.clicked.connect(self._move_down)
        row.addWidget(self.btn_down)
        lay.addLayout(row)

    def _emit_changed(self) -> None:
        self.commands_changed.emit()

    def _add(self) -> None:
        text = self.input.text().strip()
        if text:
            self.list.addItem(text)
            self.input.clear()
            self._emit_changed()

    def _remove(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            self.list.takeItem(row)
            self._emit_changed()

    def _move_up(self) -> None:
        row = self.list.currentRow()
        if row > 0:
            item = self.list.takeItem(row)
            self.list.insertItem(row - 1, item)
            self.list.setCurrentRow(row - 1)
            self._emit_changed()

    def _move_down(self) -> None:
        row = self.list.currentRow()
        if row >= 0 and row < self.list.count() - 1:
            item = self.list.takeItem(row)
            self.list.insertItem(row + 1, item)
            self.list.setCurrentRow(row + 1)
            self._emit_changed()

    def set_commands(self, commands: list[str]) -> None:
        self.list.clear()
        for c in commands:
            s = str(c).strip()
            if s:
                self.list.addItem(s)

    def get_commands(self) -> list[str]:
        return [self.list.item(i).text() for i in range(self.list.count())]
