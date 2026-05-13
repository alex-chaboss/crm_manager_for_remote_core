"""Демо-сайт: блоки текста + QPainter в одной колонке (без вложенного QTabWidget)."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class ShapePanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(160)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#3498DB"))
        p.setPen(QPen(QColor("#ECF0F1")))
        r = self.contentsRect().adjusted(24, 24, -24, -24)
        p.drawEllipse(r)


def build_site_demo_block(parent=None) -> QWidget:
    """Несколько текстовых заглушек и панель с отрисовкой — в одной вертикали."""
    w = QWidget(parent)
    lay = QVBoxLayout(w)
    for title in ("Pages (demo)", "CDN / cache (demo)", "SEO notes (demo)"):
        lbl = QLabel(f"<i>{title}</i>")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(lbl)
    lay.addWidget(ShapePanel(w))
    return w
