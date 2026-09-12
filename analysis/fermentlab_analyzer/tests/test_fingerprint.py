from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from fermentlab_analyzer.fingerprint import (
    FermentationAnalysisConfig,
    compute_fermentation_fingerprint,
    fingerprints_to_dataframe,
    fingerprints_to_json,
    time_to_growth,
)
from fermentlab_analyzer.processing import analyze_session


def analyzed_curve(
    times_h: np.ndarray,
    values: np.ndarray,
    *,
    dough_temperature: np.ndarray | float = 24.0,
    ambient_temperature: np.ndarray | float = 22.0,
    despike: bool = False,
) -> pd.DataFrame:
    timestamps = pd.Timestamp("2026-08-01T10:00:00Z") + pd.to_timedelta(
        times_h, unit="h"
    )
    frame = pd.DataFrame(
        {
            "_time": timestamps,
            "volume_ml": values,
            "temperature_dough_c": dough_temperature,
            "temperature_ambient_c": ambient_temperature,
        }
    )
    return analyze_session(
        frame,
        smoothing_minutes=1,
        post_smoothing_minutes=0,
        despike_window_minutes=15 if despike else 0,
        despike_sigma=3.0 if despike else 0.0,
        baseline_minutes=1,
        rate_window_minutes=30,
        acceleration_window_minutes=60,
    )


class FingerprintTests(unittest.TestCase):
    def test_time_to_growth_interpolates_between_samples(self) -> None:
        times = [0.0, 1.0, 2.0]
        growth = [0.0, 20.0, 60.0]

        self.assertAlmostEqual(time_to_growth(times, growth, 25.0), 1.125)
        self.assertAlmostEqual(time_to_growth(times, growth, 50.0), 1.75)

    def test_linear_curve_extracts_thresholds_and_growth_rate(self) -> None:
        times_h = np.linspace(0.0, 4.0, 241)
        values = 100.0 + 30.0 * times_h
        analysis = analyzed_curve(times_h, values)

        fingerprint = compute_fermentation_fingerprint(analysis, "linear")
        metrics = fingerprint.metrics

        self.assertAlmostEqual(metrics.max_growth_rate_value_h, 30.0, delta=0.5)
        self.assertAlmostEqual(metrics.t25_h, 0.84, delta=0.04)
        self.assertAlmostEqual(metrics.t50_h, 1.68, delta=0.04)
        self.assertAlmostEqual(metrics.t100_h, 3.35, delta=0.05)
        self.assertEqual(metrics.signal_unit, "ml")

    def test_specific_growth_rate_on_exponential_curve(self) -> None:
        times_h = np.linspace(0.0, 5.0, 301)
        values = 100.0 * np.exp(0.2 * times_h)
        analysis = analyzed_curve(times_h, values)

        fingerprint = compute_fermentation_fingerprint(analysis, "exponential")

        self.assertAlmostEqual(
            fingerprint.metrics.max_specific_growth_rate_h,
            0.2,
            delta=0.015,
        )

    def test_thermal_integral_supports_irregular_sampling(self) -> None:
        times_h = np.array([0.0, 1.0, 3.0])
        values = np.array([100.0, 110.0, 130.0])
        dough_temperature = np.array([20.0, 22.0, 24.0])
        analysis = analyzed_curve(
            times_h,
            values,
            dough_temperature=dough_temperature,
        )
        config = FermentationAnalysisConfig(
            minimum_derivative_points=3,
            minimum_analysis_points=3,
        )

        fingerprint = compute_fermentation_fingerprint(
            analysis, "irregular", config
        )

        self.assertAlmostEqual(
            fingerprint.metrics.thermal_integral_20c_c_h,
            7.0,
            places=6,
        )
        self.assertAlmostEqual(
            fingerprint.metrics.thermal_integral_0c_c_h,
            67.0,
            places=6,
        )

    def test_plateau_is_detected_only_after_persistent_low_rate(self) -> None:
        times_h = np.linspace(0.0, 8.0, 97)
        values = 100.0 + 20.0 * np.minimum(times_h, 5.0)
        analysis = analyzed_curve(times_h, values)

        fingerprint = compute_fermentation_fingerprint(analysis, "plateau")

        self.assertIsNotNone(fingerprint.metrics.plateau_start_time_h)
        self.assertGreater(fingerprint.metrics.plateau_start_time_h, 4.7)
        self.assertLess(fingerprint.metrics.plateau_start_time_h, 5.8)
        self.assertEqual(
            fingerprint.quality["plateau_start_time_h"].status,
            "valid",
        )

    def test_persistent_loss_after_peak_is_detected_as_collapse(self) -> None:
        times_h = np.linspace(0.0, 8.0, 97)
        values = np.piecewise(
            times_h,
            [times_h <= 5.0, (times_h > 5.0) & (times_h <= 6.0), times_h > 6.0],
            [
                lambda x: 100.0 + 20.0 * x,
                lambda x: 200.0 - 20.0 * (x - 5.0),
                180.0,
            ],
        )
        analysis = analyzed_curve(times_h, values)

        fingerprint = compute_fermentation_fingerprint(analysis, "collapse")

        self.assertTrue(fingerprint.metrics.collapse_detected)
        self.assertIsNotNone(fingerprint.metrics.collapse_start_time_h)
        self.assertGreaterEqual(fingerprint.metrics.loss_from_peak_percent, 9.0)

    def test_session_without_doubling_returns_unavailable(self) -> None:
        times_h = np.linspace(0.0, 4.0, 121)
        values = 100.0 + 12.0 * times_h
        analysis = analyzed_curve(times_h, values)

        fingerprint = compute_fermentation_fingerprint(analysis, "short")

        self.assertIsNone(fingerprint.metrics.t100_h)
        self.assertEqual(fingerprint.quality["t100_h"].status, "unavailable")

    def test_noise_and_nan_do_not_mutate_input_or_destroy_rate(self) -> None:
        rng = np.random.default_rng(42)
        times_h = np.linspace(0.0, 4.0, 241)
        values = 100.0 + 25.0 * times_h + rng.normal(0.0, 0.4, len(times_h))
        values[80] += 35.0
        values[120:124] = np.nan
        raw_values = values.copy()
        analysis = analyzed_curve(times_h, values, despike=True)
        analysis_before = analysis.copy(deep=True)

        fingerprint = compute_fermentation_fingerprint(analysis, "noisy")

        np.testing.assert_allclose(values, raw_values, equal_nan=True)
        pd.testing.assert_frame_equal(analysis, analysis_before)
        self.assertAlmostEqual(
            fingerprint.metrics.max_growth_rate_value_h,
            25.0,
            delta=4.0,
        )
        self.assertTrue(np.isfinite(fingerprint.curves["growth_rate_value_h"]).any())

    def test_export_keeps_numeric_values_and_missing_values(self) -> None:
        times_h = np.linspace(0.0, 2.0, 61)
        analysis = analyzed_curve(times_h, 100.0 + 20.0 * times_h)
        fingerprint = compute_fermentation_fingerprint(analysis, "export")

        frame = fingerprints_to_dataframe([fingerprint])
        payload = fingerprints_to_json([fingerprint])

        self.assertEqual(frame.loc[0, "session_id"], "export")
        self.assertIsInstance(frame.loc[0, "max_value"], float)
        self.assertIn('"t100_h": null', payload)
        self.assertIn('"quality"', payload)


if __name__ == "__main__":
    unittest.main()
