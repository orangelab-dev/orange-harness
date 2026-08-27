"""Tool 审批生命周期的核心测试。"""

import unittest

from pydantic import ValidationError

from orange_harness.tools.registry import execute_tool, tool
from orange_harness.tools.shell import _shell_approval


@tool(approval="allow")
def approval_allow_test(value: int) -> int:
    """测试静态放行。"""

    return value


@tool(approval="ask")
def approval_ask_test(value: int) -> int:
    """测试人工审批。"""

    return value


@tool(approval="deny")
def approval_deny_test(value: int) -> int:
    """测试策略拒绝。"""

    return value


@tool(approval=lambda _: "invalid")  # type: ignore[arg-type, return-value]
def approval_invalid_test(value: int) -> int:
    """测试非法审批决定。"""

    return value


class ApprovalTests(unittest.TestCase):
    def test_allow_executes_and_emits_result(self):
        events = []

        result = execute_tool(
            "approval_allow_test",
            '{"value": 1}',
            on_event=events.append,
        )

        self.assertEqual(result, 1)
        self.assertEqual(events[0]["type"], "approval_result")
        self.assertEqual(events[0]["data"]["status"], "allowed")

    def test_ask_can_be_approved(self):
        events = []

        result = execute_tool(
            "approval_ask_test",
            '{"value": 2}',
            request_approval=lambda _name, _arguments: True,
            on_event=events.append,
            approval_mode="policy",
        )

        self.assertEqual(result, 2)
        self.assertEqual(
            [event["type"] for event in events],
            ["approval_request", "approval_result"],
        )
        self.assertEqual(events[-1]["data"]["status"], "allowed")

    def test_user_denial_never_executes_tool(self):
        events = []

        result = execute_tool(
            "approval_ask_test",
            '{"value": 3}',
            request_approval=lambda _name, _arguments: False,
            on_event=events.append,
            approval_mode="policy",
        )

        self.assertEqual(result["status"], "user_denied")
        self.assertEqual(events[-1]["data"]["status"], "user_denied")

    def test_missing_handler_fails_closed(self):
        events = []

        result = execute_tool(
            "approval_ask_test",
            '{"value": 4}',
            on_event=events.append,
            approval_mode="policy",
        )

        self.assertEqual(result["status"], "policy_denied")
        self.assertEqual(events[-1]["data"]["reason"], "missing_handler")

    def test_tool_denial_cannot_be_bypassed_by_auto_mode(self):
        events = []

        result = execute_tool(
            "approval_deny_test",
            '{"value": 5}',
            request_approval=lambda _name, _arguments: self.fail(
                "策略拒绝不应该询问用户"
            ),
            on_event=events.append,
            approval_mode="auto",
        )

        self.assertEqual(result["status"], "policy_denied")
        self.assertEqual(events[-1]["data"]["status"], "policy_denied")
        self.assertEqual(events[-1]["data"]["reason"], "tool_policy_deny")

    def test_default_mode_denies_ask_without_prompting(self):
        events = []

        result = execute_tool(
            "approval_ask_test",
            '{"value": 6}',
            request_approval=lambda _name, _arguments: self.fail(
                "deny 模式不应该询问用户"
            ),
            on_event=events.append,
        )

        self.assertEqual(result["status"], "policy_denied")
        self.assertEqual(events[-1]["data"]["reason"], "approval_mode_deny")

    def test_auto_mode_executes_ask_without_prompting(self):
        events = []

        result = execute_tool(
            "approval_ask_test",
            '{"value": 7}',
            request_approval=lambda _name, _arguments: self.fail(
                "auto 模式不应该询问用户"
            ),
            on_event=events.append,
            approval_mode="auto",
        )

        self.assertEqual(result, 7)
        self.assertEqual(events[-1]["data"]["source"], "auto_mode")

    def test_invalid_approval_mode_raises(self):
        with self.assertRaisesRegex(ValueError, "无效的审批模式"):
            execute_tool(
                "approval_allow_test",
                '{"value": 8}',
                approval_mode="invalid",  # type: ignore[arg-type]
            )

    def test_invalid_approval_decision_raises(self):
        with self.assertRaisesRegex(ValueError, "无效的审批决定"):
            execute_tool("approval_invalid_test", '{"value": 6}')

    def test_arguments_are_validated_before_approval(self):
        called = False

        def approve(_name, _arguments):
            nonlocal called
            called = True
            return True

        with self.assertRaises(ValidationError):
            execute_tool(
                "approval_ask_test",
                '{"value": "not-an-integer"}',
                request_approval=approve,
                approval_mode="policy",
            )

        self.assertFalse(called)

    def test_shell_only_auto_allows_simple_workspace_commands(self):
        self.assertEqual(_shell_approval({"command": "pwd"}), "allow")
        self.assertEqual(_shell_approval({"command": "ls ."}), "allow")
        self.assertEqual(_shell_approval({"command": "ls /tmp"}), "ask")
        self.assertEqual(_shell_approval({"command": "ls .."}), "ask")
        self.assertEqual(_shell_approval({"command": "pwd; ls"}), "ask")

    def test_shell_denies_obvious_dangerous_variants(self):
        commands = [
            "rm -Rf /",
            "command rm -rf /",
            "command -- rm -fr /",
            "sh -c 'rm -Rf /'",
            "bash -c 'command rm -rf /'",
        ]

        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(_shell_approval({"command": command}), "deny")


if __name__ == "__main__":
    unittest.main()
