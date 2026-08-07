"""Feature engineering for market data using technical analysis indicators."""

import numpy as np
import pandas as pd

from ..utils.logger import setup_logger

logger = setup_logger("alphalab.processor")


class FeatureEngineer:
    """Compute technical indicators used by the strategy implementations.

    Only computes indicators actually consumed by at least one strategy's
    `required_columns()`/`generate_signals()`: SMA_10/20/50/100/200 (the last
    three exist to support GreenblattWeekly's configurable fast_sma/slow_sma,
    not just its 10/50 defaults - do not remove), RSI, ADX (+ DI lines),
    Bollinger Bands, and ATR.
    """

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all features to the OHLCV DataFrame.

        Args:
            df: DataFrame with columns Open, High, Low, Close, Volume indexed by Date.

        Returns:
            DataFrame with original OHLCV + all computed features.
        """
        df = df.copy()
        required = {"Open", "High", "Low", "Close", "Volume"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        if len(df) < 30:
            logger.warning("Only %d rows - some indicators will be NaN", len(df))

        df = self._add_trend_indicators(df)
        df = self._add_momentum_indicators(df)
        df = self._add_volatility_indicators(df)

        logger.info(
            "Feature engineering complete: %d features, %d rows",
            len(df.columns),
            len(df),
        )
        return df

    # ------------------------------------------------------------------
    # Trend
    # ------------------------------------------------------------------

    @staticmethod
    def _add_trend_indicators(df: pd.DataFrame) -> pd.DataFrame:
        close = df["Close"]

        # SMA
        for w in (10, 20, 50, 100, 200):
            df[f"SMA_{w}"] = close.rolling(window=w, min_periods=w).mean()

        # ADX (14-day)
        df = FeatureEngineer._compute_adx(df, period=14)

        return df

    @staticmethod
    def _compute_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        high, low, close = df["High"], df["Low"], df["Close"]
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        tr = pd.concat(
            [
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)

        atr = tr.ewm(alpha=1 / period, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)

        dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
        df["ADX"] = dx.ewm(alpha=1 / period, adjust=False).mean()
        df["Plus_DI"] = plus_di
        df["Minus_DI"] = minus_di
        return df

    # ------------------------------------------------------------------
    # Momentum
    # ------------------------------------------------------------------

    @staticmethod
    def _add_momentum_indicators(df: pd.DataFrame) -> pd.DataFrame:
        close = df["Close"]

        # RSI (14)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["RSI"] = 100 - (100 / (1 + rs))
        df["RSI"] = df["RSI"].clip(0, 100)

        return df

    # ------------------------------------------------------------------
    # Volatility
    # ------------------------------------------------------------------

    @staticmethod
    def _add_volatility_indicators(df: pd.DataFrame) -> pd.DataFrame:
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # Bollinger Bands (20, 2)
        sma20 = close.rolling(20, min_periods=20).mean()
        std20 = close.rolling(20, min_periods=20).std()
        df["BB_Upper"] = sma20 + 2 * std20
        df["BB_Middle"] = sma20
        df["BB_Lower"] = sma20 - 2 * std20

        # ATR (14)
        tr = pd.concat(
            [
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        df["ATR"] = tr.ewm(alpha=1 / 14, adjust=False).mean()

        return df
