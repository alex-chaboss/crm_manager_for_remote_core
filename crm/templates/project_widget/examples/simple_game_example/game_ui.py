"""Демо-виджеты: таблица (чарт данных) и линейный график QPainter (без новых зависимостей)."""

from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class MiniSparkline(QFrame):
    """Условный «график»: линия по фиксированным точкам."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self._values = [10, 25, 18, 40, 32, 55, 48, 60]

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.contentsRect().adjusted(12, 12, -12, -12)
        if rect.width() <= 0 or rect.height() <= 0:
            return
        pen = QPen(QColor("#2ECC71"))
        pen.setWidth(2)
        painter.setPen(pen)
        vmax = max(self._values)
        vmin = min(self._values)
        span = max(vmax - vmin, 1)
        n = len(self._values)
        for i in range(n - 1):
            x1 = rect.left() + i * rect.width() / (n - 1)
            x2 = rect.left() + (i + 1) * rect.width() / (n - 1)
            y1 = rect.bottom() - (self._values[i] - vmin) / span * rect.height()
            y2 = rect.bottom() - (self._values[i + 1] - vmin) / span * rect.height()
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))


def build_charts_tab(parent=None) -> QWidget:
    """Панель для отдельной вкладки: mock-метрики в таблице + sparkline (график)."""
    w = QWidget(parent)
    lay = QVBoxLayout(w)
    table = QTableWidget(4, 3)
    table.setHorizontalHeaderLabels(["metric", "value", "note"])
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    mock = [
        ("players_online", "128", "mock"),
        ("latency_ms", "42", "mock"),
        ("errors_1h", "0", "mock"),
        ("build", "ok", "mock"),
    ]
    for r, row in enumerate(mock):
        for c, text in enumerate(row):
            table.setItem(r, c, QTableWidgetItem(text))
    lay.addWidget(table, stretch=1)
    chart = MiniSparkline()
    chart.setFrameShape(QFrame.Shape.StyledPanel)
    lay.addWidget(chart)
    return w


def build_dashboard(parent=None) -> QWidget:
    """Алиас: то же содержимое, что и `build_charts_tab` (одна панель без вкладок)."""
    return build_charts_tab(parent)
