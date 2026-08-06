"""Маркеры секретов <$name> в командах: поиск, подстановка (RAM), маскирование лога."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

MARKER_RE = re.compile(r"<\$(\w+)>")
LINE_MARKER_RE = re.compile(r"^<\$(\w+)>=")


def extract_markers(commands: list[str]) -> list[str]:
    """Уникальные имена маркеров в порядке первого появления."""
    seen: set[str] = set()
    result: list[str] = []
    for cmd in commands:
        for m in MARKER_RE.finditer(cmd):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                result.append(name)
    return result


def parse_secrets_file_lines(text: str) -> tuple[dict[str, str], list[str]]:
    """
    Парсит текст файла секретов: строки ``<$name>=значение``.
    Возвращает (словарь name→value только для непустых значений, предупреждения).
    Предупреждения не содержат значений секретов.
    """
    secrets: dict[str, str] = {}
    warnings: list[str] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            warnings.append(f"line {line_no}: expected <$name>=value")
            continue
        eq = line.index("=")
        left = line[:eq].strip()
        value = line[eq + 1 :]
        m = LINE_MARKER_RE.match(left + "=")
        if not m:
            warnings.append(f"line {line_no}: expected <$name>=value")
            continue
        name = m.group(1)
        if not value:
            continue
        secrets[name] = value
    return secrets, warnings


def load_secrets_file(path: Path) -> tuple[dict[str, str], list[str]]:
    """Читает UTF-8 файл секретов. FileNotFoundError — вызывающий код."""
    text = path.read_text(encoding="utf-8")
    return parse_secrets_file_lines(text)


def substitute(text: str, secrets: dict[str, str]) -> str:
    """Заменяет <$name> на значение из *secrets*; незнакомые маркеры остаются."""
    def _repl(m: re.Match) -> str:
        return secrets.get(m.group(1), m.group(0))
    return MARKER_RE.sub(_repl, text)


def make_masked_log(
    log_fn: Callable[[str, str], None],
    secrets: dict[str, str],
) -> Callable[[str, str], None]:
    """Обёртка над log_fn: заменяет значения секретов на ``***``."""
    if not secrets:
        return log_fn
    values = sorted(
        (v for v in secrets.values() if v),
        key=len,
        reverse=True,
    )
    if not values:
        return log_fn

    def masked(text: str, level: str = "info") -> None:
        safe = text
        for v in values:
            safe = safe.replace(v, "***")
        log_fn(safe, level)

    return masked
