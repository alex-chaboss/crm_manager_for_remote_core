"""Проверки перед привязкой локального boss_server к remote."""

from __future__ import annotations

from pathlib import Path

README_NAMES = {"README.md", "README_CRM_BOSS.md", "readme"}


def boss_server_bind_warning(boss_dir: Path) -> str | None:
    """
    Текст предупреждения, если привязка может затронуть существующие файлы.
    None — подтверждение не требуется.
    """
    boss = boss_dir.resolve()
    if not boss.is_dir():
        return None
    entries = [p for p in boss.iterdir() if p.name != ".git"]
    meaningful = [p for p in entries if p.name not in README_NAMES]
    if not meaningful:
        return None
    if not (boss / ".git").is_dir():
        return (
            "В boss_server уже есть файлы, репозитория git ещё нет. "
            "Привязка добавит remote и может изменить историю. Продолжить?"
        )
    return (
        "В boss_server уже есть каталог .git и другие файлы. "
        "Привязка обновит remote и выполнит fetch/pull. Продолжить?"
    )
