import os
from pathlib import Path

import yaml


_config = None


def load_config(config_path: str = None) -> dict:
    """Load and return the YAML configuration, cached after first load."""
    global _config
    if _config is not None and config_path is None:
        return _config

    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "config.yaml"
        )

    config_path = Path(config_path).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        _config = yaml.safe_load(f)

    return _config
