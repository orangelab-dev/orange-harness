"""限制在当前 workspace 内的文件读取和搜索工具。"""

import os
from pathlib import Path, PurePath

from .registry import tool


_WORKSPACE = Path.cwd().resolve()
_MAX_DEPTH = 5
_MAX_RESULTS = 200
_MAX_OUTPUT_CHARS = 20_000
_MAX_SEARCH_FILE_BYTES = 1_000_000


def _workspace_path(path: str) -> Path:
    """解析路径，并拒绝 workspace 外的目标和逃逸软链接。"""

    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = _WORKSPACE / candidate

    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError) as error:
        raise ValueError(f"无法解析路径：{path}") from error

    if not resolved.is_relative_to(_WORKSPACE):
        raise ValueError(f"路径必须位于 workspace 内：{path}")
    return resolved


def _relative_path(path: Path) -> str:
    """把绝对路径转换成模型更容易阅读的 workspace 相对路径。"""

    relative = path.relative_to(_WORKSPACE)
    return "." if not relative.parts else relative.as_posix()


def _truncate(text: str) -> str:
    """限制返回给模型的文字长度。"""

    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    return text[:_MAX_OUTPUT_CHARS] + "\n...（输出已截断）"


def _iter_files(directory: Path):
    """遍历目录中的普通文件，不跟随目录软链接。"""

    for root, directories, files in os.walk(directory, followlinks=False):
        root_path = Path(root)

        # 不进入指向 workspace 外部的目录软链接。
        directories[:] = [
            name
            for name in directories
            if (root_path / name).resolve().is_relative_to(_WORKSPACE)
        ]

        for name in files:
            try:
                file_path = _workspace_path(str(root_path / name))
            except ValueError:
                continue
            if file_path.is_file():
                yield file_path


@tool(approval="allow")
def read_file(
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """读取 workspace 内的文本文件，可使用从 1 开始的行号限制范围。"""

    file_path = _workspace_path(path)
    if not file_path.is_file():
        raise ValueError(f"不是文件：{path}")

    start = 1 if start_line is None else start_line
    if start < 1:
        raise ValueError("start_line 必须大于等于 1")
    if end_line is not None and end_line < start:
        raise ValueError("end_line 必须大于等于 start_line")

    selected: list[str] = []
    selected_chars = 0
    try:
        with file_path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if line_number < start:
                    continue
                if end_line is not None and line_number > end_line:
                    break

                selected_line = line.rstrip("\r\n")
                selected.append(selected_line)
                selected_chars += len(selected_line) + 1
                if selected_chars > _MAX_OUTPUT_CHARS:
                    break
    except UnicodeDecodeError as error:
        raise ValueError(f"不是 UTF-8 文本文件：{path}") from error

    return _truncate("\n".join(selected))


@tool(approval="allow")
def list_dir(path: str, depth: int = 1) -> str:
    """列出 workspace 内的目录，depth 表示递归层数，范围为 1 到 5。"""

    directory = _workspace_path(path)
    if not directory.is_dir():
        raise ValueError(f"不是目录：{path}")
    if not 1 <= depth <= _MAX_DEPTH:
        raise ValueError(f"depth 必须在 1 到 {_MAX_DEPTH} 之间")

    results: list[str] = []

    def visit(current: Path, level: int) -> None:
        if len(results) >= _MAX_RESULTS:
            return

        for entry in sorted(current.iterdir(), key=lambda item: item.name.lower()):
            if len(results) >= _MAX_RESULTS:
                return

            try:
                resolved = _workspace_path(str(entry))
            except ValueError:
                # 可以看到 workspace 内有这个入口，但不会读取它指向的外部内容。
                results.append(f"{_relative_path(entry)} [workspace 外链接，已跳过]")
                continue

            is_directory = resolved.is_dir()
            results.append(f"{_relative_path(entry)}{'/' if is_directory else ''}")
            if is_directory and level < depth and not entry.is_symlink():
                visit(resolved, level + 1)

    visit(directory, 1)
    if len(results) >= _MAX_RESULTS:
        results.append("...（结果已截断）")
    return _truncate("\n".join(results))


@tool(approval="allow")
def search_text(query: str, path: str = ".") -> str:
    """在 workspace 内递归搜索 UTF-8 文本，按“文件:行号:内容”返回。"""

    if not query:
        raise ValueError("query 不能为空")

    target = _workspace_path(path)
    if not target.is_file() and not target.is_dir():
        raise ValueError(f"路径不存在：{path}")
    files = [target] if target.is_file() else _iter_files(target)
    results: list[str] = []

    for file_path in files:
        try:
            if file_path.stat().st_size > _MAX_SEARCH_FILE_BYTES:
                continue
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        for line_number, line in enumerate(lines, start=1):
            if query in line:
                results.append(
                    f"{_relative_path(file_path)}:{line_number}:{line[:500]}"
                )
                if len(results) >= _MAX_RESULTS:
                    results.append("...（结果已截断）")
                    return _truncate("\n".join(results))

    return _truncate("\n".join(results))


@tool(approval="allow")
def find_files(pattern: str, path: str = ".") -> str:
    """在 workspace 内按 glob pattern 查找文件，例如 ``*.py`` 或 ``**/*.md``。"""

    pattern_path = PurePath(pattern)
    if not pattern or pattern_path.is_absolute() or ".." in pattern_path.parts:
        raise ValueError("pattern 必须是 workspace 内的相对 glob 表达式")

    directory = _workspace_path(path)
    if not directory.is_dir():
        raise ValueError(f"不是目录：{path}")

    results: list[str] = []
    for candidate in directory.glob(pattern):
        try:
            resolved = _workspace_path(str(candidate))
        except ValueError:
            continue
        if resolved.is_file():
            results.append(_relative_path(candidate))
            if len(results) >= _MAX_RESULTS:
                results.append("...（结果已截断）")
                break

    return _truncate("\n".join(sorted(results)))
