"""Сценарий «Деплой»: pre_deploy → auto sync → push → post_deploy."""

from __future__ import annotations

from typing import Callable

from crm.command_lists import run_merged_command_list
from crm.config_store import build_ssh_restart_command, effective_ssh_config, load_project, ssh_port_for_cli
from crm.operation_cancel import CancelToken
from crm.paths import project_dir
from crm.process_runner import run_ssh_command
from crm.secret_markers import substitute
from crm.server_init import prepare_server_work_tree_for_deploy, run_ssh_command_list
from crm.core_tree import collapse_stale_build_artifacts
from crm.sync_deploy import copy_core_paths_to_targets, deploy_git_push, sync_and_push

LogFn = Callable[[str, str], None]


def _verify_server_work_tree(cfg: dict, log: LogFn, cancel: CancelToken) -> tuple[bool, str]:
    work = (cfg.get("ssh_work_dir") or "").strip()
    host = (cfg.get("ssh_host") or "").strip()
    if not host or not work:
        log("Проверка рабочей копии на сервере пропущена: не задан ssh_host или ssh_work_dir", "warn")
        return True, ""
    port, bad = ssh_port_for_cli(cfg.get("ssh_port"))
    if bad:
        return False, "invalid port"
    cmd = f'cd "{work}" && git rev-parse --is-inside-work-tree >/dev/null && git status -sb | head -8'
    log("Проверка рабочей копии на сервере после push (hook)…", "info")
    return run_ssh_command(
        host,
        cmd,
        ssh_port=port,
        timeout_sec=float(cfg.get("ssh_command_timeout_sec") or 120),
        log=log,
        cancel=cancel,
    )


def run_deploy_job(
    project_id: str,
    log: LogFn,
    cancel: CancelToken,
    *,
    secrets: dict[str, str] | None = None,
) -> tuple[bool, str]:
    root = project_dir(project_id)
    cfg = effective_ssh_config(project_id, root)
    prof = load_project(project_id)

    ok, out = run_merged_command_list(
        project_id,
        "pre_deploy_commands",
        cfg,
        log,
        cancel,
        local_cwd=root,
        secrets=secrets,
    )
    if not ok:
        return False, out

    selective_sync_paths: list[str] | None = None
    if prof.get("auto_sync_enabled"):
        paths = prof.get("core_sync_paths") or []
        if paths:
            raw_count = len(paths)
            core = cfg["project_core_path"]
            paths = collapse_stale_build_artifacts(core, paths)
            selective_sync_paths = list(paths)
            if len(paths) < raw_count:
                log(
                    f"Auto Sync: {raw_count} путей в профиле → {len(paths)} после схлопывания front/www",
                    "info",
                )
            else:
                log(f"Auto Sync: {len(paths)} путей", "info")
            err = copy_core_paths_to_targets(
                core,
                paths,
                cfg["remote_server_core_path"],
                cfg["boss_server_path"],
            )
            if err:
                return False, err

    ok, out = prepare_server_work_tree_for_deploy(cfg, log, cancel)
    if not ok:
        return False, f"Подготовка рабочей копии на сервере: {out}"

    dst = cfg["boss_server_path"]
    if selective_sync_paths:
        log(
            "git push из boss_server (без полного копирования remote_server_core → boss_server)",
            "info",
        )
        ok, out = deploy_git_push(
            dst,
            commit_message="Deploy remote_server_core",
            push_remote=cfg.get("server_remote_alias"),
            force_add_paths=selective_sync_paths,
            log=log,
            cancel=cancel,
        )
    else:
        src = cfg["remote_server_core_path"]
        log(f"Sync + push: {src} → {dst}", "info")
        ok, out = sync_and_push(
            src,
            dst,
            commit_message="Deploy remote_server_core",
            push_remote=cfg.get("server_remote_alias"),
            log=log,
            cancel=cancel,
        )
    if not ok:
        return False, out
    log("push OK; на сервере сработает post-update hook", "info")

    ok, out = _verify_server_work_tree(cfg, log, cancel)
    if not ok:
        return False, f"Проверка на сервере: {out}"

    ok, out = run_ssh_command_list(project_id, "post_deploy_commands", cfg, log, cancel, secrets=secrets)
    if not ok:
        return False, out

    restart = build_ssh_restart_command(cfg)
    if secrets:
        restart = substitute(restart, secrets)
    if restart.strip() and restart.strip() != "true":
        port, _ = ssh_port_for_cli(cfg.get("ssh_port"))
        ok, out = run_ssh_command(
            cfg["ssh_host"],
            restart,
            ssh_port=port,
            timeout_sec=float(cfg.get("ssh_command_timeout_sec") or 120),
            log=log,
            cancel=cancel,
        )
        if not ok:
            return False, out

    return True, out or "Деплой завершён"
