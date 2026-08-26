import os

from dotenv import load_dotenv
from openai import OpenAI

from agent import run_agent


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
        answer = run_agent(client, model, history)
        print(f"Agent：{answer}\n")


if __name__ == "__main__":
    main()
