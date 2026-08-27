# orange-harness

一个最小的 Python Agent：使用 DeepSeek Responses API，通过 ReAct 循环调用本地工具。

第一次使用请阅读：[使用教程](使用教程.md)

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
根据 Tool 的 approval 规则放行、询问或拒绝
  ↓
执行普通 Python 函数
  ↓
function_call_output 写回对话历史，继续调用 DeepSeek
```

DeepSeek API 不保存会话，因此 `agent.py` 会在本地维护完整的 `history`。

## 工具注册

工具只是加了 `@tool` 的普通函数：

```python
from typing import Literal


@tool(approval="allow")
def calculate(a: float, operator: Literal["+", "-", "*", "/"], b: float) -> float:
    """计算两个数字的加、减、乘、除。"""
    ...
```

`@tool` 自动完成：

1. 用 `inspect.signature()` 读取参数。
2. 用 Pydantic 动态创建输入模型。
3. 生成 Responses API 使用的 Tool Schema。
4. 将函数、输入模型、Schema 和审批规则存入 `TOOL_REGISTRY`。

Agent 只调用 `get_tool_schemas()` 和 `execute_tool()`，不依赖具体工具。
`tools/__init__.py` 会递归导入工具目录中的模块，因此新增工具后不需要维护导入清单。

## 项目结构

```text
src/orange_harness/
├── main.py              # 配置、客户端和命令行输入
├── agent.py             # Responses API 与 ReAct 循环
├── logger.py            # 原始事件文件日志
├── sandbox.py           # MacOSSandbox 和 NoSandbox
└── tools/
    ├── __init__.py      # 递归导入工具模块，触发注册
    ├── registry.py      # @tool、注册表和统一执行入口
    ├── calculator.py    # 加、减、乘、除工具
    └── shell.py         # Shell 能力和动态审批规则
```

## 安装和运行

把 API 配置放到用户目录（只需配置一次）：

```bash
mkdir -p ~/.config/orange-harness
cp .env.example ~/.config/orange-harness/.env
# 编辑 ~/.config/orange-harness/.env，填入 DEEPSEEK_API_KEY
```

系统环境变量的优先级更高。用户配置不存在或无法读取时，程序会回退读取启动目录下的 `.env`。

开发阶段推荐以 editable 模式安装一次：

```bash
uv tool install --editable .
```

`--editable` 表示 CLI 仍然使用当前项目源码，修改代码后不需要重复安装。

安装完成后，可以在任意目录直接启动：

```bash
cd /path/to/your/workspace
orange-harness --approval policy
```

启动命令所在的目录就是 Agent workspace，Shell Tool 会固定在这里执行，运行日志也会写入这里的 `logs/` 目录。

如果只想在仓库内临时运行，不安装 CLI，也可以使用：

```bash
uv sync
uv run orange-harness
```

输入 `exit` 或 `quit` 退出。

## Shell 安全边界

macOS 默认使用系统的 `sandbox-exec`：

- workspace 外禁止写入。
- workspace 外仍然允许读取。
- 网络默认不允许。
- 沙箱不可用或启动失败时，不会自动降级成裸执行。

当前没有实现敏感目录读取限制，也不能阻止命令删除 workspace 内的文件。沙箱限制和人工审批是两个独立机制：明确安全且只操作 workspace 的命令可以自动执行，无法确定的命令需要确认，明确危险的命令直接拒绝。

危险命令判断只覆盖少量明显变体，不是完整的 Shell Parser，也不把命令黑名单当作安全边界。判断不确定时会回到人工确认。

Linux、Windows 和没有可用 macOS Sandbox 的环境默认拒绝 Shell 执行。只有明确接受宿主机直接执行命令的风险时，才使用：

```bash
orange-harness --unsafe --approval policy
```

`unsafe` 使用 `NoSandbox`，它只表示“没有系统级隔离”，不会伪装成沙箱。即使开启 `unsafe`，Tool 的审批规则仍然生效。

审批有三种全局模式：

- `deny`（默认）：Tool 返回 `ask` 时直接拒绝。
- `policy`：Tool 返回 `ask` 时询问用户。
- `auto`：Tool 返回 `ask` 时自动执行。

Tool 明确返回 `deny` 时，三种模式都会拒绝；`auto` 也不能绕过。沙箱和审批可自由组合，完整命令见[使用教程](使用教程.md#5-选择运行模式)。

## 新增工具

在 `tools/` 中编写带类型注解和 docstring 的函数：

```python
from .registry import tool


@tool(approval="allow")
def power(a: float, b: float) -> float:
    """计算 a 的 b 次方。"""
    return a**b
```

保存文件即可。程序启动时会递归导入该模块并执行装饰器，无需修改 `tools/__init__.py` 或 Agent Loop。
