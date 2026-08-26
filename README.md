# myHarness

一个最小的 Python Agent：使用 DeepSeek Responses API，通过 ReAct 循环调用本地工具。

## 运行机制

```text
用户输入
  ↓
Agent 把对话历史和 Tool Schema 发给 DeepSeek
  ↓
DeepSeek 返回最终答案或 function_call
  ↓ function_call
execute_tool() 从注册表找到工具
  ↓
Pydantic 校验 JSON 参数
  ↓
执行普通 Python 函数
  ↓
function_call_output 写回对话历史，继续调用 DeepSeek
```

DeepSeek API 不保存会话，因此 `agent.py` 会在本地维护完整的 `history`。

## 工具注册

工具只是加了 `@tool` 的普通函数：

```python
@tool
def add(a: float, b: float) -> float:
    """计算两个数字之和。"""
    return a + b
```

`@tool` 自动完成：

1. 用 `inspect.signature()` 读取参数。
2. 用 Pydantic 动态创建输入模型。
3. 生成 Responses API 使用的 Tool Schema。
4. 将函数、输入模型和 Schema 存入 `TOOL_REGISTRY`。

Agent 只调用 `get_tool_schemas()` 和 `execute_tool()`，不依赖具体工具。

## 项目结构

```text
src/myharness/
├── main.py              # 配置、客户端和命令行输入
├── agent.py             # Responses API 与 ReAct 循环
└── tools/
    ├── __init__.py      # 显式导入并注册工具
    ├── registry.py      # @tool、注册表和统一执行入口
    └── calculator.py    # 加、减、乘、除工具
```

## 运行

```bash
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

uv sync
uv run myharness
```

输入 `exit` 或 `quit` 退出。

## 新增工具

在 `tools/` 中编写带类型注解和 docstring 的函数：

```python
from .registry import tool


@tool
def power(a: float, b: float) -> float:
    """计算 a 的 b 次方。"""
    return a**b
```

然后在 `tools/__init__.py` 中显式导入该函数，使装饰器执行注册。无需修改 Agent Loop。
