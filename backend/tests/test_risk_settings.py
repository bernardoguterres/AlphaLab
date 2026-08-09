"""Tests for risk settings functionality."""

import numpy as np
import pandas as pd
import pytest

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alphalab.api.validators import RiskSettings
from alphalab.backtest.engine import BacktestEngine
from alphalab.backtest.portfolio import Portfolio
from alphalab.backtest.order import Order, OrderSide
from alphalab.strategies.implementations import MovingAverageCrossover
from alphalab.data.processor import FeatureEngineer
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

    df = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        },
        index=dates,
    )

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

        # Invalid max_position_size_pct and max_open_positions bounds are
        # covered in detail by test_position_size_limits and
        # test_max_open_positions_validation below.

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


def _make_rise_then_crash_data(n=300, flat_bars=60, rise_bars=15, crash_bars=15):
    """Deterministic (no noise) price series: a flat warmup segment (so
    SMA5/SMA50 stabilize with fast < slow before any crossover is
    observed), a short rise that fires a golden-cross BUY close to the
    peak, then a SHARP crash immediately after the peak, then a flat tail.

    The crash must be sharp (large %/bar), not a slow grind: the
    portfolio-level stop-loss overlay checks the raw close price directly
    and reacts within one bar, but the strategy's OWN death-cross exit
    needs several bars for SMA5 to react - a slow decline lets the
    strategy's own exit fire first every time regardless of stop_loss_pct,
    which would make this fixture useless for proving the stop-loss
    overlay changes exit timing at all.
    """
    dates = pd.bdate_range("2020-01-01", periods=n)
    flat = np.full(flat_bars, 100.0)
    rise = np.linspace(100, 150, rise_bars)
    crash = np.linspace(150, 30, crash_bars)
    tail = np.full(n - flat_bars - rise_bars - crash_bars, 30.0)
    close = np.concatenate([flat, rise, crash, tail])

    df = pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.001,
            "Low": close * 0.999,
            "Close": close,
            "Volume": np.full(n, 2_000_000),
        },
        index=dates,
    )
    processor = FeatureEngineer()
    return processor.process(df)


class TestRiskSettingsWiredIntoEngine:
    """Regression tests for audit bug 3.1: risk_settings was validated at
    the API layer and forwarded to the AlphaLive export, but never actually
    reached the simulation - Portfolio had no concept of stop_loss_pct/
    take_profit_pct at all, and take-profit didn't exist anywhere in the
    engine. engine.run_backtest(risk_settings=...) now wires these into a
    portfolio-level risk overlay independent of each strategy's own
    internal exit logic.
    """

    def test_tight_stop_loss_exits_before_loose_stop_loss(self):
        """The core requested test: identical data and strategy, only
        stop_loss_pct differs - the tight stop must produce an earlier exit
        than the loose one. The tight (2%) stop fires on the sharp
        post-peak crash itself; the loose (20%) stop doesn't get triggered
        before the strategy's own death-cross exit fires a few bars later -
        which is itself proof the setting changed behavior (with no
        portfolio-level stop-loss at all, both runs would exit on the
        exact same bar via the strategy's own signal, since a plain
        MovingAverageCrossover has no other exit mechanism)."""
        data = _make_rise_then_crash_data()
        engine = BacktestEngine()

        def exit_info(stop_loss_pct):
            strategy = MovingAverageCrossover(
                {"short_window": 5, "long_window": 50, "volume_confirmation": False}
            )
            results = engine.run_backtest(
                strategy=strategy,
                data=data,
                initial_capital=100_000,
                position_sizing="equal_weight",
                risk_settings={"stop_loss_pct": stop_loss_pct},
            )
            for t in results.trades:
                if t["side"] == "sell":
                    return t["timestamp"], t["reason"]
            return None, None

        tight_exit_ts, tight_reason = exit_info(2.0)
        loose_exit_ts, loose_reason = exit_info(20.0)

        assert tight_exit_ts is not None
        assert loose_exit_ts is not None
        assert "Stop-loss triggered" in tight_reason
        assert tight_exit_ts < loose_exit_ts

    def test_take_profit_triggers_exit_on_sufficient_rise(self):
        """take_profit_pct didn't exist anywhere in the engine before this
        fix - confirm it now actually closes a position once the gain
        target is hit."""
        # Flat warmup (so SMA5/SMA50 stabilize with fast < slow before any
        # crossover is observed - needs at least 50 bars for SMA50 to be
        # valid), then a clean, sustained rise with no decline - only
        # take-profit (not stop-loss) can be responsible for any SELL here.
        n = 150
        dates = pd.bdate_range("2020-01-01", periods=n)
        flat = np.full(60, 100.0)
        rise = np.linspace(100, 200, n - 60)  # steady rise after warmup
        close = np.concatenate([flat, rise])
        df = pd.DataFrame(
            {
                "Open": close,
                "High": close * 1.001,
                "Low": close * 0.999,
                "Close": close,
                "Volume": np.full(n, 2_000_000),
            },
            index=dates,
        )
        data = FeatureEngineer().process(df)

        strategy = MovingAverageCrossover(
            {"short_window": 5, "long_window": 50, "volume_confirmation": False}
        )
        engine = BacktestEngine()
        results = engine.run_backtest(
            strategy=strategy,
            data=data,
            initial_capital=100_000,
            position_sizing="equal_weight",
            risk_settings={"take_profit_pct": 10.0},
        )

        sell_reasons = [t["reason"] for t in results.trades if t["side"] == "sell"]
        assert any("Take-profit triggered" in r for r in sell_reasons)

    def test_no_risk_settings_preserves_default_behavior(self):
        """risk_settings=None (or omitted) must behave exactly as before
        this fix - no stop-loss/take-profit overlay, Portfolio's own
        built-in defaults for position sizing."""
        data = _make_rise_then_crash_data()
        strategy = MovingAverageCrossover(
            {"short_window": 5, "long_window": 50, "volume_confirmation": False}
        )
        engine = BacktestEngine()

        with_none = engine.run_backtest(
            strategy=strategy,
            data=data,
            initial_capital=100_000,
            position_sizing="equal_weight",
            risk_settings=None,
        )
        without_arg = engine.run_backtest(
            strategy=strategy,
            data=data,
            initial_capital=100_000,
            position_sizing="equal_weight",
        )

        assert with_none.final_value == without_arg.final_value
        assert len(with_none.trades) == len(without_arg.trades)

    def test_max_position_size_pct_reduces_position_size(self):
        data = _make_rise_then_crash_data()
        engine = BacktestEngine()

        def first_buy_shares(max_position_size_pct):
            strategy = MovingAverageCrossover(
                {"short_window": 5, "long_window": 50, "volume_confirmation": False}
            )
            results = engine.run_backtest(
                strategy=strategy,
                data=data,
                initial_capital=100_000,
                position_sizing="equal_weight",
                risk_settings={"max_position_size_pct": max_position_size_pct},
            )
            for t in results.trades:
                if t["side"] == "buy":
                    return t["shares"]
            return None

        small_position_shares = first_buy_shares(5.0)
        large_position_shares = first_buy_shares(50.0)

        assert small_position_shares is not None
        assert large_position_shares is not None
        assert small_position_shares < large_position_shares

    def test_tight_trailing_stop_exits_before_loose_trailing_stop(self):
        """trailing_stop_enabled/trailing_stop_pct were fully wired in the
        UI and RiskSettings but never reached the simulation: engine.py
        never read them, Portfolio had no trailing_stop_pct parameter, and
        the trailing_stops dict Portfolio DID maintain (ratcheted toward a
        hardcoded 5%, not any configured percentage) was never checked
        against price anywhere - the whole feature was silently inert. This
        mirrors test_tight_stop_loss_exits_before_loose_stop_loss: identical
        data and strategy, only trailing_stop_pct differs, and the tight
        stop must exit earlier than the loose one during the post-peak
        crash."""
        data = _make_rise_then_crash_data()
        engine = BacktestEngine()

        def exit_info(trailing_stop_pct):
            strategy = MovingAverageCrossover(
                {"short_window": 5, "long_window": 50, "volume_confirmation": False}
            )
            results = engine.run_backtest(
                strategy=strategy,
                data=data,
                initial_capital=100_000,
                position_sizing="equal_weight",
                risk_settings={
                    "trailing_stop_enabled": True,
                    "trailing_stop_pct": trailing_stop_pct,
                },
            )
            for t in results.trades:
                if t["side"] == "sell":
                    return t["timestamp"], t["reason"]
            return None, None

        tight_exit_ts, tight_reason = exit_info(2.0)
        loose_exit_ts, loose_reason = exit_info(20.0)

        assert tight_exit_ts is not None
        assert loose_exit_ts is not None
        assert "Trailing stop triggered" in tight_reason
        assert tight_exit_ts < loose_exit_ts

    def test_trailing_stop_disabled_by_default_preserves_behavior(self):
        """trailing_stop_enabled defaults to False - omitting it (or setting
        it False) must not change exit behavior at all, even if
        trailing_stop_pct is present in the dict (matches the frontend,
        which always sends both fields but only trailing_stop_enabled
        gates whether the percentage applies)."""
        data = _make_rise_then_crash_data()
        strategy = MovingAverageCrossover(
            {"short_window": 5, "long_window": 50, "volume_confirmation": False}
        )
        engine = BacktestEngine()

        without_trailing = engine.run_backtest(
            strategy=strategy,
            data=data,
            initial_capital=100_000,
            position_sizing="equal_weight",
            risk_settings=None,
        )
        disabled_trailing = engine.run_backtest(
            strategy=strategy,
            data=data,
            initial_capital=100_000,
            position_sizing="equal_weight",
            risk_settings={"trailing_stop_enabled": False, "trailing_stop_pct": 2.0},
        )

        assert without_trailing.final_value == disabled_trailing.final_value
        assert len(without_trailing.trades) == len(disabled_trailing.trades)

    def test_monte_carlo_runs_honor_risk_settings(self):
        """engine._monte_carlo() previously called self._simulate(...)
        without forwarding max_drawdown_pct/risk_settings at all, so a
        Monte Carlo run silently ignored the same stop-loss the primary
        backtest applied - the MC distribution didn't represent the
        strategy+risk-settings combination it claimed to stress-test. A
        tight stop-loss during the sharp crash in _make_rise_then_crash_data
        must bound every MC run's downside; without it, the crash alone
        (before the strategy's own slower death-cross exit reacts) drives
        every run's final value meaningfully lower."""
        data = _make_rise_then_crash_data()
        strategy = MovingAverageCrossover(
            {"short_window": 5, "long_window": 50, "volume_confirmation": False}
        )
        engine = BacktestEngine()

        np.random.seed(7)
        with_stop = engine.run_backtest(
            strategy=strategy,
            data=data,
            initial_capital=100_000,
            position_sizing="equal_weight",
            monte_carlo_runs=5,
            risk_settings={"stop_loss_pct": 2.0},
        )

        np.random.seed(7)
        without_stop = engine.run_backtest(
            strategy=strategy,
            data=data,
            initial_capital=100_000,
            position_sizing="equal_weight",
            monte_carlo_runs=5,
        )

        assert with_stop.monte_carlo is not None
        assert without_stop.monte_carlo is not None
        assert (
            with_stop.monte_carlo["mean_final_value"]
            > without_stop.monte_carlo["mean_final_value"]
        )


class TestPortfolioRiskOverlay:
    """Unit tests for Portfolio.check_risk_overlay_exit directly (bug 3.1)."""

    def test_disabled_by_default(self):
        portfolio = Portfolio(initial_capital=100_000)
        portfolio.positions["AAPL"] = 10
        portfolio.avg_cost["AAPL"] = 100.0

        assert portfolio.check_risk_overlay_exit("AAPL", 1.0) is None

    def test_stop_loss_triggers_below_threshold(self):
        portfolio = Portfolio(initial_capital=100_000, stop_loss_pct=5.0)
        portfolio.positions["AAPL"] = 10
        portfolio.avg_cost["AAPL"] = 100.0

        assert portfolio.check_risk_overlay_exit("AAPL", 96.0) is None
        reason = portfolio.check_risk_overlay_exit("AAPL", 94.0)
        assert reason is not None
        assert "Stop-loss" in reason

    def test_take_profit_triggers_above_threshold(self):
        portfolio = Portfolio(initial_capital=100_000, take_profit_pct=10.0)
        portfolio.positions["AAPL"] = 10
        portfolio.avg_cost["AAPL"] = 100.0

        assert portfolio.check_risk_overlay_exit("AAPL", 109.0) is None
        reason = portfolio.check_risk_overlay_exit("AAPL", 111.0)
        assert reason is not None
        assert "Take-profit" in reason

    def test_no_position_returns_none(self):
        portfolio = Portfolio(initial_capital=100_000, stop_loss_pct=5.0)
        assert portfolio.check_risk_overlay_exit("AAPL", 50.0) is None


class TestPortfolioTrailingStop:
    """Unit tests for Portfolio.update_trailing_stops/check_trailing_stop_exit -
    the trailing-stop feature was fully wired in the UI/RiskSettings but had
    no effect on any backtest before this fix (see
    TestRiskSettingsWiredIntoEngine.test_tight_trailing_stop_exits_before_loose_trailing_stop).
    """

    def test_disabled_by_default(self):
        portfolio = Portfolio(initial_capital=100_000)
        portfolio.positions["AAPL"] = 10
        portfolio.avg_cost["AAPL"] = 100.0
        portfolio.trailing_stops["AAPL"] = 95.0  # even if somehow set

        portfolio.update_trailing_stops({"AAPL": 120.0})
        assert portfolio.check_trailing_stop_exit("AAPL", 1.0) is None

    def test_no_position_returns_none(self):
        portfolio = Portfolio(initial_capital=100_000, trailing_stop_pct=5.0)
        assert portfolio.check_trailing_stop_exit("AAPL", 50.0) is None

    def test_ratchets_up_with_price_and_never_down(self):
        portfolio = Portfolio(initial_capital=100_000, trailing_stop_pct=5.0)
        order = Order(ticker="AAPL", side=OrderSide.BUY, shares=10)
        portfolio.execute_order(order, {"AAPL": 100.0})
        assert portfolio.trailing_stops["AAPL"] == pytest.approx(95.0, rel=1e-3)

        portfolio.update_trailing_stops({"AAPL": 120.0})
        assert portfolio.trailing_stops["AAPL"] == pytest.approx(114.0, rel=1e-3)

        # A pullback must not lower the stop - it only ratchets up.
        portfolio.update_trailing_stops({"AAPL": 110.0})
        assert portfolio.trailing_stops["AAPL"] == pytest.approx(114.0, rel=1e-3)

    def test_triggers_when_price_falls_through_stop(self):
        portfolio = Portfolio(initial_capital=100_000, trailing_stop_pct=5.0)
        order = Order(ticker="AAPL", side=OrderSide.BUY, shares=10)
        portfolio.execute_order(order, {"AAPL": 100.0})
        portfolio.update_trailing_stops({"AAPL": 120.0})  # stop ratchets to 114.0

        assert portfolio.check_trailing_stop_exit("AAPL", 115.0) is None
        reason = portfolio.check_trailing_stop_exit("AAPL", 113.0)
        assert reason is not None
        assert "Trailing stop" in reason

    def test_uses_configured_percentage_not_hardcoded_five_percent(self):
        """Regression: update_trailing_stops previously hardcoded price *
        0.95 (5%) regardless of the configured trailing_stop_pct."""
        portfolio = Portfolio(initial_capital=100_000, trailing_stop_pct=20.0)
        order = Order(ticker="AAPL", side=OrderSide.BUY, shares=10)
        portfolio.execute_order(order, {"AAPL": 100.0})
        portfolio.update_trailing_stops({"AAPL": 120.0})

        # 20% below peak of 120 = 96.0, not the old hardcoded 5% (114.0).
        assert portfolio.trailing_stops["AAPL"] == pytest.approx(96.0, rel=1e-3)
