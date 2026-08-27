"""命令行参数与环境配置。"""

import argparse
from pathlib import Path

from dotenv import load_dotenv


CONFIG_FILE = Path.home() / ".config" / "orange-harness" / ".env"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """读取运行模式；安全相关选项只允许从 CLI 明确传入。"""

    parser = argparse.ArgumentParser(prog="orange-harness")
    parser.add_argument(
        "--approval",
        choices=("deny", "policy", "auto"),
        default="deny",
        help="审批模式（默认：deny）",
    )
    parser.add_argument(
        "--unsafe",
        action="store_true",
        help="不使用系统级沙箱，直接在宿主机执行 Shell",
    )
    return parser.parse_args(argv)


def load_config(config_file: Path = CONFIG_FILE) -> None:
    """优先读取用户配置；找不到时回退到当前 workspace 的 .env。"""

    try:
        if config_file.is_file():
            load_dotenv(config_file, override=False)
            return
    except OSError:
        # 用户配置无法访问时，也允许当前 workspace 提供配置。
        pass

    load_dotenv(Path.cwd() / ".env", override=False)
