#!/usr/bin/env python3
"""Точка входа CRM: десктоп-инструмент деплоя (PyQt6)."""

from __future__ import annotations

import logging
import os
import sys

_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

from crm.project_init import ensure_projects_initialized  # noqa: E402
from crm.gui.main_window import MainWindow  # noqa: E402


def main() -> int:
    ensure_projects_initialized()
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("CRM Remote Core")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
