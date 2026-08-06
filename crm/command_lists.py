"""Выполнение объединённых списков команд (local-sh: / server-sh: / local: / server: / без префикса)."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Callable

from crm.config_store import merge_command_lists, ssh_port_for_cli
from crm.operation_cancel import CancelToken
from crm.process_runner import run_local_command, run_ssh_command, run_ssh_script_stdin
from crm.secret_markers import substitute

LogFn = Callable[[str, str], None]

LOCAL_SH_PREFIX = "local-sh:"
LOCAL_PREFIX = "local:"
SERVER_SH_PREFIX = "server-sh:"
SERVER_PREFIX = "server:"


def _strip_prefix(raw: str, prefix: str) -> str:
    return raw[len(prefix) :].strip()


def _run_local_shell(cmd: str, cwd: Path | None, log: LogFn, cancel: CancelToken, timeout: float) -> tuple[bool, str]:
    cmd = cmd.strip()
    if not cmd:
        return True, "OK"
    try:
        argv = shlex.split(cmd)
    except ValueError as e:
        return False, f"local: неверная команда: {e}"
    if not argv:
        return True, "OK"
    return run_local_command(
        argv,
        cwd=str(cwd) if cwd else None,
        timeout_sec=timeout,
        log=log,
        cancel=cancel,
    )


def _run_local_shell_script(
    script: str,
    cwd: Path | None,
    log: LogFn,
    cancel: CancelToken,
    timeout: float,
) -> tuple[bool, str]:
    """Локально через ``bash -lc`` — как в терминале (``cd``, ``&&``, пайпы)."""
    script = script.strip()
    if not script:
        return True, "OK"
    if log:
        log(f"local-sh: {script}", "info")
    return run_local_command(
        ["bash", "-lc", script],
        cwd=str(cwd) if cwd else None,
        timeout_sec=timeout,
        log=log,
        cancel=cancel,
    )


def _run_remote_shell(
    host: str,
    cmd: str,
    port: int | None,
    timeout: float,
    log: LogFn,
    cancel: CancelToken,
    *,
    log_label: str,
) -> tuple[bool, str]:
    cmd = cmd.strip()
    if not cmd:
        return True, "OK"
    log(f"{log_label}: {cmd}", "info")
    return run_ssh_command(
        host,
        cmd,
        ssh_port=port,
        timeout_sec=timeout,
        log=log,
        cancel=cancel,
    )


def _run_remote_shell_script(
    host: str,
    script: str,
    port: int | None,
    timeout: float,
    log: LogFn,
    cancel: CancelToken,
) -> tuple[bool, str]:
    """
    SSH: ``bash -s`` и тело скрипта на stdin (как ``ssh host bash -s <<'EOF'``).
    Без лишнего экранирования одной строки; удобно для nvm, cd, &&, pm2.
    """
    script = script.strip()
    if not script:
        return True, "OK"
    if not script.endswith("\n"):
        script += "\n"
    if log:
        log("server-sh: bash -s <<'EOF'", "info")
        for line in script.splitlines():
            log(line, "info")
        log("EOF", "info")
    return run_ssh_script_stdin(
        host,
        script,
        ssh_port=port,
        timeout_sec=timeout,
        log=None,
        cancel=cancel,
    )


def run_merged_command_list(
    project_id: str,
    list_key: str,
    cfg: dict,
    log: LogFn,
    cancel: CancelToken,
    *,
    local_cwd: Path | None = None,
    require_ssh_host: bool = True,
    secrets: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """
    Списки команд (см. merge_command_lists в config_store):
    - local-sh:… — на ПК через bash -lc (как в терминале);
    - local:… — на ПК, одна программа (argv, без shell);
    - server-sh:… — SSH, скрипт через bash -s <<'EOF' (stdin, shell на VPS);
    - server:… — одна SSH-команда (строка как есть);
    - без префикса — тоже SSH (как раньше, для совместимости).
    """
    port, bad = ssh_port_for_cli(cfg.get("ssh_port"))
    if bad:
        return False, "invalid port"
    host = (cfg.get("ssh_host") or "").strip()
    if require_ssh_host and not host:
        return False, "ssh_host empty"
    commands = merge_command_lists(project_id, list_key)
    timeout = float(cfg.get("ssh_command_timeout_sec") or 120)
    for raw in commands:
        cancel.raise_if_cancelled()
        line = raw.strip()
        if not line:
            continue
        if secrets:
            line = substitute(line, secrets)
        if line.startswith(LOCAL_SH_PREFIX):
            ok, out = _run_local_shell_script(
                _strip_prefix(line, LOCAL_SH_PREFIX),
                local_cwd,
                log,
                cancel,
                timeout,
            )
        elif line.startswith(LOCAL_PREFIX):
            ok, out = _run_local_shell(
                _strip_prefix(line, LOCAL_PREFIX),
                local_cwd,
                log,
                cancel,
                timeout,
            )
        elif line.startswith(SERVER_SH_PREFIX):
            ok, out = _run_remote_shell_script(
                host,
                _strip_prefix(line, SERVER_SH_PREFIX),
                port,
                timeout,
                log,
                cancel,
            )
        elif line.startswith(SERVER_PREFIX):
            ok, out = _run_remote_shell(
                host,
                _strip_prefix(line, SERVER_PREFIX),
                port,
                timeout,
                log,
                cancel,
                log_label="server",
            )
        else:
            ok, out = _run_remote_shell(
                host,
                line,
                port,
                timeout,
                log,
                cancel,
                log_label="ssh",
            )
        if not ok:
            return False, out
    return True, "OK"
