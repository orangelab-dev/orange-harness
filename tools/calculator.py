"""计算器工具：这里只写普通业务函数，注册细节交给 @tool。"""

from .base import tool


# @tool 大致等价于：add = tool(add)。它会在本模块被导入时执行注册。
@tool
def add(a: float, b: float) -> float:
    """计算两个数字之和。"""
    return a + b


@tool
def subtract(a: float, b: float) -> float:
    """计算两个数字之差。"""
    return a - b


@tool
def multiply(a: float, b: float) -> float:
    """计算两个数字之积。"""
    return a * b


@tool
def divide(a: float, b: float) -> float:
    """计算两个数字之商。"""
    if b == 0:
        raise ValueError("除数不能为 0")
    return a / b
