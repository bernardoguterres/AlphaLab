import logging
from logging.handlers import RotatingFileHandler

from .config import load_config


def setup_logger(name: str = "alphalab", config_path: str = None) -> logging.Logger:
    """Configure and return a logger instance with file and console handlers."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    try:
        cfg = load_config(config_path)
        lc = cfg.logging
        level = lc.level
        log_file = lc.file
        max_bytes = lc.max_bytes
        backup_count = lc.backup_count
        fmt = lc.format
    except Exception:
        level = "INFO"
        log_file = "logs/alphalab.log"
        max_bytes = 10_485_760
        backup_count = 5
        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    formatter = logging.Formatter(fmt)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)

    import os

    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
