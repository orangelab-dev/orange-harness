"""工具框架的核心：把普通 Python 函数注册成大模型可以调用的工具。"""

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, TypeVar, get_type_hints, overload

from openai.types.responses import FunctionToolParam
from pydantic import BaseModel, ConfigDict, create_model


# F 表示“任意函数类型”。使用 TypeVar 是为了让 @tool 装饰后，IDE 仍然知道
# 原函数的参数和返回值类型；它不参与运行时的工具调用。
F = TypeVar("F", bound=Callable[..., Any])
ApprovalDecision = Literal["allow", "ask", "deny"]
ApprovalRule = ApprovalDecision | Callable[[dict[str, Any]], ApprovalDecision]


@dataclass(frozen=True)
class Tool:
    """一个已注册工具的完整资料。"""

    # 真正被执行的普通 Python 函数。
    func: Callable[..., Any]

    # 根据函数参数动态生成的 Pydantic 模型，用来验证模型传来的 JSON。
    input_model: type[BaseModel]

    # 发送给 Responses API 的工具说明书。
    schema: FunctionToolParam

    # Tool 自己声明的审批规则，可以是固定决定，也可以根据参数动态判断。
    approval: ApprovalRule


# 全局工具注册表，可以把它理解成：工具名称 -> 工具资料。
TOOL_REGISTRY: dict[str, Tool] = {}


@overload
def tool(func: F, *, approval: ApprovalRule = "ask") -> F: ...


@overload
def tool(
    func: None = None,
    *,
    approval: ApprovalRule = "ask",
) -> Callable[[F], F]: ...


def tool(
    func: F | None = None,
    *,
    approval: ApprovalRule = "ask",
) -> F | Callable[[F], F]:
    """把普通函数注册为 LLM Tool，并保存它的审批规则。"""

    # 同时支持 @tool 和 @tool(approval=...) 两种写法。
    if func is None:
        def decorator(decorated_func: F) -> F:
            return tool(decorated_func, approval=approval)

        return decorator

    if func.__name__ in TOOL_REGISTRY:
        raise ValueError(f"工具名称重复：{func.__name__}")

    # inspect.signature() 会读取函数的参数名称、注解和默认值。
    # 例如 calculate(a: float, operator: str, b: float) 会被读出三个参数。
    signature = inspect.signature(func)

    # get_type_hints() 把可能是字符串的类型注解解析成真正的 Python 类型。
    type_hints = get_type_hints(func)
    fields: dict[str, tuple[Any, Any]] = {}

    for name, parameter in signature.parameters.items():
        annotation = type_hints.get(name, parameter.annotation)
        if annotation is inspect.Parameter.empty:
            raise TypeError(f"工具参数 {name!r} 缺少类型注解")

        default = ... if parameter.default is inspect.Parameter.empty else parameter.default
        fields[name] = (annotation, default)

    # 根据刚才读到的 fields，在运行时创建 Pydantic 模型。
    # 对 calculate(a: float, operator: str, b: float) 来说，它大致等价于手写：
    #
    # class CalculateInput(BaseModel):
    #     a: float
    #     operator: str
    #     b: float
    #
    # extra="forbid" 表示拒绝函数没有声明的额外参数。
    input_model = create_model(
        f"{func.__name__.title()}Input",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )

    # 将函数信息翻译成 DeepSeek 能看懂的 Tool Schema。
    # 函数名成为工具名，docstring 成为描述，Pydantic 模型生成参数 JSON Schema。
    schema = FunctionToolParam(
        type="function",
        name=func.__name__,
        description=inspect.getdoc(func) or "",
        parameters=input_model.model_json_schema(),
        strict=False,
    )

    # 装饰器最关键的一步：导入模块时，把工具放进全局注册表。
    TOOL_REGISTRY[func.__name__] = Tool(func, input_model, schema, approval)

    # 返回原函数，所以 calculate(1, "+", 2) 仍可像普通函数一样调用。
    return func


def get_tool_schemas() -> list[FunctionToolParam]:
    """取出所有工具的说明书，交给大模型选择。"""

    return [registered_tool.schema for registered_tool in TOOL_REGISTRY.values()]
