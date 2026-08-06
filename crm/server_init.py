"""Инициализация remote git на сервере и привязка локального boss_server."""

from __future__ import annotations

import logging
import shlex
from pathlib import Path
from typing import Callable

from crm.command_lists import run_merged_command_list
from crm.config_store import effective_ssh_config, ssh_port_for_cli
from crm.create_git_repo_template import render_create_git_repo_sh
from crm.operation_cancel import CancelToken, OperationCancelledError
from crm.paths import project_dir
from crm.process_runner import run_local_command, run_ssh_command, run_ssh_script_stdin

logger = logging.getLogger(__name__)
LogFn = Callable[[str, str], None]


def server_remote_paths(cfg: dict) -> tuple[str, str]:
    """Пути bare и рабочей копии на VPS: MY_MAIN_PATH/PROJECT_NAME(.git)."""
    base = (cfg.get("server_base_path") or "").strip().rstrip("/")
    name = (cfg.get("server_project_name") or "").strip()
    return f"{base}/{name}.git", f"{base}/{name}"


def probe_server_init_paths(cfg: dict, cancel: CancelToken) -> tuple[bool, list[str], str]:
    """
    Проверка по SSH: существуют ли каталоги init на сервере.
    (ok, existing_paths, error_text)
    """
    cancel.raise_if_cancelled()
    host = (cfg.get("ssh_host") or "").strip()
    if not host:
        return False, [], "ssh_host empty"
    port, bad = ssh_port_for_cli(cfg.get("ssh_port"))
    if bad:
        return False, [], "invalid ssh port"
    bare, work = server_remote_paths(cfg)
    bq, wq = shlex.quote(bare), shlex.quote(work)
    cmd = (
        f"for p in {bq} {wq}; do "
        f'if [ -e "$p" ]; then echo "EXISTS:$p"; fi; '
        "done"
    )
    ok, out = run_ssh_command(
        host,
        cmd,
        ssh_port=port,
        timeout_sec=60,
        log=None,
        cancel=cancel,
    )
    if not ok:
        return False, [], out or "SSH probe failed"
    existing: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("EXISTS:"):
            existing.append(line[7:].strip())
    return True, existing, ""


def remove_server_init_paths(cfg: dict, log: LogFn, cancel: CancelToken) -> tuple[bool, str]:
    """Удалить bare и рабочую копию на сервере перед повторным init."""
    cancel.raise_if_cancelled()
    host = (cfg.get("ssh_host") or "").strip()
    port, bad = ssh_port_for_cli(cfg.get("ssh_port"))
    if bad:
        return False, "invalid ssh port"
    bare, work = server_remote_paths(cfg)
    bq, wq = shlex.quote(bare), shlex.quote(work)
    cmd = f"rm -rf {bq} {wq}"
    log(f"Удаление на сервере: {bare}, {work}", "warn")
    return run_ssh_command(
        host,
        cmd,
        ssh_port=port,
        timeout_sec=float(cfg.get("ssh_command_timeout_sec") or 120),
        log=log,
        cancel=cancel,
    )


def _ensure_git_on_server(cfg: dict, log: LogFn, cancel: CancelToken) -> tuple[bool, str]:
    port, _ = ssh_port_for_cli(cfg.get("ssh_port"))
    host = cfg["ssh_host"]
    timeout = float(cfg.get("ssh_command_timeout_sec") or 120)
    ok, out = run_ssh_command(host, "command -v git", ssh_port=port, timeout_sec=30, log=log, cancel=cancel)
    if ok:
        return True, out
    log("git не найден на сервере, установка пакета git…", "warn")
    install_cmd = (
        "if command -v apt-get >/dev/null 2>&1; then "
        "export DEBIAN_FRONTEND=noninteractive && apt-get update -qq && apt-get install -y git; "
        "elif command -v dnf >/dev/null 2>&1; then dnf install -y git; "
        "elif command -v yum >/dev/null 2>&1; then yum install -y git; "
        "else echo 'Не найден apt-get/dnf/yum' && exit 1; fi"
    )
    ok, out = run_ssh_command(
        host,
        install_cmd,
        ssh_port=port,
        timeout_sec=max(timeout, 180),
        log=log,
        cancel=cancel,
    )
    return ok, out


def run_ssh_command_list(
    project_id: str,
    list_key: str,
    cfg: dict,
    log: LogFn,
    cancel: CancelToken,
    *,
    secrets: dict[str, str] | None = None,
) -> tuple[bool, str]:
    root = project_dir(project_id)
    return run_merged_command_list(
        project_id,
        list_key,
        cfg,
        log,
        cancel,
        local_cwd=root,
        secrets=secrets,
    )


def prepare_server_work_tree_for_deploy(
    cfg: dict,
    log: LogFn,
    cancel: CancelToken,
) -> tuple[bool, str]:
    """
    Перед локальным git push: на VPS сбросить локальный мусор рабочей копии
    (логи/временные правки), затем git pull из bare (как post-update hook).

    Политика: server-side изменения не сохраняем — stash только чтобы очистить
    tree, сразу git stash clear (без восстановления). Источник правды — локальный
    remote_server_core / boss_server.
    """
    cancel.raise_if_cancelled()
    work = (cfg.get("ssh_work_dir") or "").strip()
    host = (cfg.get("ssh_host") or "").strip()
    if not host or not work:
        log(
            "Подготовка рабочей копии на сервере пропущена: не задан ssh_host или ssh_work_dir",
            "warn",
        )
        return True, ""
    port, bad = ssh_port_for_cli(cfg.get("ssh_port"))
    if bad:
        return False, "invalid ssh port"
    alias = shlex.quote(cfg.get("server_remote_alias") or cfg.get("server_project_name") or "")
    branch = shlex.quote(cfg.get("server_git_branch") or "master")
    wq = shlex.quote(work)
    # stash (+ untracked via add -A) → clear (discard) → pull deploy tip
    cmd = (
        f"cd {wq} && "
        "git rev-parse --is-inside-work-tree >/dev/null || "
        "{ echo 'Ошибка: ssh_work_dir не является git-репозиторием'; exit 1; }; "
        'if [ -n "$(git status --porcelain)" ]; then '
        "echo 'CRM: на сервере есть локальные изменения — git add -A && git stash && git stash clear (discard)'; "
        "git add -A && "
        'git stash push -u -m "crm-pre-deploy-discard-$(date -u +%Y%m%dT%H%M%SZ)" || '
        "{ echo 'Ошибка: git stash не удался'; exit 1; }; "
        "else "
        "echo 'CRM: рабочая копия на сервере чистая'; "
        "fi; "
        "git stash clear; "
        f"git pull {alias} {branch}"
    )
    log(
        f"Подготовка рабочей копии на сервере перед push: {work} "
        f"(stash+clear discard → git pull {cfg.get('server_remote_alias')} "
        f"{cfg.get('server_git_branch') or 'master'})",
        "info",
    )
    ok, out = run_ssh_command(
        host,
        cmd,
        ssh_port=port,
        timeout_sec=float(cfg.get("ssh_command_timeout_sec") or 120),
        log=log,
        cancel=cancel,
    )
    if ok and "crm-pre-deploy-discard" in (out or ""):
        log(
            "На сервере локальные изменения сброшены (stash + stash clear). "
            "Восстановление не предусмотрено — источник правды только локальный деплой.",
            "info",
        )
    return ok, out


def bind_local_boss_server(
    project_id: str,
    cfg: dict,
    log: LogFn,
    cancel: CancelToken,
) -> tuple[bool, str]:
    cancel.raise_if_cancelled()
    root = project_dir(project_id)
    boss = Path(cfg["boss_server_path"])
    boss.mkdir(parents=True, exist_ok=True)
    base = (cfg.get("server_base_path") or "").rstrip("/")
    name = cfg.get("server_project_name") or project_id
    host = (cfg.get("ssh_host") or "").strip()
    if "@" in host:
        user_part, host_part = host.split("@", 1)
        url = f"ssh://{user_part}@{host_part}{base}/{name}.git"
    else:
        url = f"ssh://{host}{base}/{name}.git"
    branch = cfg.get("server_git_branch") or "master"
    alias = cfg.get("server_remote_alias") or name
    log(f"Привязка {boss} → {url}", "info")
    git_dir = boss / ".git"
    if not git_dir.exists():
        ok, out = run_local_command(
            ["git", "init"],
            cwd=str(boss),
            log=log,
            cancel=cancel,
        )
        if not ok:
            return False, out
    ok, out = run_local_command(
        ["git", "remote", "add", alias, url],
        cwd=str(boss),
        log=log,
        cancel=cancel,
    )
    if not ok and "already exists" not in out.lower():
        ok, out = run_local_command(
            ["git", "remote", "set-url", alias, url],
            cwd=str(boss),
            log=log,
            cancel=cancel,
        )
        if not ok:
            return False, out
    ok, out = run_local_command(
        ["git", "fetch", alias],
        cwd=str(boss),
        timeout_sec=300,
        log=log,
        cancel=cancel,
    )
    if not ok:
        return False, out
    ok, out = run_local_command(
        ["git", "checkout", "-B", branch],
        cwd=str(boss),
        log=log,
        cancel=cancel,
    )
    if not ok:
        return False, out
    log(
        f"Синхронизация boss_server с bare (обязательно перед деплоем): "
        f"git pull {alias} {branch}",
        "info",
    )
    ok, out = run_local_command(
        ["git", "pull", alias, branch],
        cwd=str(boss),
        timeout_sec=300,
        log=log,
        cancel=cancel,
    )
    if not ok:
        return False, out
    upstream = f"{alias}/{branch}"
    ok2, out2 = run_local_command(
        ["git", "branch", "--set-upstream-to", upstream, branch],
        cwd=str(boss),
        log=log,
        cancel=cancel,
    )
    if not ok2:
        log(
            f"Предупреждение: не удалось задать upstream {upstream}: {out2}",
            "warn",
        )
    return True, out or "OK"


def run_server_init_job(
    project_id: str,
    log: LogFn,
    cancel: CancelToken,
    *,
    recreate_remote: bool = False,
    secrets: dict[str, str] | None = None,
) -> tuple[bool, str]:
    cfg = effective_ssh_config(project_id, project_dir(project_id))
    if not (cfg.get("ssh_host") or "").strip():
        return False, "ssh_host empty"
    base = (cfg.get("server_base_path") or "").strip()
    if not base:
        return False, "server_base_path empty"
    port, bad = ssh_port_for_cli(cfg.get("ssh_port"))
    if bad:
        return False, "invalid ssh port"

    ok, out = _ensure_git_on_server(cfg, log, cancel)
    if not ok:
        return False, out

    if recreate_remote:
        ok, out = remove_server_init_paths(cfg, log, cancel)
        if not ok:
            return False, out

    # --- Этап 1: pre-init команды (при ошибке — полная остановка) ---
    log("── Этап 1/3: pre-init команды ──", "info")
    ok, out = run_ssh_command_list(project_id, "pre_init_commands", cfg, log, cancel, secrets=secrets)
    if not ok:
        return False, f"pre-init commands failed: {out}"

    # --- Этап 2: remote git + привязка boss_server (при ошибке — остановка) ---
    log("── Этап 2/3: remote git + привязка boss_server ──", "info")
    name = cfg["server_project_name"]
    script = render_create_git_repo_sh(project_id)
    env_prefix = f'export MY_MAIN_PATH="{base}" PROJECT_NAME="{name}" GIT_BRANCH="{cfg["server_git_branch"]}" REMOTE_ALIAS="{cfg["server_remote_alias"]}"; '
    ok, out = run_ssh_script_stdin(
        cfg["ssh_host"],
        env_prefix + script,
        ssh_port=port,
        timeout_sec=float(cfg.get("ssh_command_timeout_sec") or 120) * 3,
        log=log,
        cancel=cancel,
    )
    if not ok:
        return False, f"remote git setup failed: {out}"

    ok, out = bind_local_boss_server(project_id, cfg, log, cancel)
    if not ok:
        return False, f"boss_server bind failed: {out}"

    # --- Этап 3: post-init команды (ошибки не блокируют результат) ---
    log("── Этап 3/3: post-init команды ──", "info")
    ok, out = run_ssh_command_list(project_id, "post_init_commands", cfg, log, cancel, secrets=secrets)
    if not ok:
        log(
            f"post-init команды завершились с ошибкой (remote git и boss_server "
            f"привязаны успешно): {out}",
            "warn",
        )

    return True, "OK"
