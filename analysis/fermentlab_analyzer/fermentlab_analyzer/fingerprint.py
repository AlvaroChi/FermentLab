"""Quantitative post-processing for FermentLab fermentation sessions.

The functions in this module operate on the dataframe returned by
``processing.analyze_session``.  They never mutate raw or processed input data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from typing import Literal, Sequence

import numpy as np
import pandas as pd


GROWTH_THRESHOLDS = (10, 25, 50, 75, 100, 150, 200)
QualityStatus = Literal["valid", "unavailable", "low_confidence"]


@dataclass(frozen=True)
class FermentationAnalysisConfig:
    """Central configuration for derivative and phase detection algorithms."""

    derivative_window_minutes: float = 30.0
    polynomial_degree: int = 2
    minimum_derivative_points: int = 7
    minimum_analysis_points: int = 12
    max_missing_fraction: float = 0.25
    lag_rate_fraction: float = 0.20
    lag_persistence_minutes: float = 15.0
    plateau_rate_fraction: float = 0.10
    plateau_persistence_minutes: float = 30.0
    plateau_min_growth_percent: float = 50.0
    collapse_loss_percent: float = 5.0
    collapse_persistence_minutes: float = 30.0
    collapse_min_peak_growth_percent: float = 20.0
    active_rate_fraction: float = 0.20
    thermal_references_c: tuple[float, ...] = (0.0, 4.0, 20.0)


@dataclass(frozen=True)
class MetricQuality:
    """Availability/confidence attached to a derived metric or event."""

    status: QualityStatus
    reason: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {"status": self.status, "reason": self.reason}


@dataclass(frozen=True)
class FermentationMetrics:
    """Machine-readable quantitative fingerprint for one session."""

    session_id: str
    signal_field: str
    signal_unit: str
    duration_h: float | None = None
    initial_value: float | None = None
    max_value: float | None = None
    maximum_growth_percent: float | None = None
    time_of_max_value_h: float | None = None
    t10_h: float | None = None
    t25_h: float | None = None
    t50_h: float | None = None
    t75_h: float | None = None
    t100_h: float | None = None
    t150_h: float | None = None
    t200_h: float | None = None
    lag_time_h: float | None = None
    max_growth_rate_value_h: float | None = None
    time_of_max_growth_rate_h: float | None = None
    value_at_max_growth_rate: float | None = None
    growth_percent_at_max_growth_rate: float | None = None
    average_rate_0_25_value_h: float | None = None
    average_rate_25_50_value_h: float | None = None
    average_rate_50_75_value_h: float | None = None
    average_rate_75_100_value_h: float | None = None
    max_specific_growth_rate_h: float | None = None
    time_of_max_specific_growth_rate_h: float | None = None
    inflection_time_h: float | None = None
    inflection_value: float | None = None
    inflection_growth_percent: float | None = None
    growth_rate_at_inflection_value_h: float | None = None
    plateau_start_time_h: float | None = None
    plateau_value: float | None = None
    plateau_growth_percent: float | None = None
    collapse_detected: bool = False
    collapse_start_time_h: float | None = None
    peak_before_collapse: float | None = None
    loss_from_peak_percent: float | None = None
    active_phase_start_h: float | None = None
    active_phase_end_h: float | None = None
    active_phase_duration_h: float | None = None
    early_rate_value_h: float | None = None
    late_rate_value_h: float | None = None
    late_early_ratio: float | None = None
    dough_temp_initial_c: float | None = None
    dough_temp_final_c: float | None = None
    dough_temp_min_c: float | None = None
    dough_temp_max_c: float | None = None
    dough_temp_mean_c: float | None = None
    dough_temp_median_c: float | None = None
    dough_temp_at_t25_c: float | None = None
    dough_temp_at_t50_c: float | None = None
    dough_temp_at_t75_c: float | None = None
    dough_temp_at_t100_c: float | None = None
    dough_temp_at_max_growth_rate_c: float | None = None
    dough_temp_at_inflection_c: float | None = None
    dough_temp_at_plateau_c: float | None = None
    ambient_temp_min_c: float | None = None
    ambient_temp_max_c: float | None = None
    ambient_temp_mean_c: float | None = None
    ambient_temp_median_c: float | None = None
    delta_t_initial_c: float | None = None
    delta_t_min_c: float | None = None
    delta_t_max_c: float | None = None
    delta_t_mean_c: float | None = None
    time_of_delta_t_max_h: float | None = None
    thermal_integral_0c_c_h: float | None = None
    thermal_integral_4c_c_h: float | None = None
    thermal_integral_20c_c_h: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class FermentationFingerprint:
    """Metrics plus derived curves, characteristic events and quality metadata."""

    metrics: FermentationMetrics
    curves: pd.DataFrame
    events_h: dict[str, float | None]
    quality: dict[str, MetricQuality] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def to_dict(self, *, include_quality: bool = True) -> dict[str, object]:
        result = self.metrics.to_dict()
        if include_quality:
            result["quality"] = {
                name: item.to_dict() for name, item in self.quality.items()
            }
            result["warnings"] = list(self.warnings)
        return result


def _finite_or_none(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _numeric_array(frame: pd.DataFrame, field_name: str) -> np.ndarray:
    if field_name not in frame:
        return np.full(len(frame), np.nan, dtype=float)
    return pd.to_numeric(frame[field_name], errors="coerce").to_numpy(
        dtype=float, copy=True
    )


def _session_time_hours(frame: pd.DataFrame) -> np.ndarray:
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("L'analisi deve avere un DatetimeIndex.")
    if frame.index.hasnans:
        raise ValueError("La timeline contiene timestamp non validi.")
    return (frame.index - frame.index[0]).total_seconds().to_numpy(dtype=float) / 3600.0


def _local_polynomial_curves(
    times_h: np.ndarray,
    values: np.ndarray,
    *,
    window_minutes: float,
    degree: int,
    minimum_points: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return centered local-polynomial value, first and second derivative.

    Unlike a classic fixed-sample Savitzky-Golay filter, this implementation
    fits against real elapsed time, so it also supports irregular sampling.
    """

    valid = np.isfinite(times_h) & np.isfinite(values)
    result_value = np.full(len(values), np.nan, dtype=float)
    result_rate = np.full(len(values), np.nan, dtype=float)
    result_acceleration = np.full(len(values), np.nan, dtype=float)
    if int(valid.sum()) < max(3, minimum_points):
        return result_value, result_rate, result_acceleration

    valid_times = times_h[valid]
    valid_values = values[valid]
    half_window_h = max(float(window_minutes) / 120.0, np.finfo(float).eps)
    required = max(3, int(minimum_points))

    for output_index, current_time in enumerate(times_h):
        left = int(np.searchsorted(valid_times, current_time - half_window_h, side="left"))
        right = int(np.searchsorted(valid_times, current_time + half_window_h, side="right"))
        if right - left < required:
            insertion = int(np.searchsorted(valid_times, current_time))
            left = max(0, insertion - required // 2)
            right = min(len(valid_times), left + required)
            left = max(0, right - required)

        sample_times = valid_times[left:right] - current_time
        sample_values = valid_values[left:right]
        if len(sample_values) < 3 or np.ptp(sample_times) <= 0:
            continue

        fit_degree = min(max(1, int(degree)), len(sample_values) - 1)
        try:
            coefficients = np.polyfit(sample_times, sample_values, fit_degree)
        except (ValueError, np.linalg.LinAlgError):
            continue
        polynomial = np.poly1d(coefficients)
        result_value[output_index] = float(polynomial(0.0))
        result_rate[output_index] = float(np.polyder(polynomial, 1)(0.0))
        if fit_degree >= 2:
            result_acceleration[output_index] = float(
                np.polyder(polynomial, 2)(0.0)
            )

    return result_value, result_rate, result_acceleration


def time_to_growth(
    times_h: Sequence[float], growth_percent: Sequence[float], percent: float
) -> float | None:
    """Return the first threshold-crossing time using linear interpolation."""

    times = np.asarray(times_h, dtype=float)
    growth = np.asarray(growth_percent, dtype=float)
    valid = np.isfinite(times) & np.isfinite(growth)
    times = times[valid]
    growth = growth[valid]
    if len(times) == 0:
        return None

    order = np.argsort(times)
    times = times[order]
    growth = growth[order]
    target = float(percent)
    if growth[0] >= target:
        return float(times[0])

    crossing_indices = np.flatnonzero((growth[1:] >= target) & (growth[:-1] < target))
    if len(crossing_indices) == 0:
        return None
    index = int(crossing_indices[0])
    x0, x1 = float(times[index]), float(times[index + 1])
    y0, y1 = float(growth[index]), float(growth[index + 1])
    if y1 == y0:
        return x1
    return x0 + (target - y0) * (x1 - x0) / (y1 - y0)


def _interpolate_at(
    event_time_h: float | None,
    times_h: np.ndarray,
    values: np.ndarray,
) -> float | None:
    if event_time_h is None:
        return None
    valid = np.isfinite(times_h) & np.isfinite(values)
    if valid.sum() < 2:
        return None
    valid_times = times_h[valid]
    valid_values = values[valid]
    if event_time_h < valid_times[0] or event_time_h > valid_times[-1]:
        return None
    return float(np.interp(event_time_h, valid_times, valid_values))


def _max_gap_hours(times_h: np.ndarray) -> float:
    finite_times = times_h[np.isfinite(times_h)]
    if len(finite_times) < 2:
        return math.inf
    median_gap = float(np.median(np.diff(finite_times)))
    return max(median_gap * 3.0, 1.0 / 3600.0)


def _true_runs(times_h: np.ndarray, condition: np.ndarray) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    max_gap = _max_gap_hours(times_h)
    start: int | None = None
    previous: int | None = None
    for index, is_true in enumerate(condition):
        if not bool(is_true) or not math.isfinite(float(times_h[index])):
            if start is not None and previous is not None:
                runs.append((start, previous))
            start = None
            previous = None
            continue
        if previous is not None and times_h[index] - times_h[previous] > max_gap:
            runs.append((start if start is not None else previous, previous))
            start = index
        elif start is None:
            start = index
        previous = index
    if start is not None and previous is not None:
        runs.append((start, previous))
    return runs


def _first_sustained_start(
    times_h: np.ndarray,
    condition: np.ndarray,
    duration_minutes: float,
) -> float | None:
    required_h = max(0.0, float(duration_minutes) / 60.0)
    for start, end in _true_runs(times_h, condition):
        if times_h[end] - times_h[start] >= required_h:
            return float(times_h[start])
    return None


def _longest_true_run(
    times_h: np.ndarray, condition: np.ndarray
) -> tuple[float | None, float | None]:
    runs = _true_runs(times_h, condition)
    if not runs:
        return None, None
    start, end = max(runs, key=lambda pair: times_h[pair[1]] - times_h[pair[0]])
    return float(times_h[start]), float(times_h[end])


def _temperature_stats(values: np.ndarray) -> dict[str, float | None]:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return {
            "initial": None,
            "final": None,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
        }
    return {
        "initial": float(finite[0]),
        "final": float(finite[-1]),
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "mean": float(np.mean(finite)),
        "median": float(np.median(finite)),
    }


def _trapezoidal_integral(
    times_h: np.ndarray, values: np.ndarray, reference: float
) -> float | None:
    valid = np.isfinite(times_h) & np.isfinite(values)
    if valid.sum() < 2:
        return None
    x = times_h[valid]
    y = values[valid] - float(reference)
    order = np.argsort(x)
    x = x[order]
    y = y[order]
    return float(np.sum((y[1:] + y[:-1]) * 0.5 * np.diff(x)))


def _average_rate_between(
    start_percent: float,
    end_percent: float,
    threshold_times: dict[int, float | None],
    times_h: np.ndarray,
    growth_percent: np.ndarray,
    values: np.ndarray,
) -> float | None:
    start_time = (
        time_to_growth(times_h, growth_percent, start_percent)
        if start_percent == 0
        else threshold_times.get(int(start_percent))
    )
    end_time = threshold_times.get(int(end_percent))
    if start_time is None or end_time is None or end_time <= start_time:
        return None
    start_value = _interpolate_at(start_time, times_h, values)
    end_value = _interpolate_at(end_time, times_h, values)
    if start_value is None or end_value is None:
        return None
    return (end_value - start_value) / (end_time - start_time)


def _quality_for(
    available: bool,
    *,
    low_confidence: bool,
    unavailable_reason: str,
    low_confidence_reason: str,
) -> MetricQuality:
    if not available:
        return MetricQuality("unavailable", unavailable_reason)
    if low_confidence:
        return MetricQuality("low_confidence", low_confidence_reason)
    return MetricQuality("valid")


def compute_fermentation_fingerprint(
    analysis: pd.DataFrame,
    session_id: str,
    config: FermentationAnalysisConfig | None = None,
) -> FermentationFingerprint:
    """Compute quantitative metrics from an analyzed FermentLab session."""

    if analysis.empty:
        raise ValueError("L'analisi non contiene dati.")
    config = config or FermentationAnalysisConfig()
    frame = analysis.copy(deep=True).sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    times_h = _session_time_hours(frame)

    signal_field = str(frame.attrs.get("signal_field") or "")
    signal_unit = str(frame.attrs.get("signal_unit") or "")
    baseline_value = _finite_or_none(frame.attrs.get("baseline_value"))
    if not signal_field or baseline_value is None or baseline_value <= 0:
        raise ValueError("L'analisi non contiene segnale e baseline validi.")

    source_field = "signal_despiked" if "signal_despiked" in frame else "signal_smooth"
    source_values = _numeric_array(frame, source_field)
    source_values[source_values <= 0] = np.nan
    analyzed_values, growth_rate, growth_acceleration = _local_polynomial_curves(
        times_h,
        source_values,
        window_minutes=config.derivative_window_minutes,
        degree=config.polynomial_degree,
        minimum_points=config.minimum_derivative_points,
    )
    analyzed_values[analyzed_values <= 0] = np.nan

    growth_valid = (
        pd.to_numeric(frame["growth_pct"], errors="coerce").notna().to_numpy()
        if "growth_pct" in frame
        else np.ones(len(frame), dtype=bool)
    )
    relative_growth = analyzed_values / baseline_value
    growth_percent = (relative_growth - 1.0) * 100.0
    relative_growth[~growth_valid] = np.nan
    growth_percent[~growth_valid] = np.nan
    growth_rate[~growth_valid] = np.nan
    growth_acceleration[~growth_valid] = np.nan
    specific_growth_rate = growth_rate / analyzed_values

    finite_signal = np.isfinite(analyzed_values) & growth_valid
    valid_count = int(finite_signal.sum())
    missing_fraction = 1.0 - valid_count / max(1, int(growth_valid.sum()))
    low_confidence = (
        valid_count < config.minimum_analysis_points
        or missing_fraction > config.max_missing_fraction
    )
    confidence_reason = (
        f"solo {valid_count} campioni validi"
        if valid_count < config.minimum_analysis_points
        else f"{missing_fraction:.0%} di campioni mancanti"
    )
    warnings: list[str] = []
    if low_confidence:
        warnings.append(f"Analisi a bassa confidenza: {confidence_reason}.")

    threshold_times = {
        threshold: time_to_growth(times_h, growth_percent, threshold)
        for threshold in GROWTH_THRESHOLDS
    }

    max_value: float | None = None
    time_of_max_value: float | None = None
    max_growth_percent: float | None = None
    peak_index: int | None = None
    if finite_signal.any():
        candidate_indices = np.flatnonzero(finite_signal)
        peak_index = int(candidate_indices[np.argmax(analyzed_values[candidate_indices])])
        max_value = float(analyzed_values[peak_index])
        time_of_max_value = float(times_h[peak_index])
        max_growth_percent = float(growth_percent[peak_index])

    max_rate: float | None = None
    time_of_max_rate: float | None = None
    value_at_max_rate: float | None = None
    growth_at_max_rate: float | None = None
    max_rate_index: int | None = None
    rate_candidates = np.isfinite(growth_rate) & np.isfinite(growth_percent)
    rate_candidates &= growth_percent >= 0
    if time_of_max_value is not None:
        rate_candidates &= times_h <= time_of_max_value
    if rate_candidates.any():
        candidate_indices = np.flatnonzero(rate_candidates)
        max_rate_index = int(candidate_indices[np.argmax(growth_rate[candidate_indices])])
        if growth_rate[max_rate_index] > 0:
            max_rate = float(growth_rate[max_rate_index])
            time_of_max_rate = float(times_h[max_rate_index])
            value_at_max_rate = float(analyzed_values[max_rate_index])
            growth_at_max_rate = float(growth_percent[max_rate_index])

    max_specific_rate: float | None = None
    time_of_max_specific_rate: float | None = None
    specific_candidates = rate_candidates & np.isfinite(specific_growth_rate)
    if specific_candidates.any():
        candidate_indices = np.flatnonzero(specific_candidates)
        specific_index = int(
            candidate_indices[np.argmax(specific_growth_rate[candidate_indices])]
        )
        if specific_growth_rate[specific_index] > 0:
            max_specific_rate = float(specific_growth_rate[specific_index])
            time_of_max_specific_rate = float(times_h[specific_index])

    average_rates = {
        (start, end): _average_rate_between(
            start,
            end,
            threshold_times,
            times_h,
            growth_percent,
            analyzed_values,
        )
        for start, end in ((0, 25), (25, 50), (50, 75), (75, 100))
    }
    early_rate = average_rates[(25, 50)]
    late_rate = average_rates[(75, 100)]
    late_early_ratio = (
        late_rate / early_rate
        if early_rate is not None
        and late_rate is not None
        and abs(early_rate) > np.finfo(float).eps
        else None
    )

    lag_time: float | None = None
    plateau_time: float | None = None
    active_start: float | None = None
    active_end: float | None = None
    if max_rate is not None:
        lag_condition = np.isfinite(growth_rate) & (
            growth_rate >= max_rate * config.lag_rate_fraction
        )
        lag_time = _first_sustained_start(
            times_h, lag_condition, config.lag_persistence_minutes
        )

        plateau_condition = (
            np.isfinite(growth_rate)
            & np.isfinite(growth_percent)
            & (times_h >= (time_of_max_rate or 0.0))
            & (growth_percent >= config.plateau_min_growth_percent)
            & (np.abs(growth_rate) <= max_rate * config.plateau_rate_fraction)
        )
        plateau_time = _first_sustained_start(
            times_h,
            plateau_condition,
            config.plateau_persistence_minutes,
        )

        active_condition = np.isfinite(growth_rate) & (
            growth_rate >= max_rate * config.active_rate_fraction
        )
        active_start, active_end = _longest_true_run(times_h, active_condition)

    plateau_value = _interpolate_at(plateau_time, times_h, analyzed_values)
    plateau_growth = _interpolate_at(plateau_time, times_h, growth_percent)
    active_duration = (
        active_end - active_start
        if active_start is not None and active_end is not None
        else None
    )

    collapse_detected = False
    collapse_time: float | None = None
    loss_from_peak: float | None = None
    if (
        peak_index is not None
        and max_value is not None
        and max_growth_percent is not None
        and max_growth_percent >= config.collapse_min_peak_growth_percent
    ):
        loss_percent_curve = (max_value - analyzed_values) / max_value * 100.0
        collapse_condition = (
            np.isfinite(loss_percent_curve)
            & (np.arange(len(frame)) > peak_index)
            & (loss_percent_curve >= config.collapse_loss_percent)
        )
        collapse_time = _first_sustained_start(
            times_h,
            collapse_condition,
            config.collapse_persistence_minutes,
        )
        collapse_detected = collapse_time is not None
        if collapse_detected:
            after_collapse = (times_h >= collapse_time) & np.isfinite(analyzed_values)
            if after_collapse.any():
                minimum_after = float(np.min(analyzed_values[after_collapse]))
                loss_from_peak = (max_value - minimum_after) / max_value * 100.0

    dough_temperature = _numeric_array(frame, "temperature_dough_c")
    ambient_temperature = _numeric_array(frame, "temperature_ambient_c")
    dough_stats = _temperature_stats(dough_temperature)
    ambient_stats = _temperature_stats(ambient_temperature)
    delta_t = dough_temperature - ambient_temperature
    delta_stats = _temperature_stats(delta_t)
    time_of_delta_t_max: float | None = None
    if np.isfinite(delta_t).any():
        delta_indices = np.flatnonzero(np.isfinite(delta_t))
        delta_max_index = int(delta_indices[np.argmax(delta_t[delta_indices])])
        time_of_delta_t_max = float(times_h[delta_max_index])

    thermal_integrals = {
        reference: _trapezoidal_integral(times_h, dough_temperature, reference)
        for reference in config.thermal_references_c
    }

    inflection_time = time_of_max_rate
    inflection_value = value_at_max_rate
    inflection_growth = growth_at_max_rate
    growth_rate_at_inflection = max_rate

    metrics = FermentationMetrics(
        session_id=str(session_id),
        signal_field=signal_field,
        signal_unit=signal_unit,
        duration_h=float(times_h[-1]) if len(times_h) else None,
        initial_value=baseline_value,
        max_value=max_value,
        maximum_growth_percent=max_growth_percent,
        time_of_max_value_h=time_of_max_value,
        **{f"t{threshold}_h": threshold_times[threshold] for threshold in GROWTH_THRESHOLDS},
        lag_time_h=lag_time,
        max_growth_rate_value_h=max_rate,
        time_of_max_growth_rate_h=time_of_max_rate,
        value_at_max_growth_rate=value_at_max_rate,
        growth_percent_at_max_growth_rate=growth_at_max_rate,
        average_rate_0_25_value_h=average_rates[(0, 25)],
        average_rate_25_50_value_h=average_rates[(25, 50)],
        average_rate_50_75_value_h=average_rates[(50, 75)],
        average_rate_75_100_value_h=average_rates[(75, 100)],
        max_specific_growth_rate_h=max_specific_rate,
        time_of_max_specific_growth_rate_h=time_of_max_specific_rate,
        inflection_time_h=inflection_time,
        inflection_value=inflection_value,
        inflection_growth_percent=inflection_growth,
        growth_rate_at_inflection_value_h=growth_rate_at_inflection,
        plateau_start_time_h=plateau_time,
        plateau_value=plateau_value,
        plateau_growth_percent=plateau_growth,
        collapse_detected=collapse_detected,
        collapse_start_time_h=collapse_time,
        peak_before_collapse=max_value if collapse_detected else None,
        loss_from_peak_percent=loss_from_peak,
        active_phase_start_h=active_start,
        active_phase_end_h=active_end,
        active_phase_duration_h=active_duration,
        early_rate_value_h=early_rate,
        late_rate_value_h=late_rate,
        late_early_ratio=late_early_ratio,
        dough_temp_initial_c=dough_stats["initial"],
        dough_temp_final_c=dough_stats["final"],
        dough_temp_min_c=dough_stats["min"],
        dough_temp_max_c=dough_stats["max"],
        dough_temp_mean_c=dough_stats["mean"],
        dough_temp_median_c=dough_stats["median"],
        dough_temp_at_t25_c=_interpolate_at(threshold_times[25], times_h, dough_temperature),
        dough_temp_at_t50_c=_interpolate_at(threshold_times[50], times_h, dough_temperature),
        dough_temp_at_t75_c=_interpolate_at(threshold_times[75], times_h, dough_temperature),
        dough_temp_at_t100_c=_interpolate_at(threshold_times[100], times_h, dough_temperature),
        dough_temp_at_max_growth_rate_c=_interpolate_at(time_of_max_rate, times_h, dough_temperature),
        dough_temp_at_inflection_c=_interpolate_at(inflection_time, times_h, dough_temperature),
        dough_temp_at_plateau_c=_interpolate_at(plateau_time, times_h, dough_temperature),
        ambient_temp_min_c=ambient_stats["min"],
        ambient_temp_max_c=ambient_stats["max"],
        ambient_temp_mean_c=ambient_stats["mean"],
        ambient_temp_median_c=ambient_stats["median"],
        delta_t_initial_c=delta_stats["initial"],
        delta_t_min_c=delta_stats["min"],
        delta_t_max_c=delta_stats["max"],
        delta_t_mean_c=delta_stats["mean"],
        time_of_delta_t_max_h=time_of_delta_t_max,
        thermal_integral_0c_c_h=thermal_integrals.get(0.0),
        thermal_integral_4c_c_h=thermal_integrals.get(4.0),
        thermal_integral_20c_c_h=thermal_integrals.get(20.0),
    )

    events_h = {
        "lag": lag_time,
        "t25": threshold_times[25],
        "t50": threshold_times[50],
        "t75": threshold_times[75],
        "t100": threshold_times[100],
        "max_rate": time_of_max_rate,
        "inflection": inflection_time,
        "plateau": plateau_time,
        "collapse": collapse_time,
    }

    quality: dict[str, MetricQuality] = {}
    for threshold, event_time in threshold_times.items():
        quality[f"t{threshold}_h"] = _quality_for(
            event_time is not None,
            low_confidence=low_confidence,
            unavailable_reason=f"la crescita non raggiunge +{threshold}%",
            low_confidence_reason=confidence_reason,
        )
    for name, value, reason in (
        ("max_growth_rate_value_h", max_rate, "derivata non stimabile"),
        ("max_specific_growth_rate_h", max_specific_rate, "derivata specifica non stimabile"),
        ("lag_time_h", lag_time, "soglia di crescita non sostenuta"),
        ("inflection_time_h", inflection_time, "punto di massima pendenza non stimabile"),
        ("plateau_start_time_h", plateau_time, "plateau non osservato"),
        ("active_phase_duration_h", active_duration, "fase attiva non osservata"),
        ("late_early_ratio", late_early_ratio, "intervalli 25–50% e 75–100% incompleti"),
    ):
        quality[name] = _quality_for(
            value is not None,
            low_confidence=low_confidence,
            unavailable_reason=reason,
            low_confidence_reason=confidence_reason,
        )
    quality["collapse_detected"] = _quality_for(
        max_growth_percent is not None
        and max_growth_percent >= config.collapse_min_peak_growth_percent,
        low_confidence=low_confidence,
        unavailable_reason="picco insufficiente per valutare il collasso",
        low_confidence_reason=confidence_reason,
    )
    quality["thermal_integral"] = _quality_for(
        thermal_integrals.get(20.0) is not None,
        low_confidence=low_confidence,
        unavailable_reason="temperatura impasto insufficiente",
        low_confidence_reason=confidence_reason,
    )

    curves = pd.DataFrame(
        {
            "fingerprint_value": analyzed_values,
            "relative_growth": relative_growth,
            "fingerprint_growth_pct": growth_percent,
            "growth_rate_value_h": growth_rate,
            "specific_growth_rate_h": specific_growth_rate,
            "growth_acceleration_value_h2": growth_acceleration,
            "delta_t_c": delta_t,
        },
        index=frame.index,
    )
    curves.attrs.update(
        {
            "signal_field": signal_field,
            "signal_unit": signal_unit,
            "session_time": True,
        }
    )
    return FermentationFingerprint(
        metrics=metrics,
        curves=curves,
        events_h=events_h,
        quality=quality,
        warnings=tuple(warnings),
    )


def fingerprints_to_dataframe(
    fingerprints: Sequence[FermentationFingerprint],
) -> pd.DataFrame:
    """Return one raw numeric record per session for comparison or CSV export."""

    return pd.DataFrame([fingerprint.metrics.to_dict() for fingerprint in fingerprints])


def fingerprints_to_json(
    fingerprints: Sequence[FermentationFingerprint],
    *,
    include_quality: bool = True,
    indent: int = 2,
) -> str:
    """Serialize fingerprints without replacing numeric values with display text."""

    payload = [
        fingerprint.to_dict(include_quality=include_quality)
        for fingerprint in fingerprints
    ]
    if len(payload) == 1:
        return json.dumps(payload[0], ensure_ascii=False, indent=indent, allow_nan=False)
    return json.dumps(payload, ensure_ascii=False, indent=indent, allow_nan=False)
