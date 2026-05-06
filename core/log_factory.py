import sys
from pathlib import Path
from loguru import logger
from core.config_reader import config


def setup_logger():
    log_dir = Path(config.get("log.dir", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()

    # 控制台：INFO 及以上
    logger.add(
        sys.stdout,
        level=config.get("log.level", "INFO"),
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level:<8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # 文件：DEBUG 及以上，按天切割
    logger.add(
        str(log_dir / "test_{time:YYYY-MM-DD}.log"),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{line} | {message}",
        rotation=config.get("log.rotation", "00:00"),
        retention=config.get("log.retention", "7 days"),
        encoding="utf-8",
        enqueue=True,  # 线程安全
    )

    # 单独记录错误日志
    logger.add(
        str(log_dir / "error_{time:YYYY-MM-DD}.log"),
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{line} | {message}\n{exception}",
        rotation="00:00",
        retention="30 days",
        encoding="utf-8",
        enqueue=True,
    )

    return logger


log = setup_logger()