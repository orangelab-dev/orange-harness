import os

from dotenv import load_dotenv
from openai import OpenAI

from .agent import run_agent
from .logger import configure_logger, logger


def log_event(event: dict):
    """把 Agent event 转换为简洁日志。"""

    event_type = event.get("type", "unknown_event")

    if event_type == "tool_call":
        message = f"{event.get('name')} {event.get('arguments')}"
    elif event_type == "tool_result":
        message = f"{event.get('name')} -> {event.get('result')}"
    elif event_type == "reasoning":
        message = str(event.get("content"))
    elif event_type == "final_answer":
        message = str(event.get("answer"))
    else:
        # 未知事件保留完整内容，便于以后扩展事件类型。
        message = str(event)

    logger.info(
        "%s",
        message,
        extra={"event_type": event_type},
    )


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
        run_agent(client, model, history, on_event=log_event)
        print()


if __name__ == "__main__":
    main()
