from openai import OpenAI
from openai.types.shared_params import Reasoning
from pydantic import ValidationError

from tools import TOOL_HANDLERS, TOOLS


def run_agent(client: OpenAI, model: str, history: list) -> str:
    while True:
        response = client.responses.create(
            model=model,
            instructions="你是一个简洁、可靠的助手。遇到计算问题时使用 calculate 工具。",
            input=history,
            tools=TOOLS,
            reasoning=Reasoning(effort="low"),
        )
        history.extend(response.output)

        tool_calls = [item for item in response.output if item.type == "function_call"]
        if not tool_calls:
            return response.output_text

        for call in tool_calls:
            handler = TOOL_HANDLERS.get(call.name)
            if handler is None:
                result = f"未知工具：{call.name}"
            else:
                try:
                    result = handler(call.arguments)
                except (ValidationError, ValueError) as error:
                    result = f"工具执行失败：{error}"

            history.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": result,
                }
            )
