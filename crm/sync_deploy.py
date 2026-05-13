"""Синхронизация remote_server_core → boss_server и git push."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

SKIP_DIRS = {".git", "__pycache__", ".cache", ".pytest_cache"}
COPY_DOTFILES = {".gitignore"}


def sync_remote_core_to_boss(source_dir: Path, boss_dir: Path) -> str:
    """
    Копирует содержимое source_dir в boss_dir (как sync_remote_core_to_boss в арбитражном ядре).
    Возвращает пустую строку при успехе, иначе текст ошибки.
    """
    source_dir = source_dir.resolve()
    boss_dir = boss_dir.resolve()
    if not source_dir.is_dir():
        return f"Каталог-источник не найден: {source_dir}"
    boss_dir.mkdir(parents=True, exist_ok=True)
    try:
        for name in os.listdir(source_dir):
            if name in SKIP_DIRS:
                continue
            if name.startswith(".") and name not in COPY_DOTFILES:
                continue
            src = source_dir / name
            dst = boss_dir / name
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(
                    src,
                    dst,
                    ignore=lambda _d, files: [f for f in files if f in ("__pycache__", ".cache", ".git")],
                )
            else:
                shutil.copy2(src, dst)
        return ""
    except Exception as e:
        logger.exception("sync_remote_core_to_boss")
        return str(e)


def git_status_short(repo: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=15,
        )
        return (r.stdout or "").strip() or "(нет изменений)"
    except Exception as e:
        return str(e)


def deploy_git_push(boss_dir: Path, commit_message: str | None = None) -> tuple[bool, str]:
    """
    git add -A, commit (если есть изменения), push в boss_dir.
    Возвращает (ok, message).
    """
    boss_dir = boss_dir.resolve()
    if not boss_dir.is_dir():
        return False, f"Каталог boss_server не найден: {boss_dir}"
    git_dir = boss_dir / ".git"
    if not git_dir.exists():
        return (
            False,
            "В boss_server нет репозитория (.git). Инициализируйте git на сервере/локально "
            "(см. create_git_repo.sh в каталоге проекта и README).",
        )
    msg = commit_message or "Deploy remote_server_core"
    status_before = git_status_short(boss_dir)
    try:
        subprocess.run(["git", "add", "-A"], cwd=str(boss_dir), check=True, capture_output=True, timeout=30)
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=str(boss_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        # код 1 при «nothing to commit» — допустимо
        r = subprocess.run(["git", "push"], cwd=str(boss_dir), capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return False, f"git push: {r.stderr or r.stdout or 'ошибка'}"
        return True, f"Деплой выполнен. git status до коммита: {status_before}"
    except subprocess.CalledProcessError as e:
        err = e.stderr or e.stdout or str(e)
        return False, err
    except subprocess.TimeoutExpired:
        return False, "Таймаут git"
    except Exception as e:
        return False, str(e)


def sync_and_push(source_dir: Path, boss_dir: Path, commit_message: str | None = None) -> tuple[bool, str]:
    err = sync_remote_core_to_boss(source_dir, boss_dir)
    if err:
        return False, f"Синхронизация: {err}"
    return deploy_git_push(boss_dir, commit_message)
