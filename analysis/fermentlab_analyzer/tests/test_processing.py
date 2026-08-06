from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from fermentlab_analyzer.processing import analyze_session, summarize_session


class ProcessingTests(unittest.TestCase):
    def test_linear_growth_produces_expected_relative_rate(self) -> None:
        times = pd.date_range("2026-08-01T10:00:00Z", periods=61, freq="1min")
        frame = pd.DataFrame(
            {
                "_time": times,
                "volume_ml": np.linspace(1000.0, 1100.0, len(times)),
                "temperature_dough_c": 24.0,
            }
        )

        analysis = analyze_session(
            frame,
            smoothing_minutes=1,
            baseline_minutes=1,
            rate_window_minutes=30,
        )
        summary = summarize_session(analysis)

        self.assertEqual(summary.signal_field, "volume_ml")
        self.assertAlmostEqual(summary.baseline_value, 1000.8333, places=3)
        self.assertAlmostEqual(summary.current_growth_pct, 9.9084, places=3)
        self.assertAlmostEqual(summary.current_growth_rate_pct_h, 9.9917, places=3)
        self.assertEqual(summary.measurements, 61)

    def test_invalid_volume_is_ignored_by_smoothing(self) -> None:
        frame = pd.DataFrame(
            {
                "_time": pd.date_range(
                    "2026-08-01T10:00:00Z", periods=4, freq="1min"
                ),
                "volume_ml": [500.0, -1.0, 510.0, 520.0],
            }
        )

        analysis = analyze_session(frame, smoothing_minutes=5, baseline_minutes=1)

        self.assertEqual(analysis["volume_ml"].iloc[1], -1.0)
        self.assertEqual(analysis["signal_smooth"].iloc[1], 500.0)

    def test_height_is_used_when_volume_is_not_available(self) -> None:
        frame = pd.DataFrame(
            {
                "_time": pd.date_range(
                    "2026-08-01T10:00:00Z", periods=4, freq="1min"
                ),
                "dough_height_mm": [50.0, 51.0, 52.0, 53.0],
            }
        )

        analysis = analyze_session(frame, smoothing_minutes=1, baseline_minutes=1)
        summary = summarize_session(analysis)

        self.assertEqual(summary.signal_field, "dough_height_mm")
        self.assertEqual(summary.signal_unit, "mm")
        self.assertGreater(summary.current_growth_pct, 0)

    def test_baseline_offset_ignores_initial_settling(self) -> None:
        frame = pd.DataFrame(
            {
                "_time": pd.date_range(
                    "2026-08-01T10:00:00Z", periods=5, freq="1min"
                ),
                "dough_height_mm": [100.0, 90.0, 50.0, 50.0, 55.0],
            }
        )

        analysis = analyze_session(
            frame,
            smoothing_minutes=1,
            baseline_offset_minutes=2,
            baseline_minutes=1,
        )

        self.assertTrue(np.isnan(analysis["growth_pct"].iloc[0]))
        self.assertAlmostEqual(analysis.attrs["baseline_value"], 50.0)
        self.assertAlmostEqual(analysis["growth_pct"].iloc[-1], 10.0)

    def test_missing_required_columns_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "volume o altezza"):
            analyze_session(pd.DataFrame({"_time": ["2026-08-01T10:00:00Z"]}))


if __name__ == "__main__":
    unittest.main()
