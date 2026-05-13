"""Каталоги приложения: корень, Projects, .cache."""

from __future__ import annotations

from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent
APP_ROOT = _PKG_ROOT.parent
PROJECTS_DIR = APP_ROOT / "Projects"
CACHE_DIR = APP_ROOT / ".cache"
GLOBAL_SETTINGS_PATH = CACHE_DIR / "global_settings.json"


def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def project_profile_path(project_id: str) -> Path:
    return project_dir(project_id) / "project_profile.json"
