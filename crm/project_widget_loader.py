"""Загрузка корневого виджета области проекта из Projects/<id>/project-widget/."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QWidget

from crm.gui.project_tab_fallback import LegacyProjectTabsWidget
from crm.paths import PROJECTS_DIR

logger = logging.getLogger(__name__)

RESERVED_WIDGET_FILE = "base_project_widget.py"
ENTRYPOINT_NAME = "build"
RESERVED_CLASS_NAME = "CRMProjectTab"


def project_widget_file(project_id: str) -> Path:
    return PROJECTS_DIR / project_id / "project-widget" / RESERVED_WIDGET_FILE


def _unload_modules_under(pkg_dir: Path, before_keys: set[str]) -> None:
    """Убирает из sys.modules модули, загруженные из каталога project-widget (соседние .py)."""
    root = str(pkg_dir.resolve())
    for name in list(sys.modules):
        if name in before_keys:
            continue
        mod = sys.modules.get(name)
        fn = getattr(mod, "__file__", None) if mod is not None else None
        if not fn:
            continue
        try:
            p = str(Path(fn).resolve())
        except OSError:
            continue
        if p == root or p.startswith(root + "/"):
            del sys.modules[name]


def _fallback(project_id: str, main_window: Any, parent: QWidget, reason: str, path: Path | None = None) -> QWidget:
    extra = f" path={path}" if path is not None else ""
    logger.info("project-widget: %s, legacy tabs fallback project_id=%s%s", reason, project_id, extra)
    return LegacyProjectTabsWidget(project_id, main_window, parent)


def load_project_tab(project_id: str, main_window: Any, parent: QWidget) -> QWidget:
    """Корень области проекта: build() или класс CRMProjectTab, иначе LegacyProjectTabsWidget."""
    path = project_widget_file(project_id)
    if not path.is_file():
        return _fallback(project_id, main_window, parent, "file missing", path)

    pkg_dir = path.parent.resolve()
    pkg_dir_s = str(pkg_dir)
    inserted = False
    if pkg_dir_s not in sys.path:
        sys.path.insert(0, pkg_dir_s)
        inserted = True

    mod_name = f"crm_dyn_pw_{project_id.replace('-', '_')}"
    before_keys = set(sys.modules.keys())
    try:
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            logger.warning("project-widget: spec_from_file_location failed path=%s", path)
            return _fallback(project_id, main_window, parent, "spec failed", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        build_fn = getattr(mod, ENTRYPOINT_NAME, None)
        if callable(build_fn):
            try:
                widget = build_fn(parent, project_id, main_window)
            except Exception:
                logger.exception("project-widget: build() raised project_id=%s", project_id)
                return _fallback(project_id, main_window, parent, "build() exception", path)
            if isinstance(widget, QWidget):
                return widget
            logger.warning(
                "project-widget: %r returned %r, expected QWidget (fallback)",
                ENTRYPOINT_NAME,
                type(widget),
            )
            return _fallback(project_id, main_window, parent, "build() not QWidget", path)

        cls = getattr(mod, RESERVED_CLASS_NAME, None)
        if isinstance(cls, type) and issubclass(cls, QWidget) and cls is not QWidget:
            try:
                inst = cls(project_id, main_window, parent)
            except TypeError:
                logger.warning(
                    "project-widget: %s(...) TypeError — ожидается (project_id, main_window, parent)",
                    RESERVED_CLASS_NAME,
                    exc_info=True,
                )
                return _fallback(project_id, main_window, parent, "class ctor TypeError", path)
            except Exception:
                logger.exception("project-widget: %s raised project_id=%s", RESERVED_CLASS_NAME, project_id)
                return _fallback(project_id, main_window, parent, "class ctor exception", path)
            if isinstance(inst, QWidget):
                return inst
            logger.warning(
                "project-widget: %s instance is not QWidget (%r)",
                RESERVED_CLASS_NAME,
                type(inst),
            )
            return _fallback(project_id, main_window, parent, "class instance not QWidget", path)

        logger.warning(
            "project-widget: no callable %r and no subclass %r of QWidget in %s",
            ENTRYPOINT_NAME,
            RESERVED_CLASS_NAME,
            path,
        )
        return _fallback(project_id, main_window, parent, "no build nor CRMProjectTab", path)
    except Exception:
        logger.exception("project-widget: load failed project_id=%s path=%s", project_id, path)
        return _fallback(project_id, main_window, parent, "exec_module failed", path)
    finally:
        _unload_modules_under(pkg_dir, before_keys)
        if inserted:
            try:
                sys.path.remove(pkg_dir_s)
            except ValueError:
                pass
