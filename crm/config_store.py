"""JSON: глобальные настройки CRM и профиль проекта."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

from crm.paths import CACHE_DIR, GLOBAL_SETTINGS_PATH, project_profile_path

logger = logging.getLogger(__name__)

GLOBAL_DEFAULTS: dict[str, Any] = {
    "ssh_host": "",
    "ssh_port": "",
    "ssh_restart_command": "true",
    "ssh_work_dir": "",
    "ssh_git_remote": "origin",
    "ssh_git_branch": "main",
    "ssh_command_timeout_sec": 120,
    "ui_locale": "ru",
}

PROJECT_DEFAULTS: dict[str, Any] = {
    "remote_server_core": "",
    "boss_server": "",
    "ssh_host": "",
    "ssh_port": "",
    "ssh_restart_command": "",
    "ssh_work_dir": "",
    "ssh_git_remote": "",
    "ssh_git_branch": "",
    "ssh_command_timeout_sec": 0,
}


def _ensure_cache() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_global() -> dict[str, Any]:
    _ensure_cache()
    if not GLOBAL_SETTINGS_PATH.is_file():
        return dict(GLOBAL_DEFAULTS)
    try:
        with open(GLOBAL_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = dict(GLOBAL_DEFAULTS)
        out.update({k: v for k, v in data.items() if k in GLOBAL_DEFAULTS})
        return out
    except Exception as e:
        logger.warning("load_global: %s", e)
        return dict(GLOBAL_DEFAULTS)


def save_global(updates: dict[str, Any]) -> None:
    _ensure_cache()
    cur = load_global()
    cur.update({k: v for k, v in updates.items() if k in GLOBAL_DEFAULTS})
    with open(GLOBAL_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(cur, f, indent=2, ensure_ascii=False)


def load_project(project_id: str) -> dict[str, Any]:
    p = project_profile_path(project_id)
    if not p.is_file():
        return dict(PROJECT_DEFAULTS)
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = dict(PROJECT_DEFAULTS)
        out.update({k: v for k, v in data.items() if k in PROJECT_DEFAULTS})
        return out
    except Exception as e:
        logger.warning("load_project %s: %s", project_id, e)
        return dict(PROJECT_DEFAULTS)


def save_project(project_id: str, updates: dict[str, Any]) -> None:
    p = project_profile_path(project_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    cur = load_project(project_id)
    cur.update({k: v for k, v in updates.items() if k in PROJECT_DEFAULTS})
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cur, f, indent=2, ensure_ascii=False)


def ssh_port_for_cli(raw: Any) -> tuple[int | None, bool]:
    """Порт для argv ssh -p: (None, False) = стандартный 22; (int, False); (_, True) = невалидное непустое."""
    if raw is None:
        return None, False
    s = str(raw).strip()
    if not s:
        return None, False
    try:
        p = int(s, 10)
    except ValueError:
        return None, True
    if p < 1 or p > 65535:
        return None, True
    return p, False


def validate_deploy_ssh(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    """Перед SSH: достаточно ли настроек. Коды ошибок: host_empty, port_invalid."""
    host = (cfg.get("ssh_host") or "").strip()
    if not host:
        return False, "host_empty"
    _, bad = ssh_port_for_cli(cfg.get("ssh_port"))
    if bad:
        return False, "port_invalid"
    return True, None


_GLOBAL_KEYS_NOT_FROM_PROJECT = frozenset({"ui_locale"})


def effective_ssh_config(project_id: str, project_root: Path) -> dict[str, Any]:
    """Слияние глобальных настроек и профиля проекта; пустые поля проекта берутся из global."""
    g = load_global()
    p = load_project(project_id)
    out = deepcopy(g)
    for key in GLOBAL_DEFAULTS:
        if key in _GLOBAL_KEYS_NOT_FROM_PROJECT:
            continue
        v = p.get(key)
        if isinstance(v, str) and v.strip():
            out[key] = v.strip()
        elif isinstance(v, (int, float)) and key == "ssh_command_timeout_sec" and v > 0:
            out[key] = int(v)
    # пути по умолчанию внутри проекта
    rsc = (p.get("remote_server_core") or "").strip()
    bs = (p.get("boss_server") or "").strip()
    out["remote_server_core_path"] = Path(rsc) if rsc else project_root / "remote_server_core"
    out["boss_server_path"] = Path(bs) if bs else project_root / "boss_server"
    to = int(p.get("ssh_command_timeout_sec") or 0)
    if to > 0:
        out["ssh_command_timeout_sec"] = max(30, min(3600, to))
    else:
        out["ssh_command_timeout_sec"] = max(
            30, min(3600, int(g.get("ssh_command_timeout_sec") or GLOBAL_DEFAULTS["ssh_command_timeout_sec"]))
        )
    return out


def build_ssh_remote_command(cfg: dict[str, Any]) -> str:
    """Команда на удалённой машине: cd work_dir && git … && restart (как в remote_server_config)."""
    restart_cmd = (cfg.get("ssh_restart_command") or "true").strip()
    work_dir = (cfg.get("ssh_work_dir") or "").strip()
    if not work_dir:
        return restart_cmd
    remote = (cfg.get("ssh_git_remote") or "origin").strip()
    branch = (cfg.get("ssh_git_branch") or "main").strip()
    return (
        f"cd {work_dir} && git add . && git stash && git pull {remote} {branch} && {restart_cmd}"
    )
