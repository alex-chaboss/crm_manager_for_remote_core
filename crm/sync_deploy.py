"""Синхронизация remote_server_core → boss_server и git push."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from crm.core_tree import (
    collapse_stale_build_artifacts,
    minimize_sync_paths,
    normalize_sync_path,
)
from crm.operation_cancel import CancelToken
from crm.process_runner import run_local_command

logger = logging.getLogger(__name__)

LogFn = Callable[[str, str], None]

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


def _git_run(cwd: str, args: list[str], *, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _git_current_branch(cwd: str) -> str | None:
    r = _git_run(cwd, ["git", "branch", "--show-current"])
    if r.returncode != 0:
        r = _git_run(cwd, ["git", "rev-parse", "--abbrev-ref", "HEAD"])
    branch = (r.stdout or "").strip()
    return branch or None


def _git_has_upstream(cwd: str) -> bool:
    r = _git_run(cwd, ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    return r.returncode == 0 and bool((r.stdout or "").strip())


def _git_remote_names(cwd: str) -> list[str]:
    r = _git_run(cwd, ["git", "remote"])
    if r.returncode != 0:
        return []
    return [line.strip() for line in (r.stdout or "").splitlines() if line.strip()]


def _git_resolve_push_remote(cwd: str, remote_alias: str | None) -> str | None:
    alias = (remote_alias or "").strip()
    remotes = _git_remote_names(cwd)
    if alias and alias in remotes:
        return alias
    if alias and remotes:
        logger.warning(
            "git push: remote %r не найден в boss_server (есть: %s), используем %r",
            alias,
            ", ".join(remotes),
            remotes[0],
        )
    return remotes[0] if remotes else None


def _git_push_command(cwd: str, remote_alias: str | None) -> tuple[list[str], str]:
    """
    Аргументы для git push. Без upstream — push -u <remote> <branch> (первый push после Init).
    """
    if _git_has_upstream(cwd):
        return ["git", "push"], ""
    branch = _git_current_branch(cwd)
    if not branch:
        return ["git", "push"], ""
    remote = _git_resolve_push_remote(cwd, remote_alias)
    if not remote:
        return (
            ["git", "push"],
            "Нет настроенного git remote в boss_server. Выполните Init или "
            "git remote add <alias> <url>.",
        )
    note = f"Первый push: git push --set-upstream {remote} {branch}"
    return ["git", "push", "--set-upstream", remote, branch], note


_NO_UPSTREAM_MARKERS = ("no upstream branch", "has no upstream branch")


def _push_failed_no_upstream(stderr: str, stdout: str) -> bool:
    text = f"{stderr}\n{stdout}".lower()
    return any(m in text for m in _NO_UPSTREAM_MARKERS)


def _git_add_deploy_paths(
    boss_dir: Path,
    *,
    force_add_paths: list[str] | None = None,
    log: LogFn | None = None,
    cancel: CancelToken | None = None,
) -> tuple[bool, str]:
    """git add -A + git add -f для путей деплоя (например front/www в .gitignore)."""
    cwd = str(boss_dir.resolve())
    paths = [p.strip().replace("\\", "/").lstrip("/") for p in (force_add_paths or []) if p.strip()]

    def _run_add(args: list[str]) -> tuple[bool, str]:
        if log is not None and cancel is not None:
            return run_local_command(args, cwd=cwd, log=log, cancel=cancel)
        try:
            subprocess.run(args, cwd=cwd, check=True, capture_output=True, timeout=120)
            return True, ""
        except subprocess.CalledProcessError as e:
            return False, e.stderr or e.stdout or str(e)
        except subprocess.TimeoutExpired:
            return False, "Таймаут git add"

    ok, out = _run_add(["git", "add", "-A"])
    if not ok:
        return False, out
    for rel in paths:
        if (boss_dir / rel).exists():
            ok, out = _run_add(["git", "add", "-f", rel])
            if not ok:
                return False, out
    return True, ""


def deploy_git_push(
    boss_dir: Path,
    commit_message: str | None = None,
    *,
    push_remote: str | None = None,
    force_add_paths: list[str] | None = None,
    log: LogFn | None = None,
    cancel: CancelToken | None = None,
) -> tuple[bool, str]:
    """
    git add -A (+ git add -f для force_add_paths), commit, push в boss_dir.
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
    cwd = str(boss_dir)
    push_cmd, push_note = _git_push_command(cwd, push_remote)
    if push_note and "--set-upstream" not in push_cmd:
        return False, push_note

    if log is not None and cancel is not None:
        ok, out = _git_add_deploy_paths(
            boss_dir,
            force_add_paths=force_add_paths,
            log=log,
            cancel=cancel,
        )
        if not ok:
            return False, out
        run_local_command(["git", "commit", "-m", msg], cwd=cwd, log=log, cancel=cancel)
        if push_note:
            log(push_note, "info")
        ok, out = run_local_command(push_cmd, cwd=cwd, timeout_sec=180, log=log, cancel=cancel)
        if not ok and _push_failed_no_upstream(out, "") and push_cmd == ["git", "push"]:
            push_cmd, push_note = _git_push_command(cwd, push_remote)
            if "--set-upstream" in push_cmd:
                log(push_note, "info")
                ok, out = run_local_command(push_cmd, cwd=cwd, timeout_sec=180, log=log, cancel=cancel)
        if not ok:
            return False, out
        return True, f"Деплой выполнен. git status до коммита: {status_before}"

    try:
        ok, out = _git_add_deploy_paths(boss_dir, force_add_paths=force_add_paths)
        if not ok:
            return False, out
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        r = subprocess.run(push_cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0 and _push_failed_no_upstream(r.stderr or "", r.stdout or ""):
            if push_cmd == ["git", "push"]:
                push_cmd, _ = _git_push_command(cwd, push_remote)
                r = subprocess.run(push_cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
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


def sync_and_push(
    source_dir: Path,
    boss_dir: Path,
    commit_message: str | None = None,
    *,
    push_remote: str | None = None,
    log: LogFn | None = None,
    cancel: CancelToken | None = None,
) -> tuple[bool, str]:
    err = sync_remote_core_to_boss(source_dir, boss_dir)
    if err:
        return False, f"Синхронизация: {err}"
    return deploy_git_push(
        boss_dir,
        commit_message,
        push_remote=push_remote,
        log=log,
        cancel=cancel,
    )


def copy_core_paths_to_targets(
    project_core: Path,
    paths: list[str],
    remote_server_core: Path,
    boss_server: Path,
) -> str:
    """Копирует относительные пути из project_core в remote_server_core и boss_server."""
    project_core = project_core.resolve()
    remote_server_core.mkdir(parents=True, exist_ok=True)
    boss_server.mkdir(parents=True, exist_ok=True)
    try:
        paths = collapse_stale_build_artifacts(project_core, paths)
        for rel in paths:
            rel = rel.strip().replace("\\", "/").lstrip("/")
            if not rel:
                continue
            src = project_core / rel
            if not src.exists():
                return f"Не найдено в project_core: {rel}"
            for dst_root in (remote_server_core, boss_server):
                dst = dst_root / rel
                if src.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst, ignore_errors=True)
                    shutil.copytree(
                        src,
                        dst,
                        ignore=lambda _d, files: [f for f in files if f in ("__pycache__", ".cache", ".git")],
                    )
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
        for dst_root in (remote_server_core, boss_server):
            prune_deploy_tree_to_sync_paths(dst_root, paths)
        return ""
    except Exception as e:
        logger.exception("copy_core_paths_to_targets")
        return str(e)


def allowed_children_at(allowed_prefixes: list[str], ancestor_rel: str) -> set[str] | None:
    """
    Имена непосредственных потомков ancestor_rel, которые должны остаться в deploy-дереве.
    None — выбрана вся директория ancestor_rel целиком, внутри не чистим.
    """
    ancestor_rel = normalize_sync_path(ancestor_rel)
    allowed_prefixes = [normalize_sync_path(p) for p in allowed_prefixes if normalize_sync_path(p)]
    for p in allowed_prefixes:
        if p == ancestor_rel:
            return None
    names: set[str] = set()
    if not ancestor_rel:
        for p in allowed_prefixes:
            if "/" in p:
                names.add(p.split("/", 1)[0])
            else:
                names.add(p)
        return names
    prefix = ancestor_rel + "/"
    for p in allowed_prefixes:
        if p.startswith(prefix):
            rest = p[len(prefix) :]
            if rest:
                names.add(rest.split("/")[0])
    return names


def prune_deploy_tree_to_sync_paths(deploy_root: Path, sync_paths: list[str]) -> None:
    """
    Удаляет из deploy_root файлы/каталоги вне core_sync_paths.

    Нужно после частичного копирования (например только front/www), иначе в front/
    остаются src/node_modules от прошлых полных синков, а sync_remote_core_to_boss
    заливает их в boss_server и в git push.
    """
    deploy_root = deploy_root.resolve()
    if not deploy_root.is_dir():
        return
    allowed_prefixes = minimize_sync_paths(sync_paths)
    if not allowed_prefixes:
        return
    _prune_deploy_dir(deploy_root, "", allowed_prefixes)


def _prune_deploy_dir(
    dir_path: Path,
    ancestor_rel: str,
    allowed_prefixes: list[str],
) -> None:
    allowed = allowed_children_at(allowed_prefixes, ancestor_rel)
    if allowed is None or not dir_path.is_dir():
        return
    for child in list(dir_path.iterdir()):
        if child.name in SKIP_DIRS:
            continue
        if child.name == ".git":
            continue
        if child.name.startswith(".") and child.name not in COPY_DOTFILES:
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
            continue
        if child.name not in allowed:
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
            continue
        if child.is_dir():
            child_rel = f"{ancestor_rel}/{child.name}" if ancestor_rel else child.name
            _prune_deploy_dir(child, child_rel, allowed_prefixes)
