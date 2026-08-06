"""Тесты префиксов списков команд."""

from __future__ import annotations

import unittest

from crm.command_lists import (
    LOCAL_PREFIX,
    LOCAL_SH_PREFIX,
    SERVER_PREFIX,
    SERVER_SH_PREFIX,
)


class TestCommandPrefixes(unittest.TestCase):
    def test_local_sh_not_matched_as_local_only(self) -> None:
        line = f"{LOCAL_SH_PREFIX}cd foo && npm i"
        self.assertTrue(line.startswith(LOCAL_SH_PREFIX))
        self.assertFalse(line.startswith(LOCAL_PREFIX))

    def test_server_sh_not_matched_as_server_only(self) -> None:
        line = f"{SERVER_SH_PREFIX}export NVM_DIR=\"$HOME/.nvm\"; . \"$NVM_DIR/nvm.sh\"; npm -v"
        self.assertTrue(line.startswith(SERVER_SH_PREFIX))
        self.assertFalse(line.startswith(SERVER_PREFIX))

    def test_strip_order(self) -> None:
        line = f"{LOCAL_SH_PREFIX}echo ok"
        body = line[len(LOCAL_SH_PREFIX) :].strip()
        self.assertEqual(body, "echo ok")


if __name__ == "__main__":
    unittest.main()
