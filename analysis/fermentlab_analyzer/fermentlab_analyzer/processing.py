"""Derive operational fermentation curves from raw session measurements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd


NUMERIC_FIELDS = (
    "sequence",
    "elapsed_ms",
    "temperature_dough_c",
    "temperature_ambient_c",
    "humidity_pct",
    "distance_mm",
    "dough_height_mm",
    "volume_ml",
)


@dataclass(frozen=True)
class AnalysisSummary:
    started_at: pd.Timestamp
    ended_at: pd.Timestamp
    duration_hours: float
    measurements: int
    signal_field: str
    signal_label: str
    signal_unit: str
    baseline_value: float
    current_value: float
    current_ratio_x: float
    current_growth_pct: float
    current_growth_rate_pct_h: float
    current_growth_accel_pct_h2: float
    maximum_growth_pct: float


def _rolling_slope(
    values: pd.Series, window_minutes: int, minimum_points: int = 3
) -> pd.Series:
    slopes: list[float] = []
    times = values.index
    window = timedelta(minutes=int(window_minutes))
    for current_time in times:
        sample = values.loc[current_time - window : current_time].dropna()
        if len(sample) < minimum_points:
            slopes.append(np.nan)
            continue
        hours = (sample.index - sample.index[0]).total_seconds() / 3600.0
        if hours[-1] <= 0:
            slopes.append(np.nan)
            continue
        slopes.append(float(np.polyfit(hours, sample.to_numpy(), 1)[0]))
    return pd.Series(slopes, index=times, dtype=float)


def _despike_signal(
    values: pd.Series, window_minutes: int, sigma: float
) -> pd.Series:
    """Replace impulsive outliers using rolling median + MAD threshold."""

    if window_minutes <= 0 or sigma <= 0:
        return values.copy()

    median = values.rolling(f"{int(window_minutes)}min", min_periods=3).median()
    deviation = (values - median).abs()
    mad = deviation.rolling(f"{int(window_minutes)}min", min_periods=3).median()
    robust_sigma = 1.4826 * mad

    threshold = robust_sigma * float(sigma)
    outlier_mask = threshold.gt(0) & deviation.gt(threshold)
    cleaned = values.copy()
    cleaned.loc[outlier_mask] = median.loc[outlier_mask]
    return cleaned


def analyze_session(
    measurements: pd.DataFrame,
    *,
    smoothing_minutes: int = 5,
    post_smoothing_minutes: int = 0,
    despike_window_minutes: int = 0,
    despike_sigma: float = 0.0,
    baseline_offset_minutes: int = 0,
    baseline_minutes: int = 5,
    rate_window_minutes: int = 30,
    acceleration_window_minutes: int = 60,
    minimum_slope_points: int = 3,
) -> pd.DataFrame:
    """Return cleaned measurements plus normalized growth and growth rate."""

    if measurements.empty:
        raise ValueError("La sessione non contiene misure.")
    if "_time" not in measurements:
        raise ValueError("Serve la colonna temporale _time.")

    frame = measurements.copy()
    frame["_time"] = pd.to_datetime(frame["_time"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["_time"]).sort_values("_time")
    frame = frame.drop_duplicates("_time", keep="last").set_index("_time")

    for field in NUMERIC_FIELDS:
        if field in frame:
            frame[field] = pd.to_numeric(frame[field], errors="coerce")

    signal_options = (
        ("volume_ml", "Volume", "ml"),
        ("dough_height_mm", "Altezza impasto", "mm"),
    )
    selected = next(
        (
            option
            for option in signal_options
            if option[0] in frame and frame[option[0]].gt(0).any()
        ),
        None,
    )
    if selected is None:
        raise ValueError("La sessione non contiene volume o altezza validi.")
    signal_field, signal_label, signal_unit = selected

    signal_raw = frame[signal_field].where(frame[signal_field] > 0)
    signal_despiked = _despike_signal(
        signal_raw,
        int(despike_window_minutes),
        float(despike_sigma),
    )
    signal_smooth = signal_despiked.rolling(
        f"{int(smoothing_minutes)}min", min_periods=1
    ).median()
    if int(post_smoothing_minutes) > 0:
        signal_smooth = signal_smooth.rolling(
            f"{int(post_smoothing_minutes)}min", min_periods=1
        ).mean()

    frame["signal_raw"] = signal_raw
    frame["signal_despiked"] = signal_despiked
    frame["signal_smooth"] = signal_smooth

    baseline_start = frame.index[0] + timedelta(
        minutes=int(baseline_offset_minutes)
    )
    baseline_stop = baseline_start + timedelta(minutes=int(baseline_minutes))
    baseline_values = frame.loc[
        baseline_start:baseline_stop, "signal_smooth"
    ].dropna()
    if baseline_values.empty:
        raise ValueError("Non è possibile determinare il volume iniziale.")
    baseline = float(baseline_values.median())

    frame["elapsed_hours"] = (
        frame.index - frame.index[0]
    ).total_seconds() / 3600.0
    frame["growth_pct"] = (frame["signal_smooth"] / baseline - 1.0) * 100.0
    frame.loc[frame.index < baseline_start, "growth_pct"] = np.nan
    frame["growth_rate_pct_h"] = _rolling_slope(
        frame["growth_pct"],
        int(rate_window_minutes),
        minimum_points=max(3, int(minimum_slope_points)),
    )
    frame["growth_accel_pct_h2"] = _rolling_slope(
        frame["growth_rate_pct_h"],
        int(acceleration_window_minutes),
        minimum_points=max(3, int(minimum_slope_points)),
    )
    frame.attrs["signal_field"] = signal_field
    frame.attrs["signal_label"] = signal_label
    frame.attrs["signal_unit"] = signal_unit
    frame.attrs["baseline_value"] = baseline
    return frame


def summarize_session(analysis: pd.DataFrame) -> AnalysisSummary:
    if analysis.empty:
        raise ValueError("L'analisi non contiene dati.")

    growth_rate = analysis["growth_rate_pct_h"].dropna()
    growth_accel = analysis["growth_accel_pct_h2"].dropna()
    return AnalysisSummary(
        started_at=analysis.index[0],
        ended_at=analysis.index[-1],
        duration_hours=float(analysis["elapsed_hours"].iloc[-1]),
        measurements=len(analysis),
        signal_field=str(analysis.attrs["signal_field"]),
        signal_label=str(analysis.attrs["signal_label"]),
        signal_unit=str(analysis.attrs["signal_unit"]),
        baseline_value=float(analysis.attrs["baseline_value"]),
        current_value=float(analysis["signal_smooth"].iloc[-1]),
        current_ratio_x=(
            float(analysis["signal_smooth"].iloc[-1])
            / float(analysis.attrs["baseline_value"])
        ),
        current_growth_pct=float(analysis["growth_pct"].iloc[-1]),
        current_growth_rate_pct_h=(
            float(growth_rate.iloc[-1]) if not growth_rate.empty else float("nan")
        ),
        current_growth_accel_pct_h2=(
            float(growth_accel.iloc[-1])
            if not growth_accel.empty
            else float("nan")
        ),
        maximum_growth_pct=float(analysis["growth_pct"].max()),
    )
