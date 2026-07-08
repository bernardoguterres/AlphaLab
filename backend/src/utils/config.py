import os
from dataclasses import dataclass, field
from pathlib import Path
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
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:8080"])


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


def _apply_env_overrides(config: AppConfig) -> AppConfig:
    """Override file-based config with env vars, for Railway/production deploys.

    PORT, HOST, and DEBUG are the settings that must differ between local dev
    and a hosted deploy; ALLOWED_ORIGINS lets the production frontend URL be
    added without a code change once it's known.
    """
    if "PORT" in os.environ:
        config.api.port = int(os.environ["PORT"])
    if "HOST" in os.environ:
        config.api.host = os.environ["HOST"]
    if "DEBUG" in os.environ:
        config.app.debug = os.environ["DEBUG"].lower() == "true"
    extra_origins = os.environ.get("ALLOWED_ORIGINS", "")
    if extra_origins:
        config.api.cors_origins = config.api.cors_origins + [
            o.strip() for o in extra_origins.split(",") if o.strip()
        ]
    return config


def _build_config(raw: dict) -> AppConfig:
    def _get(d: dict, key: str, default) -> dict:
        return d.get(key) or default

    config = AppConfig(
        app=AppSection(**_get(raw, "app", {})),
        data=DataConfig(**_get(raw, "data", {})),
        backtest=BacktestConfig(**_get(raw, "backtest", {})),
        api=ApiConfig(**_get(raw, "api", {})),
        logging=LoggingConfig(**_get(raw, "logging", {})),
        strategies=raw.get("strategies", {}),
    )
    return _apply_env_overrides(config)


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
