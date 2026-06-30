import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml


@dataclass
class AppSection:
    name: str = "AlphaLab"
    version: str = "0.1.0"
    debug: bool = False


@dataclass
class DataConfig:
    cache_dir: str = "data/cache"
    max_retries: int = 3
    cache_expiry_hours: int = 24


@dataclass
class BacktestConfig:
    initial_capital: float = 100_000.0
    commission: float = 0.0
    slippage: float = 0.05
    risk_free_rate: float = 0.04


@dataclass
class ApiConfig:
    host: str = "127.0.0.1"
    port: int = 5000
    cors_origins: List[str] = field(default_factory=lambda: ["http://localhost:8080"])


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "logs/alphalab.log"
    max_bytes: int = 10_485_760
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class AppConfig:
    app: AppSection = field(default_factory=AppSection)
    data: DataConfig = field(default_factory=DataConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    strategies: dict = field(default_factory=dict)


def _build_config(raw: dict) -> AppConfig:
    def _get(d: dict, key: str, default) -> dict:
        return d.get(key) or default

    return AppConfig(
        app=AppSection(**_get(raw, "app", {})),
        data=DataConfig(**_get(raw, "data", {})),
        backtest=BacktestConfig(**_get(raw, "backtest", {})),
        api=ApiConfig(**_get(raw, "api", {})),
        logging=LoggingConfig(**_get(raw, "logging", {})),
        strategies=raw.get("strategies", {}),
    )


_config: AppConfig | None = None


def load_config(config_path: str = None) -> AppConfig:
    """Load and return the typed application config, cached after first load."""
    global _config
    if _config is not None and config_path is None:
        return _config

    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")

    config_path = Path(config_path).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    _config = _build_config(raw)
    return _config
