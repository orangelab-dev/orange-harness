import os

from dotenv import load_dotenv
from openai import OpenAI

from .agent import run_agent


def print_event(event):
    """把 Agent 的关键事件打印到控制台。"""

    if event["type"] == "tool_call":
        print(f"[tool_call] {event['name']} {event['arguments']}")
    elif event["type"] == "tool_result":
        print(f"[tool_result] {event['name']} -> {event['result']}")
    elif event["type"] == "final_answer":
        print(f"[final_answer] {event['answer']}")


def main():
    load_dotenv()

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
        run_agent(client, model, history, on_event=print_event)
        print()


if __name__ == "__main__":
    main()
