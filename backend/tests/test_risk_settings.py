"""Tests for risk settings functionality."""

import numpy as np
import pandas as pd
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.validators import RiskSettings
from src.backtest.engine import BacktestEngine
from src.backtest.portfolio import Portfolio
from src.strategies.implementations import MovingAverageCrossover
from src.data.processor import FeatureEngineer
from pydantic import ValidationError


def _make_test_data(n=300):
    """Create synthetic price data for testing."""
    np.random.seed(42)
    dates = pd.bdate_range("2020-01-01", periods=n)

    # Trending price with volatility
    trend = np.linspace(100, 150, n)
    noise = np.random.normal(0, 3, n)
    close = trend + noise

    high = close + np.abs(np.random.normal(0, 1, n))
    low = close - np.abs(np.random.normal(0, 1, n))
    open_ = close + np.random.normal(0, 0.5, n)
    volume = np.random.randint(1_000_000, 5_000_000, n)

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=dates)

    processor = FeatureEngineer()
    return processor.process(df)


class TestRiskSettings:
    """Tests for risk management settings."""

    def test_default_risk_values_applied(self):
        """Test that default risk values are applied when none specified."""
        # Create RiskSettings with defaults
        risk = RiskSettings()

        assert risk.stop_loss_pct == 2.0
        assert risk.take_profit_pct == 5.0
        assert risk.max_position_size_pct == 10.0
        assert risk.max_daily_loss_pct == 3.0
        assert risk.max_open_positions == 5
        assert risk.trailing_stop_enabled is False
        assert risk.trailing_stop_pct == 3.0
        assert risk.commission_per_trade == 0.0

    def test_risk_settings_validation(self):
        """Test that risk settings validation works correctly."""
        # Valid settings
        risk = RiskSettings(
            stop_loss_pct=3.0,
            take_profit_pct=10.0,
            max_position_size_pct=20.0,
            max_daily_loss_pct=5.0,
            max_open_positions=10,
            trailing_stop_enabled=True,
            trailing_stop_pct=2.5,
            commission_per_trade=1.0,
        )

        assert risk.stop_loss_pct == 3.0
        assert risk.take_profit_pct == 10.0

        # Invalid stop loss (too high)
        with pytest.raises(ValidationError):
            RiskSettings(stop_loss_pct=60.0)

        # Invalid stop loss (too low)
        with pytest.raises(ValidationError):
            RiskSettings(stop_loss_pct=0.05)

        # Invalid max position size
        with pytest.raises(ValidationError):
            RiskSettings(max_position_size_pct=150.0)

        # Invalid max open positions
        with pytest.raises(ValidationError):
            RiskSettings(max_open_positions=100)

    def test_stop_loss_and_take_profit_ranges(self):
        """Test that stop loss and take profit have valid ranges."""
        # Valid stop loss
        risk = RiskSettings(stop_loss_pct=1.0)
        assert risk.stop_loss_pct == 1.0

        # Valid take profit
        risk = RiskSettings(take_profit_pct=15.0)
        assert risk.take_profit_pct == 15.0

        # Stop loss and take profit can have any relationship (some strategies use inverted)
        risk = RiskSettings(stop_loss_pct=10.0, take_profit_pct=5.0)
        assert risk.stop_loss_pct == 10.0

    def test_position_size_limits(self):
        """Test that position size limits are validated."""
        # Valid max position size
        risk = RiskSettings(max_position_size_pct=25.0)
        assert risk.max_position_size_pct == 25.0

        # Invalid - too high
        with pytest.raises(ValidationError):
            RiskSettings(max_position_size_pct=150.0)

        # Invalid - too low
        with pytest.raises(ValidationError):
            RiskSettings(max_position_size_pct=0.5)

    def test_daily_loss_limit_validation(self):
        """Test that daily loss limit is validated."""
        # Valid daily loss limit
        risk = RiskSettings(max_daily_loss_pct=2.0)
        assert risk.max_daily_loss_pct == 2.0

        # Invalid - too high
        with pytest.raises(ValidationError):
            RiskSettings(max_daily_loss_pct=25.0)

        # Invalid - too low
        with pytest.raises(ValidationError):
            RiskSettings(max_daily_loss_pct=0.1)

    def test_max_open_positions_validation(self):
        """Test that max open positions is validated."""
        # Valid max open positions
        risk = RiskSettings(max_open_positions=3)
        assert risk.max_open_positions == 3

        # Invalid - too many
        with pytest.raises(ValidationError):
            RiskSettings(max_open_positions=100)

        # Invalid - zero
        with pytest.raises(ValidationError):
            RiskSettings(max_open_positions=0)

    def test_commission_validation(self):
        """Test that commission is validated."""
        # Valid commission
        risk = RiskSettings(commission_per_trade=2.5)
        assert risk.commission_per_trade == 2.5

        # Invalid - negative
        with pytest.raises(ValidationError):
            RiskSettings(commission_per_trade=-1.0)

        # Invalid - too high
        with pytest.raises(ValidationError):
            RiskSettings(commission_per_trade=100.0)
