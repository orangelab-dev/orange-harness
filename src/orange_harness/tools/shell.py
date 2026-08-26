"""需要人工确认的本地 Shell 工具。"""

import subprocess
from pathlib import Path

from .registry import tool


# 启动程序时固定 workspace，模型不能通过工具参数修改它。
_WORKSPACE = Path.cwd().resolve()
_MAX_STREAM_LENGTH = 5_000


def _truncate(text: str) -> str:
    """限制单个输出流的长度，避免日志和模型上下文过大。"""

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


@tool
def shell(command: str) -> str:
    """在当前 workspace 执行 Shell 命令；每次执行前都需要人工确认。"""

    # 确认信息由 Harness 展示，模型只能决定 command，不能绕过确认或修改 cwd。
    print("\n[shell confirmation]")
    print(f"cwd: {_WORKSPACE}")
    print(f"command: {command}")
    confirmed = input("执行该命令？[y/N]: ").strip().lower()

    if confirmed not in {"y", "yes"}:
        return "命令未执行：用户拒绝。"

    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=_WORKSPACE,
        )
        exit_code = str(completed.returncode)
        stdout = _to_text(completed.stdout)
        stderr = _to_text(completed.stderr)
    except subprocess.TimeoutExpired as error:
        exit_code = "timeout"
        stdout = _to_text(error.stdout)
        stderr = _to_text(error.stderr) or "命令执行超过 30 秒，已终止。"

    return (
        f"exit_code: {exit_code}\n"
        f"stdout:\n{_truncate(stdout)}\n"
        f"stderr:\n{_truncate(stderr)}"
    )
