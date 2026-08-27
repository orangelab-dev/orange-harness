"""工具包的公共入口，并在导入时递归加载所有工具模块。"""

from importlib import import_module
from pkgutil import walk_packages

from .executor import execute_tool
from .registry import TOOL_REGISTRY, get_tool_schemas, tool


def _load_tools():
    """递归导入 tools 包中的模块，触发其中的 @tool 装饰器。"""

    prefix = f"{__name__}."

    for module in walk_packages(__path__, prefix):
        relative_name = module.name.removeprefix(prefix)

        # registry.py 和 executor.py 是框架本身；下划线开头的模块视为内部实现。
        if relative_name in {"executor", "registry"}:
            continue
        if any(part.startswith("_") for part in relative_name.split(".")):
            continue

        import_module(module.name)


_load_tools()

# 保留现有工具的包级公开导入；工具注册本身已经由 _load_tools() 完成。
from .calculator import calculate
from .shell import shell


__all__ = [
    "TOOL_REGISTRY",
    "calculate",
    "execute_tool",
    "get_tool_schemas",
    "shell",
    "tool",
]
