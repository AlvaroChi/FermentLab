from __future__ import annotations

from pathlib import Path
import sys
import unittest

import pandas as pd


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from fermentlab_analyzer.influx import (
    build_merged_points,
    classify_session_summary,
    preview_merge_records,
    summarize_session_records,
)


class InfluxHelpersTests(unittest.TestCase):
    def test_summarize_session_records_reports_window_and_counts(self) -> None:
        frame = pd.DataFrame(
            {
                "_time": pd.to_datetime(
                    [
                        "2026-08-01T10:00:00Z",
                        "2026-08-01T10:00:00Z",
                        "2026-08-01T10:05:00Z",
                    ],
                    utc=True,
                ),
                "_measurement": [
                    "fermentation_measurement",
                    "session_start",
                    "fermentation_measurement",
                ],
                "_field": ["elapsed_ms", "recipe", "temperature_dough_c"],
                "session_id": ["session-a", "session-a", "session-a"],
            }
        )

        summary = summarize_session_records(frame)

        self.assertEqual(summary["session_id"], "session-a")
        self.assertEqual(summary["record_count"], 3)
        self.assertEqual(summary["sample_count"], 2)
        self.assertEqual(summary["measurement_count"], 2)
        self.assertEqual(summary["field_count"], 3)
        self.assertEqual(summary["measurements"], ["fermentation_measurement", "session_start"])
        self.assertEqual(summary["fields"], ["elapsed_ms", "recipe", "temperature_dough_c"])
        self.assertAlmostEqual(summary["duration_hours"], 5 / 60, places=5)

    def test_build_merged_points_rewrites_session_id_and_keeps_tags(self) -> None:
        frame = pd.DataFrame(
            {
                "_time": pd.to_datetime(["2026-08-01T10:00:00Z"], utc=True),
                "_measurement": ["fermentation_measurement"],
                "_field": ["volume_ml"],
                "_value": [1250.5],
                "session_id": ["source-session"],
                "device_id": ["device-01"],
                "schema": ["v1"],
            }
        )

        points = build_merged_points(frame, "target-session")

        self.assertEqual(len(points), 1)
        line_protocol = points[0].to_line_protocol()
        self.assertIn("fermentation_measurement", line_protocol)
        self.assertIn("session_id=target-session", line_protocol)
        self.assertIn("device_id=device-01", line_protocol)
        self.assertIn("schema=v1", line_protocol)
        self.assertIn("volume_ml=1250.5", line_protocol)
        self.assertNotIn("source-session", line_protocol)

    def test_preview_merge_records_reports_overlap_and_new_points(self) -> None:
        source = pd.DataFrame(
            {
                "_time": pd.to_datetime(
                    ["2026-08-01T10:00:00Z", "2026-08-01T10:05:00Z"], utc=True
                ),
                "_measurement": ["fermentation_measurement", "fermentation_measurement"],
                "_field": ["volume_ml", "volume_ml"],
                "_value": [1000.0, 1020.0],
                "session_id": ["source", "source"],
                "device_id": ["dev-1", "dev-1"],
            }
        )
        target = pd.DataFrame(
            {
                "_time": pd.to_datetime(
                    ["2026-08-01T10:05:00Z", "2026-08-01T10:10:00Z"], utc=True
                ),
                "_measurement": ["fermentation_measurement", "fermentation_measurement"],
                "_field": ["volume_ml", "volume_ml"],
                "_value": [1020.0, 1040.0],
                "session_id": ["target", "target"],
                "device_id": ["dev-1", "dev-1"],
            }
        )

        preview = preview_merge_records(source, target)

        self.assertEqual(preview["source_record_count"], 2)
        self.assertEqual(preview["target_record_count"], 2)
        self.assertEqual(preview["overlap_point_count"], 1)
        self.assertEqual(preview["overlap_timestamp_count"], 1)
        self.assertEqual(preview["new_point_count"], 1)
        self.assertFalse(preview["would_create_target"])

    def test_classify_session_summary_marks_test_and_suspicious(self) -> None:
        summary = {
            "session_id": "debug-test-run",
            "record_count": 8,
            "sample_count": 3,
            "duration_hours": 0.1,
            "field_count": 1,
        }

        classified = classify_session_summary(summary)

        self.assertEqual(classified["kind"], "test")
        self.assertTrue(classified["is_test"])
        self.assertTrue(classified["is_suspicious"])
        self.assertIn("pochi record", classified["reasons"])
        self.assertIn("session_id suggerisce test", classified["reasons"])


if __name__ == "__main__":
    unittest.main()