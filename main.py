import os

from dotenv import load_dotenv
from openai import OpenAI


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
        response = client.responses.create(
            model=model,
            instructions="你是一个简洁、可靠的助手。",
            input=history,
            reasoning={"effort": "low"},
        )
        history.extend(response.output)
        print(f"Agent：{response.output_text}\n")


if __name__ == "__main__":
    main()
