"""Shell 命令的统一沙箱执行层。"""

import platform
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal


_MAX_STREAM_LENGTH = 5_000
ExecutionStatus = Literal[
    "success",
    "failed",
    "timeout",
    "policy_denied",
    "user_denied",
    "sandbox_unavailable",
]
ExecutionResult = dict[str, Any]


class SandboxUnavailableError(RuntimeError):
    """当前平台没有可用沙箱，并且没有显式允许不安全执行。"""


def _truncate(text: str) -> str:
    """限制单个输出流长度，避免日志和模型上下文过大。"""

    if len(text) <= _MAX_STREAM_LENGTH:
        return text
    return f"{text[:_MAX_STREAM_LENGTH]}\n...（已截断，原始长度 {len(text)} 字符）"


def _to_text(output: str | bytes | None) -> str:
    """统一普通执行和超时异常中的输出类型。"""

    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output


def execution_result(
    status: ExecutionStatus,
    *,
    exit_code: int | None = None,
    stdout: str = "",
    stderr: str = "",
    message: str = "",
) -> ExecutionResult:
    """创建简单、统一的 Shell 执行结果。"""

    result: ExecutionResult = {
        "status": status,
        "exit_code": exit_code,
        "stdout": _truncate(stdout),
        "stderr": _truncate(stderr),
    }
    if message:
        result["message"] = message
    return result


def _run(command: str | list[str], workspace: str) -> ExecutionResult:
    """执行命令，并统一处理输出和超时。"""

    try:
        completed = subprocess.run(
            command,
            shell=isinstance(command, str),
            capture_output=True,
            text=True,
            timeout=30,
            cwd=workspace,
        )
        return execution_result(
            "success" if completed.returncode == 0 else "failed",
            exit_code=completed.returncode,
            stdout=_to_text(completed.stdout),
            stderr=_to_text(completed.stderr),
        )
    except subprocess.TimeoutExpired as error:
        return execution_result(
            "timeout",
            stdout=_to_text(error.stdout),
            stderr=_to_text(error.stderr),
            message="命令执行超过 30 秒，已终止。",
        )


class SandboxBackend(ABC):
    """所有 Shell 执行 Backend 的统一接口。"""

    @abstractmethod
    def run(self, command: str, workspace: str) -> ExecutionResult:
        """在指定 workspace 中执行命令。"""


class MacOSSandbox(SandboxBackend):
    """使用 macOS sandbox-exec 限制命令的系统权限。"""

    _PROFILE = """
    (version 1)
    (deny default)
    (allow process*)
    (allow file-read*)
    (allow file-write* (subpath (param "WORKSPACE")))
    """

    @staticmethod
    def is_available() -> bool:
        """检查系统是否提供 sandbox-exec。"""

        return shutil.which("sandbox-exec") is not None

    def run(self, command: str, workspace: str) -> ExecutionResult:
        workspace = str(Path(workspace).resolve())
        sandbox_executable = shutil.which("sandbox-exec")
        if sandbox_executable is None:
            return execution_result(
                "sandbox_unavailable",
                message="找不到 macOS sandbox-exec。",
            )

        sandboxed_command = [
            sandbox_executable,
            "-D",
            f"WORKSPACE={workspace}",
            "-p",
            self._PROFILE,
            "/bin/sh",
            "-c",
            command,
        ]

        try:
            result = _run(sandboxed_command, workspace)
        except OSError as error:
            return execution_result(
                "sandbox_unavailable",
                message=f"macOS 沙箱启动失败：{error}",
            )

        # sandbox-exec 自身报错属于基础设施失败，不是用户命令执行失败。
        if result["status"] == "failed" and str(result["stderr"]).lstrip().startswith(
            "sandbox-exec:"
        ):
            result["status"] = "sandbox_unavailable"
            result["message"] = "macOS 沙箱启动失败。"
        return result


class NoSandbox(SandboxBackend):
    """不提供系统级隔离，直接在宿主机执行命令。"""

    def run(self, command: str, workspace: str) -> ExecutionResult:
        workspace = str(Path(workspace).resolve())
        return _run(command, workspace)


def create_sandbox(*, unsafe: bool = False) -> SandboxBackend:
    """选择执行 Backend；NoSandbox 只能通过 unsafe 显式启用。"""

    if unsafe:
        return NoSandbox()

    if platform.system() == "Darwin" and MacOSSandbox.is_available():
        return MacOSSandbox()

    raise SandboxUnavailableError(
        "当前平台没有可用的系统沙箱；如确认接受风险，请显式开启 unsafe。"
    )
