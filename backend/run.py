#!/usr/bin/env python3
"""AlphaLab application entry point."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.utils.logger import setup_logger
from src.utils.config import load_config


def main():
    config = load_config()
    logger = setup_logger()

    logger.info("AlphaLab v%s starting", config["app"]["version"])

    from src.api.routes import create_app

    app = create_app()
    api_config = config.get("api", {})
    app.run(
        host=api_config.get("host", "0.0.0.0"),
        port=api_config.get("port", 5000),
        debug=config["app"].get("debug", False),
    )


if __name__ == "__main__":
    main()
