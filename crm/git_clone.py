"""Клонирование source git URL в project_core (`git clone <url> .`)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from crm.operation_cancel import CancelToken
from crm.paths import project_dir
from crm.process_runner import run_local_command

LogFn = Callable[[str, str], None]


def extract_git_url_token(raw: str) -> str | None:
    """Первый токен (по пробелам) с подстрокой «.git»; иначе None."""
    for part in raw.split():
        token = part.strip().strip("'\"")
        if ".git" in token:
            return token
    return None


def project_core_has_content(project_id: str) -> bool:
    """True, если в project_core есть что-то кроме одного тестового README.md."""
    core = project_dir(project_id) / "project_core"
    if not core.is_dir():
        return False
    for p in core.iterdir():
        if p.name == "README.md" and p.is_file():
            continue
        return True
    return False


def project_core_has_git(project_id: str) -> bool:
    core = project_dir(project_id) / "project_core"
    git_dir = core / ".git"
    return git_dir.is_dir() or git_dir.is_file()


def clear_project_core(project_id: str) -> None:
    core = project_dir(project_id) / "project_core"
    core.mkdir(parents=True, exist_ok=True)
    for child in list(core.iterdir()):
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def clone_into_project_core(
    project_id: str,
    url: str,
    *,
    log: LogFn,
    cancel: CancelToken,
) -> tuple[bool, str]:
    url = url.strip()
    if not url:
        return False, "URL пустой"
    root = project_dir(project_id)
    core = root / "project_core"
    core.mkdir(parents=True, exist_ok=True)
    clear_project_core(project_id)
    if log:
        log(f"$ cd {core} && git clone {url} .", "info")
    ok, out = run_local_command(
        ["git", "clone", url, "."],
        cwd=str(core),
        log=log,
        cancel=cancel,
        timeout_sec=600,
    )
    if ok:
        return True, out
    return False, out
