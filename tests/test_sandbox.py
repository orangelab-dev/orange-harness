"""Sandbox Backend 的核心测试，全程使用 mock。"""

import importlib
import subprocess
import unittest
from unittest.mock import patch

import orange_harness.sandbox as sandbox_module
from orange_harness.sandbox import (
    MacOSSandbox,
    NoSandbox,
    SandboxUnavailableError,
    create_sandbox,
    execution_result,
)


shell_module = importlib.import_module("orange_harness.tools.shell")


class SandboxTests(unittest.TestCase):
    def test_macos_uses_system_sandbox_when_available(self):
        with patch.object(sandbox_module.platform, "system", return_value="Darwin"), patch.object(
            MacOSSandbox, "is_available", return_value=True
        ):
            self.assertIsInstance(create_sandbox(), MacOSSandbox)

    def test_non_macos_does_not_fall_back_to_no_sandbox(self):
        with patch.object(sandbox_module.platform, "system", return_value="Linux"):
            with self.assertRaises(SandboxUnavailableError):
                create_sandbox()

    def test_missing_macos_sandbox_does_not_fall_back(self):
        with patch.object(sandbox_module.platform, "system", return_value="Darwin"), patch.object(
            MacOSSandbox, "is_available", return_value=False
        ):
            with self.assertRaises(SandboxUnavailableError):
                create_sandbox()

    def test_unsafe_explicitly_enables_no_sandbox(self):
        with patch.object(sandbox_module.platform, "system", return_value="Linux"):
            self.assertIsInstance(create_sandbox(unsafe=True), NoSandbox)

    def test_no_sandbox_only_executes(self):
        backend = NoSandbox()

        with patch.object(sandbox_module, "_run", return_value={"status": "success"}) as run, patch(
            "builtins.input"
        ) as user_input:
            result = backend.run("python script.py", ".")

        self.assertEqual(result["status"], "success")
        user_input.assert_not_called()
        run.assert_called_once()

    def test_sandbox_infrastructure_failure_is_distinct(self):
        failed = execution_result(
            "failed",
            exit_code=1,
            stderr="sandbox-exec: sandbox_apply: Operation not permitted",
        )

        with patch.object(sandbox_module.shutil, "which", return_value="/usr/bin/sandbox-exec"), patch.object(
            sandbox_module, "_run", return_value=failed
        ):
            result = MacOSSandbox().run("pwd", ".")

        self.assertEqual(result["status"], "sandbox_unavailable")

    def test_normal_command_failure_is_not_sandbox_failure(self):
        failed = execution_result(
            "failed",
            exit_code=1,
            stderr="touch: /outside: Operation not permitted",
        )

        with patch.object(sandbox_module.shutil, "which", return_value="/usr/bin/sandbox-exec"), patch.object(
            sandbox_module, "_run", return_value=failed
        ):
            result = MacOSSandbox().run("touch /outside", ".")

        self.assertEqual(result["status"], "failed")

    def test_shell_reports_unavailable_without_running_raw_command(self):
        shell_module.configure_shell(unsafe=False)

        with patch.object(
            shell_module,
            "create_sandbox",
            side_effect=SandboxUnavailableError("sandbox missing"),
        ), patch.object(sandbox_module, "_run") as run:
            result = shell_module.shell("pwd")

        self.assertEqual(result["status"], "sandbox_unavailable")
        run.assert_not_called()

    def test_shell_uses_no_sandbox_only_after_explicit_configuration(self):
        shell_module.configure_shell(unsafe=True)

        try:
            with patch.object(
                shell_module,
                "create_sandbox",
                return_value=NoSandbox(),
            ) as factory, patch.object(
                sandbox_module,
                "_run",
                return_value={"status": "success"},
            ):
                result = shell_module.shell("pwd")
        finally:
            # 避免模块级运行配置污染其他测试。
            shell_module.configure_shell(unsafe=False)

        self.assertEqual(result["status"], "success")
        factory.assert_called_once_with(unsafe=True)

    def test_timeout_has_structured_status(self):
        timeout = subprocess.TimeoutExpired("command", 30, output=b"partial")

        with patch.object(sandbox_module.subprocess, "run", side_effect=timeout):
            result = sandbox_module._run("command", ".")

        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["stdout"], "partial")


if __name__ == "__main__":
    unittest.main()
