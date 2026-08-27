import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from .agent import run_agent
from .logger import configure_logger, log_raw_event


def confirm_tool(name: str, arguments: dict) -> bool:
    """在 CLI 中展示 Tool 调用信息并请求人工确认。"""

    print("\n[approval]")
    print(f"cwd: {Path.cwd().resolve()}")
    print(f"tool: {name}")
    print(f"arguments: {json.dumps(arguments, ensure_ascii=False, default=str)}")
    answer = input("是否执行？[y/N]: ")
    return answer.strip().lower() in {"y", "yes"}


def _read_text(parts: list[dict]) -> str:
    """从 Responses API 的内容数组中取出可展示文字。"""

    return "\n".join(str(part["text"]) for part in parts if part.get("text"))


def print_readable_event(event: dict) -> None:
    """从原始 event 中提取适合人阅读的关键信息。"""

    event_type = event.get("type", "unknown_event")
    data = event.get("data", {})

    if event_type == "model_response":
        # 文件保留完整 response；这里只遍历 output 展示关键内容。
        for item in data.get("output", []):
            item_type = item.get("type")

            if item_type == "reasoning":
                text = _read_text(item.get("content") or item.get("summary") or [])
                if text:
                    print(f"[reasoning] {text}")
            elif item_type == "function_call":
                print(f"[tool_call] {item.get('name')} {item.get('arguments')}")
            elif item_type == "message":
                text = _read_text(item.get("content") or [])
                if text:
                    print(f"[answer] {text}")

    elif event_type == "tool_result":
        print(f"[tool_result] {data.get('name')} -> {data.get('result')}")
    elif event_type == "approval_request":
        print(f"[approval_request] {data.get('name')} {data.get('arguments')}")
    elif event_type == "approval_result":
        print(f"[approval_result] {data.get('name')} -> {data.get('status')}")
    elif event_type == "error":
        print(f"[error] {data.get('stage')}: {data.get('message')}")
    else:
        print(f"[{event_type}] {data}")


def handle_event(event: dict) -> None:
    """同一个 callback：完整写入文件，同时精简展示到终端。"""

    log_raw_event(event)
    print_readable_event(event)


def main():
    load_dotenv()
    configure_logger()

    client = OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    history = []

    while True:
        question = input("你：").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue

        history.append({"role": "user", "content": question})
        run_agent(
            client,
            model,
            history,
            on_event=handle_event,
            request_approval=confirm_tool,
        )
        print()


if __name__ == "__main__":
    main()
