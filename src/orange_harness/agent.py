"""Agent Loop：在 DeepSeek 和本地 Python 工具之间传递调用与结果。"""

import json

from openai import OpenAI
from openai.types.shared_params import Reasoning

from .tools import execute_tool, get_tool_schemas


def run_agent(
    client: OpenAI,
    model: str,
    history: list,
    on_event=None,
    request_approval=None,
) -> str:
    """持续调用模型和工具，直到模型返回最终文字答案。"""

    # 一次用户提问可能需要调用多个工具，所以这里是循环而不是只请求一次。
    while True:
        try:
            response = client.responses.create(
                model=model,
                instructions="你是一个可爱的女仆，你的任务是辅助好用户完成任务，说话自然、亲切、可爱；需要时使用提供的工具完成任务～",
                input=history,

                # 这里只把工具“说明书”交给模型；模型不会直接执行 Python 函数。
                tools=get_tool_schemas(),
                reasoning=Reasoning(effort="low"),
            )
        except Exception as error:
            if on_event is not None:
                on_event(
                    {
                        "type": "error",
                        "data": {
                            "stage": "model_request",
                            "error_type": type(error).__name__,
                            "message": str(error),
                        },
                    }
                )
            raise

        # 原始响应完整交给观察层，由观察层决定如何记录和展示。
        if on_event is not None:
            on_event({"type": "model_response", "data": response.model_dump()})

        # DeepSeek API 是无状态的。把本次输出保存下来，下次请求时要完整传回。
        # response.output 可能同时包含 reasoning、function_call 或最终 message。
        history.extend(response.output)

        # 从本次输出中找出模型希望执行的所有工具调用。
        tool_calls = [item for item in response.output if item.type == "function_call"]

        # 没有 function_call，表示模型已经给出最终答案，Agent Loop 结束。
        if not tool_calls:
            return response.output_text

        for call in tool_calls:
            try:
                # Agent 不知道具体工具实现，只走统一执行入口。
                result = execute_tool(
                    call.name,
                    call.arguments,
                    request_approval=request_approval,
                    on_event=on_event,
                )
            except Exception as error:
                if on_event is not None:
                    on_event(
                        {
                            "type": "error",
                            "data": {
                                "stage": "tool_execution",
                                "call_id": call.call_id,
                                "name": call.name,
                                "arguments": call.arguments,
                                "error_type": type(error).__name__,
                                "message": str(error),
                            },
                        }
                    )

                # 工具失败也要作为观察结果交还模型，让它解释或尝试修正。
                result = f"工具执行失败：{error}"

            if on_event is not None:
                on_event(
                    {
                        "type": "tool_result",
                        "data": {
                            "call_id": call.call_id,
                            "name": call.name,
                            "arguments": call.arguments,
                            "result": result,
                        },
                    }
                )

            # call_id 像订单号，用来告诉模型这个结果属于哪次 function_call。
            history.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": (
                        json.dumps(result, ensure_ascii=False, default=str)
                        if isinstance(result, dict)
                        else str(result)
                    ),
                }
            )
