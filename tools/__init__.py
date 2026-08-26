"""工具包的公共入口，以及需要注册的工具模块清单。"""

from .base import TOOL_REGISTRY, execute_tool, get_tool_schemas, tool

# 这里的导入不只是为了使用函数。
# Python 导入 calculator.py 时会执行其中的 @tool 装饰器，从而注册四个工具。
# 以后新增 tools/weather.py 时，也需要在这里显式导入它；当前不做自动目录扫描。
from .calculator import add, divide, multiply, subtract


__all__ = [
    "TOOL_REGISTRY",
    "add",
    "divide",
    "execute_tool",
    "get_tool_schemas",
    "multiply",
    "subtract",
    "tool",
]
