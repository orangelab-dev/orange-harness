import os

from openai import OpenAI

from .agent import run_agent
from .config import load_config, parse_args
from .logger import configure_logger
from .observer import confirm_tool, handle_event
from .tools.shell import configure_shell


def main(argv: list[str] | None = None):
    args = parse_args(argv)
    load_config()
    configure_logger()
    configure_shell(unsafe=args.unsafe)

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
            approval_mode=args.approval,
        )
        print()


if __name__ == "__main__":
    main()
