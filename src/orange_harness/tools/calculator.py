"""计算器工具：这里只写普通业务函数，注册细节交给 @tool。"""

from typing import Literal

from .registry import tool


# @tool 大致等价于：calculate = tool(calculate)。模块被导入时会自动注册。
@tool(approval="allow")
def calculate(a: float, operator: Literal["+", "-", "*", "/"], b: float) -> float:
    """计算两个数字的加、减、乘、除。"""

    if operator == "+":
        return a + b
    if operator == "-":
        return a - b
    if operator == "*":
        return a * b

    if b == 0:
        raise ValueError("除数不能为 0")
    return a / b
