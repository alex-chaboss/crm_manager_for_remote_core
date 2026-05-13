"""SSH: git pull на сервере и перезапуск."""

from __future__ import annotations

import logging
import subprocess

from crm.config_store import build_ssh_remote_command, ssh_port_for_cli

logger = logging.getLogger(__name__)


def ssh_argv(ssh_host: str, remote_command: str, port: int | None) -> list[str]:
    argv: list[str] = ["ssh"]
    if port is not None:
        argv.extend(["-p", str(port)])
    argv.extend([ssh_host.strip(), remote_command])
    return argv


def ssh_restart(
    ssh_host: str,
    remote_command: str,
    timeout_sec: float,
    ssh_port: int | None = None,
) -> tuple[bool, str]:
    if not (ssh_host or "").strip():
        return False, "Не задан ssh_host"
    timeout_sec = max(30.0, min(3600.0, float(timeout_sec)))
    argv = ssh_argv(ssh_host, remote_command, ssh_port)
    try:
        r = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        if r.returncode != 0:
            return False, r.stderr or r.stdout or "Ошибка SSH"
        return True, (r.stdout or r.stderr or "OK").strip() or "Сервис перезапущен"
    except subprocess.TimeoutExpired:
        lim = int(round(timeout_sec))
        return (
            False,
            f"Таймаут SSH ({lim} с). Проверьте хост, ключи и при необходимости увеличьте таймаут.",
        )
    except FileNotFoundError:
        return False, "Команда ssh не найдена"
    except Exception as e:
        logger.exception("ssh_restart")
        return False, str(e)


def ssh_restart_from_config(cfg: dict) -> tuple[bool, str]:
    host = (cfg.get("ssh_host") or "").strip()
    cmd = build_ssh_remote_command(cfg)
    timeout_sec = float(cfg.get("ssh_command_timeout_sec") or 120)
    port, bad = ssh_port_for_cli(cfg.get("ssh_port"))
    if bad:
        return False, "Некорректный ssh_port в конфигурации"
    return ssh_restart(host, cmd, timeout_sec, port)
