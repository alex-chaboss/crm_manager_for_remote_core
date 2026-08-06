"""Обслуживание каталога Projects/ (вне git репозитория CRM)."""

from __future__ import annotations

import logging

from crm.create_git_repo_template import render_create_git_repo_sh
from crm.paths import project_dir
from crm.project_init import list_project_ids

logger = logging.getLogger(__name__)


def refresh_create_git_repo_scripts() -> list[str]:
    """Перезаписывает create_git_repo.sh во всех Projects/<id>/ актуальным шаблоном."""
    updated: list[str] = []
    for pid in list_project_ids():
        path = project_dir(pid) / "create_git_repo.sh"
        if not path.parent.is_dir():
            continue
        path.write_text(render_create_git_repo_sh(pid), encoding="utf-8")
        try:
            mode = path.stat().st_mode
            path.chmod(mode | 0o111)
        except OSError:
            pass
        updated.append(pid)
        logger.info("Обновлён %s", path)
    return updated
