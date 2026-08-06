"""Обрезка deploy-дерева и allowed_children_at."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from crm.sync_deploy import allowed_children_at, prune_deploy_tree_to_sync_paths


class TestAllowedChildrenAt(unittest.TestCase):
    def test_root_level(self) -> None:
        allowed = allowed_children_at(["back", "front/www"], "")
        self.assertEqual(allowed, {"back", "front"})

    def test_partial_front(self) -> None:
        allowed = allowed_children_at(["back", "front/www"], "front")
        self.assertEqual(allowed, {"www"})

    def test_whole_front_no_prune(self) -> None:
        self.assertIsNone(allowed_children_at(["front"], "front"))


class TestPruneDeployTree(unittest.TestCase):
    def test_removes_stale_siblings_under_front(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "front" / "www").mkdir(parents=True)
            (root / "front" / "www" / "index.html").write_text("ok", encoding="utf-8")
            (root / "front" / "src").mkdir()
            (root / "front" / "src" / "app.ts").write_text("", encoding="utf-8")
            (root / "back").mkdir()
            (root / "readme").write_text("", encoding="utf-8")

            prune_deploy_tree_to_sync_paths(root, ["back", "front/www"])

            self.assertTrue((root / "front" / "www" / "index.html").is_file())
            self.assertFalse((root / "front" / "src").exists())
            self.assertFalse((root / "readme").exists())
            self.assertTrue((root / "back").is_dir())


if __name__ == "__main__":
    unittest.main()
