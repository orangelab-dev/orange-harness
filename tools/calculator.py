from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CalculatorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    a: float = Field(description="第一个数字")
    operator: Literal["+", "-", "*", "/"] = Field(description="运算符")
    b: float = Field(description="第二个数字")


CALCULATOR_TOOL = {
    "type": "function",
    "name": "calculate",
    "description": "计算两个数字的加、减、乘、除。",
    "parameters": CalculatorInput.model_json_schema(),
}


def calculate(arguments: str) -> str:
    data = CalculatorInput.model_validate_json(arguments)

    if data.operator == "+":
        result = data.a + data.b
    elif data.operator == "-":
        result = data.a - data.b
    elif data.operator == "*":
        result = data.a * data.b
    elif data.b == 0:
        return "计算失败：除数不能为 0"
    else:
        result = data.a / data.b

    return str(result)
