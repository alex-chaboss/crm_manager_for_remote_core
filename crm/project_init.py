"""Первый запуск: каталог Projects/ и скелеты проектов."""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from crm.paths import PROJECTS_DIR

logger = logging.getLogger(__name__)

_TEMPLATE_ROOT = Path(__file__).resolve().parent / "templates" / "project_widget"

SKELETON_IDS = ("simple_game_example", "simple_service_example", "simple_site_example")
PROJECT_ID_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,127}$")


def _create_git_repo_template(project_root: Path, project_id: str) -> None:
    """Шаблон скрипта для инициализации bare + рабочей копии на сервере (запуск по SSH)."""
    path = project_root / "create_git_repo.sh"
    text = f'''#!/bin/sh
# CRM: инициализация git-пространства для проекта «{project_id}» на сервере.
# Рекомендуемый запуск с машины разработчика (подставьте user@host и путь):
#   ssh user@host 'bash -s' < Projects/{project_id}/create_git_repo.sh
#
# Перед запуском на сервере задайте базовый каталог (родитель boss_server и bare-репо):
set -e
CRM_SERVER_BASE="${{CRM_SERVER_BASE:?Задайте CRM_SERVER_BASE, например /var/crm/projects/{project_id}}}"
BARE_NAME="${{BARE_NAME:-{project_id}.git}}"
WORK_NAME="${{WORK_NAME:-boss_server}}"
REMOTE_ALIAS="${{REMOTE_ALIAS:-deploy}}"

cd "$CRM_SERVER_BASE"
mkdir -p "$BARE_NAME"
cd "$BARE_NAME"
git init --bare

cd "$CRM_SERVER_BASE"
mkdir -p "$WORK_NAME"
cd "$WORK_NAME"
git init -b main 2>/dev/null || git init
git remote add "$REMOTE_ALIAS" "../$BARE_NAME" 2>/dev/null || git remote set-url "$REMOTE_ALIAS" "../$BARE_NAME"
echo "# {project_id}" > README_CRM_BOSS.md
git add README_CRM_BOSS.md
git commit -m "init CRM boss_server" || true
git push -u "$REMOTE_ALIAS" HEAD:main || git push -u "$REMOTE_ALIAS" master
echo "Готово: bare в $CRM_SERVER_BASE/$BARE_NAME, рабочая копия в $CRM_SERVER_BASE/$WORK_NAME"
'''
    path.write_text(text, encoding="utf-8")
    try:
        mode = path.stat().st_mode
        path.chmod(mode | 0o111)
    except OSError:
        pass


def _readme(path: Path, title: str, body: str) -> None:
    path.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")


def _install_project_widget(root: Path, project_id: str) -> None:
    """Копирует шаблон project-widget/ (демо для simple_* или default)."""
    dst = root / "project-widget"
    example = _TEMPLATE_ROOT / "examples" / project_id
    src = example if example.is_dir() else _TEMPLATE_ROOT / "default"
    if not src.is_dir():
        logger.warning("project-widget template missing: %s (skip)", src)
        return
    shutil.copytree(src, dst)


def create_project_skeleton(project_id: str) -> Path:
    """Создаёт каталог проекта с базовыми подкаталогами и project-widget. Возвращает путь к корню проекта."""
    if not PROJECT_ID_RE.match(project_id):
        raise ValueError(
            "Идентификатор проекта: латиница/цифры/дефис/подчёркивание, "
            "первый символ — буква, длина до 128."
        )
    root = PROJECTS_DIR / project_id
    if root.exists():
        raise FileExistsError(f"Проект уже существует: {project_id}")
    root.mkdir(parents=True)
    (root / "project_core").mkdir()
    (root / "remote_server_core").mkdir()
    (root / "boss_server").mkdir()
    _readme(
        root / "project_core" / "README.md",
        "project_core",
        "Полный исходный проект: клонируйте или скопируйте сюда рабочий репозиторий до разделения на серверную часть.",
    )
    _readme(
        root / "remote_server_core" / "README.md",
        "remote_server_core",
        "Канон файлов для выкладки на VPS. Содержимое синхронизируется в boss_server перед git push.",
    )
    _readme(
        root / "boss_server" / "README.md",
        "boss_server",
        "Рабочая копия для push в удалённый bare-репозиторий. Выполните create_git_repo.sh на сервере "
        "и настройте remote, затем клонируйте или свяжите этот каталог с тем репозиторием.",
    )
    _create_git_repo_template(root, project_id)
    _install_project_widget(root, project_id)
    return root


def ensure_projects_initialized() -> None:
    """Если Projects/ нет или пуст — создаём три примера-скелета."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        entries = [p for p in PROJECTS_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")]
    except OSError as e:
        logger.error("Projects dir: %s", e)
        return
    if entries:
        return
    for pid in SKELETON_IDS:
        try:
            create_project_skeleton(pid)
            logger.info("Создан скелет проекта: %s", pid)
        except Exception as e:
            logger.error("Скелет %s: %s", pid, e)


def list_project_ids() -> list[str]:
    if not PROJECTS_DIR.is_dir():
        return []
    out = sorted(
        p.name for p in PROJECTS_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")
    )
    return out
