"""文件工具的 workspace 边界与核心行为测试。"""

import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


filesystem = importlib.import_module("orange_harness.tools.filesystem")


class FilesystemToolTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.outside = root / "outside.txt"
        self.outside.write_text("secret", encoding="utf-8")

        (self.workspace / "notes.txt").write_text(
            "first\nfind me\nthird\n",
            encoding="utf-8",
        )
        source = self.workspace / "src"
        source.mkdir()
        (source / "app.py").write_text("print('find me')\n", encoding="utf-8")

        self.workspace_patch = patch.object(
            filesystem,
            "_WORKSPACE",
            self.workspace.resolve(),
        )
        self.workspace_patch.start()

    def tearDown(self):
        self.workspace_patch.stop()
        self.temporary_directory.cleanup()

    def test_read_file_supports_line_range(self):
        result = filesystem.read_file("notes.txt", start_line=2, end_line=3)

        self.assertEqual(result, "find me\nthird")

    def test_list_dir_respects_depth(self):
        shallow = filesystem.list_dir(".", depth=1)
        deep = filesystem.list_dir(".", depth=2)

        self.assertIn("src/", shallow)
        self.assertNotIn("src/app.py", shallow)
        self.assertIn("src/app.py", deep)

    def test_search_text_returns_file_and_line_number(self):
        result = filesystem.search_text("find me")

        self.assertIn("notes.txt:2:find me", result)
        self.assertIn("src/app.py:1:print('find me')", result)

    def test_find_files_supports_recursive_glob(self):
        result = filesystem.find_files("**/*.py")

        self.assertEqual(result, "src/app.py")

    def test_all_tools_reject_paths_outside_workspace(self):
        calls = [
            lambda: filesystem.read_file("../outside.txt"),
            lambda: filesystem.list_dir(".."),
            lambda: filesystem.search_text("secret", ".."),
            lambda: filesystem.find_files("*.txt", ".."),
        ]

        for call in calls:
            with self.subTest(call=call), self.assertRaisesRegex(
                ValueError,
                "workspace 内",
            ):
                call()

    def test_find_files_rejects_parent_directory_pattern(self):
        with self.assertRaisesRegex(ValueError, "相对 glob"):
            filesystem.find_files("../*.txt")


if __name__ == "__main__":
    unittest.main()
