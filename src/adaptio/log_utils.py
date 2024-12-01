import logging

import colorlog


def setup_colored_logger(
    logger_name: str,
    log_level: str = "INFO",
    log_prefix: str = "",
    propagate: bool = False,
) -> logging.Logger:
    """配置一个带有彩色输出的日志记录器

    Args:
        logger_name: 日志记录器名称
        log_level: 日志级别，默认为 "INFO"
        log_prefix: 日志前缀，默认为空字符串
        propagate: 是否传播日志到父级logger，默认为False

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(logger_name)
    # 清除已存在的处理器
    logger.handlers.clear()
    # 设置日志传播
    logger.propagate = propagate

    handler = colorlog.StreamHandler()
    formatter = colorlog.ColoredFormatter(
        f"%(log_color)s%(asctime)s - %(name)s:%(filename)s:%(lineno)d:%(funcName)s - %(levelname)s - {log_prefix} %(message)s",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, log_level.upper()))

    return logger
