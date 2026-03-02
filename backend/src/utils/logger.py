import logging
import os
from logging.handlers import RotatingFileHandler

import yaml


def setup_logger(name: str = "alphalab", config_path: str = None) -> logging.Logger:
    """Configure and return a logger instance with file and console handlers."""
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "config.yaml"
        )

    log_config = {
        "level": "INFO",
        "file": "logs/alphalab.log",
        "max_bytes": 10485760,
        "backup_count": 5,
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    }

    if os.path.exists(config_path):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
            log_config.update(cfg.get("logging", {}))

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_config["level"].upper(), logging.INFO))

    if logger.handlers:
        return logger

    formatter = logging.Formatter(log_config["format"])

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler
    log_dir = os.path.dirname(log_config["file"])
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_config["file"],
        maxBytes=log_config["max_bytes"],
        backupCount=log_config["backup_count"],
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
