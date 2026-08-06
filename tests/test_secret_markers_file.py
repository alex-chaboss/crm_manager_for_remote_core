"""Тесты парсера файла секретов."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from crm.secret_markers import load_secrets_file, parse_secrets_file_lines


class TestParseSecretsFileLines(unittest.TestCase):
    def test_basic(self) -> None:
        text = """<$postgres_password>=PWD_123
<$secret_for_ws>=Secret_123
"""
        secrets, warnings = parse_secrets_file_lines(text)
        self.assertEqual(warnings, [])
        self.assertEqual(
            secrets,
            {"postgres_password": "PWD_123", "secret_for_ws": "Secret_123"},
        )

    def test_comments_and_empty(self) -> None:
        text = """
# comment
<$a>=1

<$b>=2
"""
        secrets, warnings = parse_secrets_file_lines(text)
        self.assertEqual(warnings, [])
        self.assertEqual(secrets, {"a": "1", "b": "2"})

    def test_duplicate_last_wins(self) -> None:
        text = "<$x>=first\n<$x>=second\n"
        secrets, _ = parse_secrets_file_lines(text)
        self.assertEqual(secrets, {"x": "second"})

    def test_empty_value_skipped(self) -> None:
        text = "<$empty>=\n<$ok>=yes\n"
        secrets, warnings = parse_secrets_file_lines(text)
        self.assertEqual(warnings, [])
        self.assertEqual(secrets, {"ok": "yes"})
        self.assertNotIn("empty", secrets)

    def test_value_with_equals(self) -> None:
        text = "<$k>=a=b=c\n"
        secrets, warnings = parse_secrets_file_lines(text)
        self.assertEqual(warnings, [])
        self.assertEqual(secrets, {"k": "a=b=c"})

    def test_invalid_line_warning(self) -> None:
        text = "<$bad>no_equals\n<$good>=1\n"
        secrets, warnings = parse_secrets_file_lines(text)
        self.assertEqual(secrets, {"good": "1"})
        self.assertEqual(len(warnings), 1)
        self.assertIn("line 1", warnings[0])

    def test_no_equals_warning(self) -> None:
        text = "not_a_secret_line\n"
        secrets, warnings = parse_secrets_file_lines(text)
        self.assertEqual(secrets, {})
        self.assertEqual(len(warnings), 1)


class TestLoadSecretsFile(unittest.TestCase):
    def test_load_from_disk(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("<$t>=val\n")
            path = Path(f.name)
        try:
            secrets, warnings = load_secrets_file(path)
            self.assertEqual(secrets, {"t": "val"})
            self.assertEqual(warnings, [])
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
