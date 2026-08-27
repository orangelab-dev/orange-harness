"""用户配置与 CLI 运行模式测试。"""

import os
import tempfile
import unittest
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from orange_harness.config import load_config, parse_args


class CliTests(unittest.TestCase):
    def test_default_mode_is_sandbox_with_deny(self):
        args = parse_args([])

        self.assertFalse(args.unsafe)
        self.assertEqual(args.approval, "deny")

    def test_all_six_mode_combinations(self):
        cases = [
            ([], False, "deny"),
            (["--approval", "policy"], False, "policy"),
            (["--approval", "auto"], False, "auto"),
            (["--unsafe"], True, "deny"),
            (["--unsafe", "--approval", "policy"], True, "policy"),
            (["--unsafe", "--approval", "auto"], True, "auto"),
        ]

        for argv, unsafe, approval in cases:
            with self.subTest(argv=argv):
                args = parse_args(argv)
                self.assertEqual(args.unsafe, unsafe)
                self.assertEqual(args.approval, approval)

    def test_system_environment_has_priority_over_config_file(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / ".env"
            config_file.write_text(
                "DEEPSEEK_API_KEY=from-file\nDEEPSEEK_MODEL=file-model\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {"DEEPSEEK_API_KEY": "from-system"},
                clear=True,
            ):
                load_config(config_file)
                self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "from-system")
                self.assertEqual(os.environ["DEEPSEEK_MODEL"], "file-model")

    def test_user_config_has_priority_over_workspace_config(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / ".env").write_text(
                "DEEPSEEK_API_KEY=from-workspace\n",
                encoding="utf-8",
            )
            user_config = workspace / "user.env"
            user_config.write_text(
                "DEEPSEEK_API_KEY=from-user-config\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True), chdir(workspace):
                load_config(user_config)
                self.assertEqual(
                    os.environ["DEEPSEEK_API_KEY"],
                    "from-user-config",
                )

    def test_workspace_env_is_fallback_when_user_config_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / ".env").write_text(
                "DEEPSEEK_API_KEY=from-workspace\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True), chdir(workspace):
                load_config(workspace / "missing-user-config")
                self.assertEqual(
                    os.environ["DEEPSEEK_API_KEY"],
                    "from-workspace",
                )


if __name__ == "__main__":
    unittest.main()
