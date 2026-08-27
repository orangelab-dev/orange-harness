"""统一处理 Tool 的参数校验、审批和执行。"""

from collections.abc import Callable
from typing import Any, Literal

from .registry import ApprovalDecision, ApprovalRule, TOOL_REGISTRY


ApprovalMode = Literal["deny", "policy", "auto"]
ApprovalHandler = Callable[[str, dict[str, Any]], bool]
EventHandler = Callable[[dict], None]


def _resolve_approval(
    approval: ApprovalRule,
    arguments: dict[str, Any],
) -> ApprovalDecision:
    """把静态或动态审批规则统一转换成审批决定。"""

    decision = approval(arguments) if callable(approval) else approval
    if decision not in {"allow", "ask", "deny"}:
        raise ValueError(f"无效的审批决定：{decision}")
    return decision


def _emit_event(on_event: EventHandler | None, event: dict) -> None:
    """有 callback 时发送结构化审批事件。"""

    if on_event is not None:
        on_event(event)


def _denied_result(
    status: Literal["policy_denied", "user_denied"],
    message: str,
) -> dict:
    """返回没有执行 Tool 的结构化结果。"""

    return {"status": status, "message": message}


def execute_tool(
    name: str,
    arguments: str,
    request_approval: ApprovalHandler | None = None,
    on_event: EventHandler | None = None,
    approval_mode: ApprovalMode = "deny",
) -> Any:
    """根据模型返回的工具名和 JSON 参数，验证并执行对应函数。"""

    if approval_mode not in {"deny", "policy", "auto"}:
        raise ValueError(f"无效的审批模式：{approval_mode}")

    # 第一步：用 call.name 从注册表找到工具。
    registered_tool = TOOL_REGISTRY.get(name)
    if registered_tool is None:
        raise ValueError(f"未知工具：{name}")

    # 第二步：Pydantic 解析并验证 call.arguments。
    validated_input = registered_tool.input_model.model_validate_json(arguments)
    kwargs = validated_input.model_dump()

    # 审批规则只看到已经通过 Pydantic 校验的参数。
    decision = _resolve_approval(registered_tool.approval, kwargs)
    if decision == "deny":
        _emit_event(
            on_event,
            {
                "type": "approval_result",
                "data": {
                    "name": name,
                    "arguments": kwargs,
                    "status": "policy_denied",
                    "reason": "tool_policy_deny",
                },
            },
        )
        return _denied_result("policy_denied", "工具未执行：审批规则拒绝。")

    if decision == "ask":
        # deny 模式默认拒绝所有需要确认的调用；auto 不能越过明确 deny。
        if approval_mode == "deny":
            _emit_event(
                on_event,
                {
                    "type": "approval_result",
                    "data": {
                        "name": name,
                        "arguments": kwargs,
                        "status": "policy_denied",
                        "reason": "approval_mode_deny",
                    },
                },
            )
            return _denied_result("policy_denied", "工具未执行：当前审批模式默认拒绝。")

        if approval_mode == "auto":
            approval_source = "auto_mode"
        else:
            _emit_event(
                on_event,
                {
                    "type": "approval_request",
                    "data": {"name": name, "arguments": kwargs},
                },
            )

            if request_approval is None:
                _emit_event(
                    on_event,
                    {
                        "type": "approval_result",
                        "data": {
                            "name": name,
                            "arguments": kwargs,
                            "status": "policy_denied",
                            "reason": "missing_handler",
                        },
                    },
                )
                return _denied_result(
                    "policy_denied",
                    "工具未执行：缺少人工审批处理器。",
                )

            if not request_approval(name, kwargs):
                _emit_event(
                    on_event,
                    {
                        "type": "approval_result",
                        "data": {
                            "name": name,
                            "arguments": kwargs,
                            "status": "user_denied",
                            "reason": "user_rejected",
                        },
                    },
                )
                return _denied_result("user_denied", "工具未执行：用户拒绝。")

            approval_source = "user"
    else:
        approval_source = "policy"

    _emit_event(
        on_event,
        {
            "type": "approval_result",
            "data": {
                "name": name,
                "arguments": kwargs,
                "status": "allowed",
                "source": approval_source,
            },
        },
    )

    # func(**{"a": 2.0, "b": 3.0}) 等价于 func(a=2.0, b=3.0)。
    return registered_tool.func(**kwargs)
