"""通过统一沙箱 Backend 执行命令的 Shell 工具。"""

import os
import shlex
from pathlib import Path
from typing import Any

from ..sandbox import (
    ExecutionResult,
    SandboxUnavailableError,
    create_sandbox,
    execution_result,
)
from .registry import ApprovalDecision, tool


# 启动程序时固定 workspace，模型不能通过工具参数修改它。
_WORKSPACE = Path.cwd().resolve()

_SAFE_COMMANDS = {"ls", "pwd", "uname", "whoami"}
_DANGEROUS_COMMANDS = {"halt", "mkfs", "poweroff", "reboot", "shutdown"}


def _split_command(command: str) -> list[str]:
    """解析命令用于审批判断；解析失败时默认要求人工确认。"""

    try:
        return shlex.split(command)
    except ValueError:
        return []


def _inside_workspace(path: str) -> bool:
    """判断命令参数指向的路径是否仍在 workspace 内。"""

    try:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = _WORKSPACE / candidate
        return candidate.resolve().is_relative_to(_WORKSPACE)
    except (OSError, RuntimeError):
        return False


def _is_dangerous_target(target: str) -> bool:
    """判断删除目标是否明确指向根目录或用户目录。"""

    if target in {"/*", "$HOME", "${HOME}", "~", "~/*"}:
        return True

    try:
        resolved = Path(target).expanduser().resolve()
    except (OSError, RuntimeError):
        return False
    return resolved in {Path("/"), Path.home().resolve()}


def _is_safe_command(command: str) -> bool:
    """只放行语法简单且不会操作 workspace 外路径的只读命令。"""

    # 避免把 `pwd; rm ...` 或 `echo $(...)` 误判成安全命令。
    if any(character in command for character in ";&|><`$()\n"):
        return False

    parts = _split_command(command)
    if not parts or parts[0] not in _SAFE_COMMANDS:
        return False

    if parts[0] == "ls":
        paths = [part for part in parts[1:] if not part.startswith("-")]
        return all(_inside_workspace(path) for path in paths)

    # pwd、uname、whoami 只允许携带选项，不自动放行其他位置参数。
    return all(part.startswith("-") for part in parts[1:])


def _is_dangerous_command(command: str, depth: int = 0) -> bool:
    """识别少量非常明确、不应该执行的危险命令。"""

    # 只递归拆几层常见包装，不尝试实现完整 Shell Parser。
    if depth > 3:
        return False

    parts = _split_command(command)
    if not parts:
        return False

    executable = Path(parts[0]).name

    # command rm ... 只是给命令加了一层 Shell 包装。
    if executable == "command":
        wrapped = [part for part in parts[1:] if part != "--"]
        while wrapped and wrapped[0].startswith("-"):
            wrapped.pop(0)
        return bool(wrapped) and _is_dangerous_command(shlex.join(wrapped), depth + 1)

    # 对 sh -c '...' 中最明显的危险命令继续做基础识别。
    if executable in {"bash", "sh", "zsh"} and "-c" in parts:
        command_index = parts.index("-c") + 1
        if command_index < len(parts):
            return _is_dangerous_command(parts[command_index], depth + 1)

    if executable in _DANGEROUS_COMMANDS:
        return True

    # 第一版只拒绝最明显的递归强制删除根目录或用户目录。
    if executable == "rm":
        flags = "".join(part for part in parts[1:] if part.startswith("-")).lower()
        targets = {part for part in parts[1:] if not part.startswith("-")}
        targets_are_dangerous = any(_is_dangerous_target(target) for target in targets)
        return "r" in flags and "f" in flags and targets_are_dangerous

    return False


def _shell_approval(arguments: dict[str, Any]) -> ApprovalDecision:
    """根据 command 内容决定自动放行、人工确认或拒绝。"""

    command = arguments["command"]
    if _is_dangerous_command(command):
        return "deny"
    if _is_safe_command(command):
        return "allow"
    return "ask"


@tool(approval=_shell_approval)
def shell(command: str) -> ExecutionResult:
    """在当前 workspace 中通过所选 Sandbox Backend 执行命令。"""

    unsafe = os.getenv("ORANGE_HARNESS_UNSAFE", "").lower() in {"1", "true", "yes"}

    try:
        sandbox = create_sandbox(unsafe=unsafe)
    except SandboxUnavailableError as error:
        return execution_result("sandbox_unavailable", message=str(error))

    return sandbox.run(command, str(_WORKSPACE))
