"""Демо-сервис: только таблица метрик (другие колонки)."""

from PyQt6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


def build_service_table(parent=None) -> QWidget:
    w = QWidget(parent)
    lay = QVBoxLayout(w)
    table = QTableWidget(5, 4)
    table.setHorizontalHeaderLabels(["service", "cpu%", "mem_mb", "uptime"])
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    rows = [
        ("api", "12", "512", "3d"),
        ("worker", "34", "1024", "3d"),
        ("redis", "4", "256", "30d"),
        ("nginx", "2", "64", "30d"),
        ("cron", "1", "32", "3d"),
    ]
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            table.setItem(r, c, QTableWidgetItem(text))
    lay.addWidget(table)
    return w
