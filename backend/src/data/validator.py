"""Data validation and cleaning pipeline for market data."""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from ..utils.logger import setup_logger

logger = setup_logger("alphalab.validator")


@dataclass
class QualityReport:
    """Comprehensive data quality report."""

    completeness: float = 1.0
    outliers_removed: int = 0
    values_imputed: int = 0
    duplicates_removed: int = 0
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)

    @property
    def is_acceptable(self) -> bool:
        return self.confidence > 0.9

    def to_dict(self) -> dict:
        return {
            "completeness": round(self.completeness, 4),
            "outliers_removed": self.outliers_removed,
            "values_imputed": self.values_imputed,
            "duplicates_removed": self.duplicates_removed,
            "confidence": round(self.confidence, 4),
            "is_acceptable": self.is_acceptable,
            "warnings": self.warnings,
        }


class DataValidator:
    """Validates and cleans OHLCV market data.

    Runs missing-data analysis, outlier detection, price consistency checks,
    and a cleaning pipeline. Produces a QualityReport with a confidence score.
    """

    def __init__(
        self,
        max_ffill_gap: int = 3,
        iqr_factor: float = 5.0,
        zscore_threshold: float = 5.0,
    ):
        self.max_ffill_gap = max_ffill_gap
        self.iqr_factor = iqr_factor
        self.zscore_threshold = zscore_threshold

    def validate_and_clean(
        self, df: pd.DataFrame, ticker: str = ""
    ) -> tuple[pd.DataFrame, QualityReport]:
        """Run the full validation and cleaning pipeline.

        Returns:
            (cleaned DataFrame, QualityReport)
        """
        report = QualityReport()
        df = df.copy()

        if df.empty:
            report.confidence = 0.0
            report.warnings.append("Empty DataFrame")
            return df, report

        # Step 1: Remove duplicates
        before = len(df)
        df = df[~df.index.duplicated(keep="last")]
        report.duplicates_removed = before - len(df)
        if report.duplicates_removed:
            report.warnings.append(f"Removed {report.duplicates_removed} duplicate timestamps")

        # Step 2: Missing data analysis
        df, imputed = self._handle_missing_data(df, report)
        report.values_imputed = imputed

        # Step 3: OHLC consistency
        df = self._fix_ohlc_consistency(df, report)

        # Step 4: Outlier detection and removal
        df, removed = self._remove_outliers(df, report)
        report.outliers_removed = removed

        # Step 5: Volume validation
        self._validate_volume(df, report)

        # Step 6: Detect suspicious patterns
        self._detect_suspicious_patterns(df, report)

        # Step 7: Compute completeness and confidence
        report.completeness = self._compute_completeness(df)
        report.confidence = self._compute_confidence(report)

        status = "PASS" if report.is_acceptable else "FAIL"
        logger.info(
            "Validation %s for %s: confidence=%.3f, outliers=%d, imputed=%d",
            status, ticker, report.confidence, report.outliers_removed, report.values_imputed,
        )
        return df, report

    # ------------------------------------------------------------------
    # Missing data
    # ------------------------------------------------------------------

    def _handle_missing_data(
        self, df: pd.DataFrame, report: QualityReport
    ) -> tuple[pd.DataFrame, int]:
        """Fill small gaps with ffill, interpolate larger ones, flag for review."""
        price_cols = [c for c in ["Open", "High", "Low", "Close"] if c in df.columns]
        total_imputed = 0

        for col in price_cols:
            nans = df[col].isna()
            if not nans.any():
                continue

            # Identify runs of NaN
            groups = (~nans).cumsum()
            nan_groups = nans.groupby(groups)

            for _, group in nan_groups:
                if not group.any():
                    continue
                gap_len = group.sum()
                if gap_len <= self.max_ffill_gap:
                    df[col] = df[col].ffill(limit=self.max_ffill_gap)
                else:
                    df[col] = df[col].interpolate(method="linear")
                    report.warnings.append(
                        f"Interpolated {gap_len}-day gap in {col} (review recommended)"
                    )
                total_imputed += gap_len

        # Forward-fill volume gaps
        if "Volume" in df.columns:
            vol_nans = df["Volume"].isna().sum()
            if vol_nans:
                df["Volume"] = df["Volume"].ffill().bfill()
                total_imputed += vol_nans

        return df, total_imputed

    # ------------------------------------------------------------------
    # OHLC consistency
    # ------------------------------------------------------------------

    @staticmethod
    def _fix_ohlc_consistency(df: pd.DataFrame, report: QualityReport) -> pd.DataFrame:
        """Ensure High >= max(O,C) and Low <= min(O,C)."""
        required = {"Open", "High", "Low", "Close"}
        if not required.issubset(df.columns):
            return df

        bad_high = df["High"] < df[["Open", "Close"]].max(axis=1)
        bad_low = df["Low"] > df[["Open", "Close"]].min(axis=1)

        if bad_high.any():
            count = bad_high.sum()
            df.loc[bad_high, "High"] = df.loc[bad_high, ["Open", "Close"]].max(axis=1)
            report.warnings.append(f"Corrected {count} rows where High < max(Open, Close)")

        if bad_low.any():
            count = bad_low.sum()
            df.loc[bad_low, "Low"] = df.loc[bad_low, ["Open", "Close"]].min(axis=1)
            report.warnings.append(f"Corrected {count} rows where Low > min(Open, Close)")

        return df

    # ------------------------------------------------------------------
    # Outlier detection
    # ------------------------------------------------------------------

    def _remove_outliers(
        self, df: pd.DataFrame, report: QualityReport
    ) -> tuple[pd.DataFrame, int]:
        """Use IQR on returns and Z-score on volume to detect outliers."""
        removed = 0
        mask = pd.Series(True, index=df.index)

        # Price outliers via IQR on daily returns
        if "Close" in df.columns and len(df) > 20:
            returns = df["Close"].pct_change().dropna()
            q1 = returns.quantile(0.25)
            q3 = returns.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - self.iqr_factor * iqr
            upper = q3 + self.iqr_factor * iqr
            outlier_returns = (returns < lower) | (returns > upper)
            if outlier_returns.any():
                count = outlier_returns.sum()
                mask.loc[outlier_returns[outlier_returns].index] = False
                report.warnings.append(f"Flagged {count} price return outliers (IQR)")

        # Volume outliers via Z-score
        if "Volume" in df.columns and len(df) > 20:
            df["Volume"] = df["Volume"].astype(float)
            vol = df["Volume"].replace(0, np.nan)
            if vol.std() > 0:
                z = (vol - vol.mean()) / vol.std()
                vol_outlier = z.abs() > self.zscore_threshold
                if vol_outlier.any():
                    count = vol_outlier.sum()
                    report.warnings.append(f"Flagged {count} volume anomalies (Z-score)")
                    # Cap rather than remove volume outliers
                    upper_cap = vol.mean() + self.zscore_threshold * vol.std()
                    df.loc[vol_outlier, "Volume"] = upper_cap

        removed = (~mask).sum()
        df = df[mask]
        return df, removed

    # ------------------------------------------------------------------
    # Volume validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_volume(df: pd.DataFrame, report: QualityReport):
        if "Volume" not in df.columns:
            return
        neg = (df["Volume"] < 0).sum()
        if neg:
            df.loc[df["Volume"] < 0, "Volume"] = 0
            report.warnings.append(f"Set {neg} negative volume values to 0")

    # ------------------------------------------------------------------
    # Suspicious patterns
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_suspicious_patterns(df: pd.DataFrame, report: QualityReport):
        """Flag constant prices or zero-volume streaks."""
        if "Close" not in df.columns or len(df) < 5:
            return

        # Constant close for 5+ consecutive days
        changes = df["Close"].diff().abs()
        no_change = changes == 0
        streaks = no_change.astype(int).groupby((~no_change).cumsum()).sum()
        long_streaks = (streaks >= 5).sum()
        if long_streaks:
            report.warnings.append(
                f"{long_streaks} streak(s) of 5+ days with constant close price"
            )

        # Zero volume for 5+ consecutive days
        if "Volume" in df.columns:
            zero_vol = df["Volume"] == 0
            vol_streaks = zero_vol.astype(int).groupby((~zero_vol).cumsum()).sum()
            long_vol = (vol_streaks >= 5).sum()
            if long_vol:
                report.warnings.append(
                    f"{long_vol} streak(s) of 5+ days with zero volume"
                )

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_completeness(df: pd.DataFrame) -> float:
        if df.empty:
            return 0.0
        price_cols = [c for c in ["Open", "High", "Low", "Close"] if c in df.columns]
        if not price_cols:
            return 0.0
        total_cells = len(df) * len(price_cols)
        non_null = df[price_cols].notna().sum().sum()
        return non_null / total_cells

    @staticmethod
    def _compute_confidence(report: QualityReport) -> float:
        """Aggregate quality signals into a 0-1 confidence score."""
        score = 1.0
        # Penalize for issues
        score -= min(0.2, report.outliers_removed * 0.01)
        score -= min(0.2, report.values_imputed * 0.005)
        score -= min(0.1, report.duplicates_removed * 0.02)
        score -= min(0.3, len(report.warnings) * 0.03)
        score *= report.completeness
        return max(0.0, min(1.0, round(score, 4)))
