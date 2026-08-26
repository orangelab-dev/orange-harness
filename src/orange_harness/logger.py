"""orange-harness 的标准日志配置。"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


logger = logging.getLogger("orange_harness.agent")


def configure_logger(log_file: str | Path = "logs/agent.log") -> logging.Logger:
    """配置控制台和轮转文件日志。"""

    # 避免 main() 被重复调用时重复添加 Handler。
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 控制台面向实时阅读，只显示事件类型和内容。
    console_formatter = logging.Formatter("[%(event_type)s] %(message)s")

    # 文件保留时间和日志级别，方便之后排查问题。
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(event_type)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)

    # 单文件最多 10 MB，最多保留 5 个历史备份。
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(file_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger
