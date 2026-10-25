"""Data validation and cleaning pipeline for market data."""

from dataclasses import dataclass, field

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
    # Informational flags (extreme-but-plausible returns/volumes, dropped
    # long gaps). Genuine market moves are KEPT and do not lower confidence.
    notes: list[str] = field(default_factory=list)
    outliers_flagged: int = 0
    rows_dropped_for_gaps: int = 0

    @property
    def is_acceptable(self) -> bool:
        return self.confidence > 0.9

    def to_dict(self) -> dict:
        return {
            "completeness": round(float(self.completeness), 4),
            "outliers_removed": int(self.outliers_removed),
            "values_imputed": int(self.values_imputed),
            "duplicates_removed": int(self.duplicates_removed),
            "confidence": round(float(self.confidence), 4),
            "is_acceptable": bool(self.is_acceptable),
            "warnings": self.warnings,
            "notes": self.notes,
            "outliers_flagged": int(self.outliers_flagged),
            "rows_dropped_for_gaps": int(self.rows_dropped_for_gaps),
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
            report.warnings.append(
                f"Removed {report.duplicates_removed} duplicate timestamps"
            )

        # Step 2: Missing data analysis
        df, imputed = self._handle_missing_data(df, report)
        report.values_imputed = imputed

        # Step 3: OHLC consistency
        df = self._fix_ohlc_consistency(df, report)

        # Step 4: Outlier detection - FLAG only. Rows are never removed and
        # values never capped: the largest moves (crash days, earnings gaps)
        # are real and are exactly what a backtest must see, and capping
        # with full-sample statistics leaked future information into past
        # bars (2026-10 audit: e.g. 2020-03-12/16 silently dropped).
        self._flag_outliers(df, report)

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
            status,
            ticker,
            report.confidence,
            report.outliers_removed,
            report.values_imputed,
        )
        return df, report

    # ------------------------------------------------------------------
    # Missing data
    # ------------------------------------------------------------------

    def _handle_missing_data(
        self, df: pd.DataFrame, report: QualityReport
    ) -> tuple[pd.DataFrame, int]:
        """Causal gap handling only.

        Gaps of <= max_ffill_gap bars are forward-filled (past information
        only). Longer gaps are DROPPED - the previous linear interpolation
        drew the line to the post-gap price, so bars inside the gap were
        built from future information. Volume is forward-filled only (it
        was also back-filled). Leading values with no history are dropped.
        """
        price_cols = [c for c in ["Open", "High", "Low", "Close"] if c in df.columns]
        total_imputed = 0
        drop_mask = pd.Series(False, index=df.index)

        for col in price_cols:
            nans = df[col].isna()
            if not nans.any():
                continue
            run_id = (~nans).cumsum()
            run_len = nans.groupby(run_id).transform("sum")
            long_gap = nans & (run_len > self.max_ffill_gap)
            leading = nans & (run_id == 0)
            drop_mask |= long_gap | leading
            total_imputed += int((nans & ~long_gap & ~leading).sum())
            df[col] = df[col].ffill(limit=self.max_ffill_gap)

        if drop_mask.any():
            n = int(drop_mask.sum())
            report.rows_dropped_for_gaps = n
            report.notes.append(
                f"Dropped {n} rows inside gaps longer than {self.max_ffill_gap} bars "
                f"(not interpolated - that would use post-gap prices)"
            )
            df = df[~drop_mask]

        if "Volume" in df.columns:
            vol_nans = int(df["Volume"].isna().sum())
            if vol_nans:
                df["Volume"] = df["Volume"].ffill().fillna(0.0)
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
            report.warnings.append(
                f"Corrected {count} rows where High < max(Open, Close)"
            )

        if bad_low.any():
            count = bad_low.sum()
            df.loc[bad_low, "Low"] = df.loc[bad_low, ["Open", "Close"]].min(axis=1)
            report.warnings.append(
                f"Corrected {count} rows where Low > min(Open, Close)"
            )

        return df

    # ------------------------------------------------------------------
    # Outlier detection
    # ------------------------------------------------------------------

    def _flag_outliers(self, df: pd.DataFrame, report: QualityReport) -> None:
        """Flag (never remove/cap) extreme daily returns (IQR) and volumes
        (Z-score) as informational notes for review."""
        flagged = 0
        if "Close" in df.columns and len(df) > 20:
            returns = df["Close"].pct_change(fill_method=None).dropna()
            q1, q3 = returns.quantile(0.25), returns.quantile(0.75)
            iqr = q3 - q1
            extreme = returns[
                (returns < q1 - self.iqr_factor * iqr)
                | (returns > q3 + self.iqr_factor * iqr)
            ]
            if len(extreme):
                flagged += len(extreme)
                dates = ", ".join(
                    str(pd.Timestamp(d).date()) for d in extreme.index[:5]
                )
                report.notes.append(
                    f"{len(extreme)} extreme daily return(s) kept (e.g. {dates}) - "
                    f"verify against corporate actions if unexpected"
                )
        if "Volume" in df.columns and len(df) > 20:
            vol = df["Volume"].astype(float).replace(0, np.nan)
            if vol.std() > 0:
                z = (vol - vol.mean()) / vol.std()
                n = int((z.abs() > self.zscore_threshold).sum())
                if n:
                    flagged += n
                    report.notes.append(f"{n} extreme volume bar(s) kept unmodified")
        report.outliers_flagged = flagged

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
        # outliers_removed stays 0 (nothing is removed); flagged genuine
        # moves are informational notes and do not reduce confidence.
        score -= min(0.2, report.values_imputed * 0.005)
        score -= min(0.1, report.duplicates_removed * 0.02)
        score -= min(0.3, len(report.warnings) * 0.03)
        score *= report.completeness
        return max(0.0, min(1.0, round(score, 4)))
