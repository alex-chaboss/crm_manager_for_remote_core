"""Логика путей core_sync_paths без GUI."""

from __future__ import annotations

import unittest

from pathlib import Path
import tempfile

from crm.core_tree import (
    check_state_for_saved_path,
    collapse_stale_build_artifacts,
    collect_checked_paths,
    iter_relative_paths,
    minimize_sync_paths,
    normalize_sync_path,
    populate_core_tree,
)

try:
    from PyQt6.QtCore import Qt
except ImportError:  # pragma: no cover
    Qt = None  # type: ignore


@unittest.skipIf(Qt is None, "PyQt6 required")
class TestCheckStateForSavedPath(unittest.TestCase):
    def test_exact_path_checked(self) -> None:
        sel = {"front/www"}
        self.assertEqual(check_state_for_saved_path("front/www", sel), Qt.CheckState.Checked)

    def test_ancestor_partial_not_checked(self) -> None:
        sel = {"front/www/index.html"}
        self.assertEqual(check_state_for_saved_path("front", sel), Qt.CheckState.PartiallyChecked)
        self.assertEqual(check_state_for_saved_path("front/www", sel), Qt.CheckState.PartiallyChecked)
        self.assertEqual(
            check_state_for_saved_path("front/www/index.html", sel),
            Qt.CheckState.Checked,
        )

    def test_unrelated_unchecked(self) -> None:
        sel = {"back/main.js"}
        self.assertEqual(check_state_for_saved_path("front", sel), Qt.CheckState.Unchecked)


class TestMinimizeSyncPaths(unittest.TestCase):
    def test_drops_nested_when_parent_present(self) -> None:
        out = minimize_sync_paths(["front", "front/www", "back"])
        self.assertEqual(sorted(out), ["back", "front"])

    def test_keeps_siblings(self) -> None:
        out = minimize_sync_paths(["front/www", "front/src/a.ts"])
        self.assertEqual(sorted(out), ["front/src/a.ts", "front/www"])

    def test_normalize(self) -> None:
        self.assertEqual(normalize_sync_path(" front/www/ "), "front/www")


class TestCollapseStaleBuildArtifacts(unittest.TestCase):
    def test_collapses_hashed_chunks_to_www_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            www = root / "front" / "www"
            www.mkdir(parents=True)
            (www / "index.html").write_text("<html></html>", encoding="utf-8")
            stale = [
                "back/main.js",
                "front/www/4638.df995b2a5b1286b1.js",
                "front/www/index.html",
            ]
            out = collapse_stale_build_artifacts(root, stale)
            self.assertIn("back/main.js", out)
            self.assertIn("front/www", out)
            self.assertNotIn("front/www/4638.df995b2a5b1286b1.js", out)
            self.assertNotIn("front/www/index.html", out)

    def test_front_parent_replaced_by_www_not_dropped(self) -> None:
        """Регрессия: front + front/www/* → только front/www, не весь front/."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            www = root / "front" / "www"
            www.mkdir(parents=True)
            (www / "index.html").write_text("<html></html>", encoding="utf-8")
            (root / "front" / "src").mkdir(parents=True)
            stale = ["front", "front/www/old.chunk.js", "back/main.js"]
            out = collapse_stale_build_artifacts(root, stale)
            self.assertIn("front/www", out)
            self.assertNotIn("front", out)
            self.assertNotIn("front/src", out)

    def test_back_only_profile_gets_front_www(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            www = root / "front" / "www"
            www.mkdir(parents=True)
            (www / "index.html").write_text("<html></html>", encoding="utf-8")
            out = collapse_stale_build_artifacts(root, ["back/main.js", "back/package.json"])
            self.assertEqual(out, ["back/main.js", "back/package.json", "front/www"])


class TestIterRelativePaths(unittest.TestCase):
    def test_includes_dot_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".gitignore").write_text("front/www/\n", encoding="utf-8")
            (root / "back").mkdir()
            (root / "back" / "main.js").write_text("//", encoding="utf-8")
            paths = iter_relative_paths(root)
            self.assertIn(".gitignore", paths)
            self.assertIn("back", paths)
            self.assertIn("back/main.js", paths)

    def test_skips_git_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("[core]", encoding="utf-8")
            paths = iter_relative_paths(root)
            self.assertNotIn(".git", paths)
            self.assertFalse(any(p.startswith(".git/") for p in paths))


@unittest.skipIf(Qt is None, "PyQt6 required")
class TestCollectCheckedPaths(unittest.TestCase):
    def test_partially_checked_folder_without_children_saved(self) -> None:
        """Регрессия: front/www в профиле не теряется после перезагрузки дерева."""
        from PyQt6.QtWidgets import QApplication, QTreeWidget

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            www = root / "front" / "www"
            www.mkdir(parents=True)
            (www / "index.html").write_text("<html></html>", encoding="utf-8")
            tree = QTreeWidget()
            populate_core_tree(tree, root, {"front/www", "back/main.js"})
            paths = collect_checked_paths(tree)
            self.assertIn("front/www", paths)


if __name__ == "__main__":
    unittest.main()
