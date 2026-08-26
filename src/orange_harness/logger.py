"""orange-harness 的标准日志配置。"""

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


logger = logging.getLogger("orange_harness.agent")


def configure_logger(log_file: str | Path = "logs/agent.log") -> logging.Logger:
    """配置保存原始事件的轮转文件日志。"""

    # 避免 main() 被重复调用时重复添加 Handler。
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 每条日志的 message 是完整 event JSON，前面保留时间和日志级别。
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 单文件最多 10 MB，最多保留 5 个历史备份。
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(file_formatter)

    logger.addHandler(file_handler)
    return logger


def log_raw_event(event: dict) -> None:
    """把完整 event 序列化后写入文件日志。"""

    logger.info(json.dumps(event, ensure_ascii=False, default=str))
