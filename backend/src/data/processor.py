"""Feature engineering for market data using technical analysis indicators."""

from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from ..utils.logger import setup_logger

logger = setup_logger("alphalab.processor")


class FeatureEngineer:
    """Compute technical indicators and statistical features on OHLCV data.

    Uses stockstats and manual implementations to produce a wide feature
    DataFrame suitable for strategy signal generation and backtesting.
    """

    def __init__(self, benchmark_ticker: str = "SPY"):
        self.benchmark_ticker = benchmark_ticker

    def process(
        self,
        df: pd.DataFrame,
        benchmark: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Add all features to the OHLCV DataFrame.

        Args:
            df: DataFrame with columns Open, High, Low, Close, Volume indexed by Date.
            benchmark: Optional benchmark DataFrame (e.g. SPY) for beta/correlation.

        Returns:
            DataFrame with original OHLCV + all computed features.
        """
        df = df.copy()
        required = {"Open", "High", "Low", "Close", "Volume"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        if len(df) < 30:
            logger.warning("Only %d rows — some indicators will be NaN", len(df))

        df = self._add_trend_indicators(df)
        df = self._add_momentum_indicators(df)
        df = self._add_volatility_indicators(df)
        df = self._add_volume_indicators(df)
        df = self._add_statistical_features(df, benchmark)
        df = self._add_advanced_features(df)

        logger.info("Feature engineering complete: %d features, %d rows", len(df.columns), len(df))
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

        # EMA
        for w in (12, 26, 50, 200):
            df[f"EMA_{w}"] = close.ewm(span=w, adjust=False).mean()

        # MACD (12, 26, 9)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df["MACD"] = ema12 - ema26
        df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

        # ADX (14-day)
        df = FeatureEngineer._compute_adx(df, period=14)

        # Parabolic SAR
        df = FeatureEngineer._compute_psar(df)

        return df

    @staticmethod
    def _compute_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        high, low, close = df["High"], df["Low"], df["Close"]
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1 / period, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)

        dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
        df["ADX"] = dx.ewm(alpha=1 / period, adjust=False).mean()
        df["Plus_DI"] = plus_di
        df["Minus_DI"] = minus_di
        return df

    @staticmethod
    def _compute_psar(df: pd.DataFrame, af_start: float = 0.02, af_max: float = 0.2) -> pd.DataFrame:
        high = df["High"].values
        low = df["Low"].values
        n = len(df)
        psar = np.full(n, np.nan)
        if n < 2:
            df["PSAR"] = psar
            return df

        bull = True
        af = af_start
        ep = high[0]
        psar[0] = low[0]

        for i in range(1, n):
            prev_psar = psar[i - 1]
            if bull:
                psar[i] = prev_psar + af * (ep - prev_psar)
                psar[i] = min(psar[i], low[i - 1])
                if i >= 2:
                    psar[i] = min(psar[i], low[i - 2])
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + af_start, af_max)
                if low[i] < psar[i]:
                    bull = False
                    psar[i] = ep
                    ep = low[i]
                    af = af_start
            else:
                psar[i] = prev_psar + af * (ep - prev_psar)
                psar[i] = max(psar[i], high[i - 1])
                if i >= 2:
                    psar[i] = max(psar[i], high[i - 2])
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + af_start, af_max)
                if high[i] > psar[i]:
                    bull = True
                    psar[i] = ep
                    ep = high[i]
                    af = af_start

        df["PSAR"] = psar
        return df

    # ------------------------------------------------------------------
    # Momentum
    # ------------------------------------------------------------------

    @staticmethod
    def _add_momentum_indicators(df: pd.DataFrame) -> pd.DataFrame:
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # RSI (14)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["RSI"] = 100 - (100 / (1 + rs))
        df["RSI"] = df["RSI"].clip(0, 100)

        # Stochastic Oscillator
        low14 = low.rolling(14, min_periods=14).min()
        high14 = high.rolling(14, min_periods=14).max()
        denom = (high14 - low14).replace(0, np.nan)
        df["Stoch_K"] = 100 * (close - low14) / denom
        df["Stoch_D"] = df["Stoch_K"].rolling(3, min_periods=3).mean()

        # Williams %R
        df["Williams_R"] = -100 * (high14 - close) / denom

        # Rate of Change
        df["ROC_10"] = close.pct_change(periods=10, fill_method=None) * 100

        # Chande Momentum Oscillator (9-day)
        period = 9
        up = delta.clip(lower=0).rolling(period, min_periods=period).sum()
        down = (-delta.clip(upper=0)).rolling(period, min_periods=period).sum()
        total = up + down
        df["CMO"] = ((up - down) / total.replace(0, np.nan)) * 100

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
        df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / sma20.replace(0, np.nan)

        # ATR (14)
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        df["ATR"] = tr.ewm(alpha=1 / 14, adjust=False).mean()

        # Historical volatility
        log_ret = np.log(close / close.shift(1))
        for w in (30, 60, 90):
            df[f"HV_{w}"] = log_ret.rolling(w, min_periods=w).std() * np.sqrt(252)

        # Keltner Channels
        ema20 = close.ewm(span=20, adjust=False).mean()
        df["Keltner_Upper"] = ema20 + 2 * df["ATR"]
        df["Keltner_Lower"] = ema20 - 2 * df["ATR"]

        return df

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    @staticmethod
    def _add_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
        close = df["Close"]
        volume = df["Volume"]
        high = df["High"]
        low = df["Low"]

        # OBV
        direction = np.sign(close.diff()).fillna(0)
        df["OBV"] = (volume * direction).cumsum()

        # VWMA
        for w in (10, 20):
            vw = (close * volume).rolling(w, min_periods=w).sum()
            vol_sum = volume.rolling(w, min_periods=w).sum()
            df[f"VWMA_{w}"] = vw / vol_sum.replace(0, np.nan)

        # Money Flow Index (14)
        tp = (high + low + close) / 3
        raw_mf = tp * volume
        flow_dir = tp.diff()
        pos_flow = raw_mf.where(flow_dir > 0, 0).rolling(14, min_periods=14).sum()
        neg_flow = raw_mf.where(flow_dir <= 0, 0).rolling(14, min_periods=14).sum()
        mfi_ratio = pos_flow / neg_flow.replace(0, np.nan)
        df["MFI"] = 100 - (100 / (1 + mfi_ratio))

        # Accumulation/Distribution
        clv = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
        df["AD"] = (clv.fillna(0) * volume).cumsum()

        # Volume MA
        df["Volume_SMA_20"] = volume.rolling(20, min_periods=20).mean()

        return df

    # ------------------------------------------------------------------
    # Statistical
    # ------------------------------------------------------------------

    @staticmethod
    def _add_statistical_features(
        df: pd.DataFrame, benchmark: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        close = df["Close"]

        # Returns
        df["Return"] = close.pct_change(fill_method=None)
        df["Log_Return"] = np.log(close / close.shift(1))

        # Rolling stats
        for w in (20, 60):
            df[f"Return_Mean_{w}"] = df["Return"].rolling(w, min_periods=w).mean()
            df[f"Return_Std_{w}"] = df["Return"].rolling(w, min_periods=w).std()

        # Skewness and kurtosis (30-day)
        df["Skew_30"] = df["Return"].rolling(30, min_periods=30).skew()
        df["Kurt_30"] = df["Return"].rolling(30, min_periods=30).kurt()

        # Beta and correlation vs benchmark
        if benchmark is not None and "Close" in benchmark.columns and len(benchmark) > 60:
            bench_ret = benchmark["Close"].pct_change(fill_method=None).reindex(df.index)
            df["Benchmark_Return"] = bench_ret
            rolling_cov = df["Return"].rolling(60, min_periods=60).cov(bench_ret)
            rolling_var = bench_ret.rolling(60, min_periods=60).var()
            df["Beta_60"] = rolling_cov / rolling_var.replace(0, np.nan)
            df["Corr_60"] = df["Return"].rolling(60, min_periods=60).corr(bench_ret)

        return df

    # ------------------------------------------------------------------
    # Advanced
    # ------------------------------------------------------------------

    @staticmethod
    def _add_advanced_features(df: pd.DataFrame) -> pd.DataFrame:
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # Support / Resistance (local minima/maxima over 20-day window)
        window = 20
        if len(df) >= window:
            df["Resistance"] = high.rolling(window, min_periods=window).max()
            df["Support"] = low.rolling(window, min_periods=window).min()

        # Fibonacci retracement levels (rolling 60-day swing)
        fib_window = 60
        if len(df) >= fib_window:
            swing_high = high.rolling(fib_window, min_periods=fib_window).max()
            swing_low = low.rolling(fib_window, min_periods=fib_window).min()
            diff = swing_high - swing_low
            df["Fib_0.236"] = swing_high - 0.236 * diff
            df["Fib_0.382"] = swing_high - 0.382 * diff
            df["Fib_0.500"] = swing_high - 0.500 * diff
            df["Fib_0.618"] = swing_high - 0.618 * diff

        # Pivot points (classic)
        df["Pivot"] = (high.shift(1) + low.shift(1) + close.shift(1)) / 3
        df["Pivot_R1"] = 2 * df["Pivot"] - low.shift(1)
        df["Pivot_S1"] = 2 * df["Pivot"] - high.shift(1)

        # Gap analysis
        df["Gap"] = df["Open"] - close.shift(1)
        df["Gap_Pct"] = df["Gap"] / close.shift(1).replace(0, np.nan) * 100

        return df
