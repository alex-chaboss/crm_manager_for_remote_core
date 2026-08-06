"""JSON: глобальные настройки CRM и профиль проекта."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

from crm.paths import (
    CACHE_DIR,
    GLOBAL_SETTINGS_PATH,
    legacy_project_profile_path,
    project_cache_dir,
    project_profile_path,
)

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
    "server_base_path": "",
    "pre_init_commands": [],
    "post_init_commands": [],
    "pre_deploy_commands": [],
    "post_deploy_commands": [],
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
    "server_base_path": "",
    "server_project_name": "",
    "server_git_branch": "master",
    "server_remote_alias": "",
    "pre_init_commands": [],
    "post_init_commands": [],
    "pre_deploy_commands": [],
    "post_deploy_commands": [],
    "merge_global_commands": False,
    "source_git_url": "",
    "secrets_file_path": "",
    "auto_sync_enabled": False,
    "core_sync_paths": [],
}


def _normalize_loaded(data: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    out = dict(defaults)
    for k, default in defaults.items():
        if k not in data:
            continue
        v = data[k]
        if isinstance(default, list):
            out[k] = list(v) if isinstance(v, list) else []
        elif isinstance(default, bool):
            out[k] = bool(v)
        else:
            out[k] = v
    return out


def _ensure_cache() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_global() -> dict[str, Any]:
    _ensure_cache()
    if not GLOBAL_SETTINGS_PATH.is_file():
        return dict(GLOBAL_DEFAULTS)
    try:
        with open(GLOBAL_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _normalize_loaded(data, GLOBAL_DEFAULTS)
    except Exception as e:
        logger.warning("load_global: %s", e)
        return dict(GLOBAL_DEFAULTS)


def save_global(updates: dict[str, Any]) -> None:
    _ensure_cache()
    cur = load_global()
    for k, v in updates.items():
        if k in GLOBAL_DEFAULTS:
            cur[k] = v
    with open(GLOBAL_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(cur, f, indent=2, ensure_ascii=False)


def _read_project_profile_file(path: Path, project_id: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = _normalize_loaded(data, PROJECT_DEFAULTS)
        if not (out.get("server_project_name") or "").strip():
            out["server_project_name"] = project_id
        return out
    except Exception as e:
        logger.warning("load_project %s from %s: %s", project_id, path, e)
        return None


def load_project(project_id: str) -> dict[str, Any]:
    p = project_profile_path(project_id)
    loaded = _read_project_profile_file(p, project_id)
    if loaded is not None:
        return loaded

    legacy = legacy_project_profile_path(project_id)
    loaded = _read_project_profile_file(legacy, project_id)
    if loaded is not None:
        logger.info(
            "load_project %s: migrated profile from %s to %s",
            project_id,
            legacy,
            p,
        )
        save_project(project_id, loaded)
        return loaded

    out = dict(PROJECT_DEFAULTS)
    out["server_project_name"] = project_id
    return out


def save_project(project_id: str, updates: dict[str, Any]) -> None:
    project_cache_dir(project_id).mkdir(parents=True, exist_ok=True)
    p = project_profile_path(project_id)
    cur = _read_project_profile_file(p, project_id)
    if cur is None:
        cur = _read_project_profile_file(legacy_project_profile_path(project_id), project_id)
    if cur is None:
        cur = dict(PROJECT_DEFAULTS)
        cur["server_project_name"] = project_id
    for k, v in updates.items():
        if k in PROJECT_DEFAULTS:
            cur[k] = v
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cur, f, indent=2, ensure_ascii=False)


def _command_lines_from_profile(data: dict[str, Any], key: str) -> list[str]:
    out: list[str] = []
    src = data.get(key)
    if not isinstance(src, list):
        return out
    for line in src:
        s = str(line).strip()
        if s:
            out.append(s)
    return out


def merge_command_lists(project_id: str, key: str) -> list[str]:
    """
    Списки pre/post init/deploy:
    - merge_global_commands=True: global, затем project (как раньше);
    - False (по умолчанию): только project, если непустой; иначе только global.
    """
    g = load_global()
    p = load_project(project_id)
    project_lines = _command_lines_from_profile(p, key)
    global_lines = _command_lines_from_profile(g, key)
    if bool(p.get("merge_global_commands")):
        return global_lines + project_lines
    if project_lines:
        return project_lines
    return global_lines


def ssh_port_for_cli(raw: Any) -> tuple[int | None, bool]:
    if raw is None:
        return None, False
    s = str(raw).strip()
    if not s:
        return None, False
    try:
        port = int(s, 10)
    except ValueError:
        return None, True
    if port < 1 or port > 65535:
        return None, True
    return port, False


def validate_deploy_ssh(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    host = (cfg.get("ssh_host") or "").strip()
    if not host:
        return False, "host_empty"
    _, bad = ssh_port_for_cli(cfg.get("ssh_port"))
    if bad:
        return False, "port_invalid"
    return True, None


_GLOBAL_KEYS_NOT_FROM_PROJECT = frozenset(
    {"ui_locale", "pre_init_commands", "post_init_commands", "pre_deploy_commands", "post_deploy_commands"}
)


def effective_ssh_config(project_id: str, project_root: Path) -> dict[str, Any]:
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
    rsc = (p.get("remote_server_core") or "").strip()
    bs = (p.get("boss_server") or "").strip()
    out["remote_server_core_path"] = Path(rsc) if rsc else project_root / "remote_server_core"
    out["boss_server_path"] = Path(bs) if bs else project_root / "boss_server"
    out["project_core_path"] = project_root / "project_core"
    to = int(p.get("ssh_command_timeout_sec") or 0)
    if to > 0:
        out["ssh_command_timeout_sec"] = max(30, min(3600, to))
    else:
        out["ssh_command_timeout_sec"] = max(
            30, min(3600, int(g.get("ssh_command_timeout_sec") or GLOBAL_DEFAULTS["ssh_command_timeout_sec"]))
        )
    sb = (p.get("server_base_path") or "").strip() or (g.get("server_base_path") or "").strip()
    out["server_base_path"] = sb
    out["server_project_name"] = (p.get("server_project_name") or "").strip() or project_id
    out["server_git_branch"] = (p.get("server_git_branch") or "").strip() or "master"
    alias = (p.get("server_remote_alias") or "").strip()
    out["server_remote_alias"] = alias or out["server_project_name"]
    if not (out.get("ssh_work_dir") or "").strip() and sb:
        out["ssh_work_dir"] = f"{sb.rstrip('/')}/{out['server_project_name']}"
    return out


def build_ssh_shell_command(cfg: dict[str, Any], remote_command: str) -> str:
    """Одна команда на сервере (без git pull — hook обновляет рабочую копию)."""
    work_dir = (cfg.get("ssh_work_dir") or "").strip()
    if work_dir:
        return f"cd {work_dir} && {remote_command}"
    return remote_command


def build_ssh_restart_command(cfg: dict[str, Any]) -> str:
    restart = (cfg.get("ssh_restart_command") or "true").strip()
    return build_ssh_shell_command(cfg, restart)
