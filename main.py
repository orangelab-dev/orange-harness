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
    messages = [{"role": "system", "content": "你是一个简洁、可靠的助手。"}]

    while True:
        question = input("你：").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue

        messages.append({"role": "user", "content": question})
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            reasoning_effort="low",
            extra_body={"thinking": {"type": "enabled"}},
        )
        answer = response.choices[0].message
        messages.append(answer)
        print(f"Agent：{answer.content}\n")


if __name__ == "__main__":
    main()
