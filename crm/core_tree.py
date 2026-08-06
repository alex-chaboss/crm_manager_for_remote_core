"""Сканирование project_core и дерево путей для FromCoreToRemote."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem

SKIP_DIRS = {".git", "__pycache__", ".cache", ".pytest_cache", ".venv", ".idea", ".angular"}
SKIP_DOT_FILES = {".DS_Store", "Thumbs.db"}


def _skip_dir(name: str) -> bool:
    return name in SKIP_DIRS


def _skip_file(name: str) -> bool:
    return name in SKIP_DOT_FILES


def iter_relative_paths(project_core: Path) -> list[str]:
    root = project_core.resolve()
    if not root.is_dir():
        return []
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _skip_dir(d)]
        rel_dir = Path(dirpath).relative_to(root)
        if str(rel_dir) != ".":
            out.append(str(rel_dir).replace("\\", "/"))
        for fn in filenames:
            if _skip_file(fn):
                continue
            rel = rel_dir / fn if str(rel_dir) != "." else Path(fn)
            out.append(str(rel).replace("\\", "/"))
    return sorted(set(out))


def _path_tree(paths: list[str]) -> dict[str, Any]:
    root: dict[str, Any] = {}
    for rel in paths:
        parts = [p for p in rel.replace("\\", "/").split("/") if p]
        node = root
        for part in parts:
            node = node.setdefault(part, {})
    return root


def normalize_sync_path(rel: str) -> str:
    return rel.strip().replace("\\", "/").strip("/")


def minimize_sync_paths(paths: list[str]) -> list[str]:
    """Убирает вложенные пути, если уже выбран родитель (front + front/www → front)."""
    normed = sorted({normalize_sync_path(p) for p in paths if normalize_sync_path(p)})
    return [
        p
        for p in normed
        if not any(p != q and p.startswith(q + "/") for q in normed)
    ]


def collapse_stale_build_artifacts(project_core: Path, paths: list[str]) -> list[str]:
    """
    Нормализует пути деплоя фронта: только front/www (сборка), не весь front/.

    - Отдельные front/www/<hash>.js из старого ng build → один каталог front/www.
    - Путь front (родитель) или front/src и т.п. → front/www, если www/ существует.
    - minimize_sync_paths иначе оставляет front и выкидывает front/www.
    - Профиль только с back/* → front/www добавляется, если каталог сборки есть.
    """
    paths = minimize_sync_paths(paths)
    www_dir = project_core.resolve() / "front" / "www"
    if not www_dir.is_dir():
        return paths

    front_related = [p for p in paths if p == "front" or p.startswith("front/")]
    if front_related:
        has_www_leaves = any(p.startswith("front/www/") and p != "front/www" for p in paths)
        deploy_www_only = (
            "front/www" in paths
            or has_www_leaves
            or "front" in paths
        )
        if deploy_www_only:
            paths = [p for p in paths if not (p == "front" or p.startswith("front/"))]
            if "front/www" not in paths:
                paths.append("front/www")
            paths = minimize_sync_paths(paths)

    if not any(p == "front/www" or p.startswith("front/www/") for p in paths):
        if any(p.startswith("back/") for p in paths):
            paths.append("front/www")
            paths = minimize_sync_paths(paths)
    return paths


def check_state_for_saved_path(rel: str, selected: set[str]) -> Qt.CheckState:
    """
    Состояние чекбокса при восстановлении выбора из core_sync_paths.

    Раньше предок помечался Checked, если выбран потомок — при сохранении
    в профиль попадал родитель (front/) вместо front/www/….
    """
    if rel in selected:
        return Qt.CheckState.Checked
    prefix = rel + "/"
    if any(s.startswith(prefix) for s in selected):
        return Qt.CheckState.PartiallyChecked
    return Qt.CheckState.Unchecked


def _folder_checked_without_descendants(item: QTreeWidgetItem) -> bool:
    """Пользователь отметил только эту папку; дочерние узлы не отмечены."""
    if item.childCount() == 0:
        return True
    return all(
        item.child(i).checkState(0) == Qt.CheckState.Unchecked
        for i in range(item.childCount())
    )


def _add_items(
    parent_item: QTreeWidgetItem | QTreeWidget,
    node: dict[str, Any],
    prefix: str,
    selected: set[str],
) -> None:
    sel_norm = {normalize_sync_path(s) for s in selected}
    for name in sorted(node.keys()):
        rel = f"{prefix}/{name}" if prefix else name
        rel_norm = normalize_sync_path(rel)
        item = QTreeWidgetItem([name])
        flags = item.flags() | Qt.ItemFlag.ItemIsUserCheckable
        child_node = node[name]
        whole_folder = rel_norm in sel_norm
        if child_node and not whole_folder:
            flags |= Qt.ItemFlag.ItemIsAutoTristate
        item.setFlags(flags)
        item.setCheckState(0, check_state_for_saved_path(rel, selected))
        if isinstance(parent_item, QTreeWidget):
            parent_item.addTopLevelItem(item)
        else:
            parent_item.addChild(item)
        if child_node:
            _add_items(item, child_node, rel, selected)


def populate_core_tree(tree: QTreeWidget, project_core: Path, selected: set[str]) -> None:
    tree.clear()
    paths = list(iter_relative_paths(project_core))
    for p in selected:
        norm = normalize_sync_path(p)
        if norm:
            paths.append(norm)
    paths = sorted(set(paths))
    if not paths:
        return
    sel = set(minimize_sync_paths(list(selected)))
    _add_items(tree, _path_tree(paths), "", sel)


def _collect_checked(item: QTreeWidgetItem, prefix: str, out: list[str]) -> None:
    name = item.text(0)
    rel = f"{prefix}/{name}" if prefix else name
    state = item.checkState(0)
    if state == Qt.CheckState.Unchecked:
        return
    if state == Qt.CheckState.Checked and _folder_checked_without_descendants(item):
        out.append(rel)
        return
    # ItemIsAutoTristate: выбранная папка (front/www) → PartiallyChecked, дети Unchecked
    if state == Qt.CheckState.PartiallyChecked and _folder_checked_without_descendants(item):
        out.append(rel)
        return
    for i in range(item.childCount()):
        _collect_checked(item.child(i), rel, out)


def collect_checked_paths(tree: QTreeWidget) -> list[str]:
    out: list[str] = []
    for i in range(tree.topLevelItemCount()):
        _collect_checked(tree.topLevelItem(i), "", out)
    return minimize_sync_paths(out)


def set_all_checked(tree: QTreeWidget, checked: bool) -> None:
    state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked

    def walk(item: QTreeWidgetItem) -> None:
        item.setCheckState(0, state)
        for i in range(item.childCount()):
            walk(item.child(i))

    for i in range(tree.topLevelItemCount()):
        walk(tree.topLevelItem(i))
