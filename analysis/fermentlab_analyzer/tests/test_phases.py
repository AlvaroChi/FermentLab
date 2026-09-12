from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from fermentlab_analyzer.phases import (
    PHASE_SIDECAR_SCHEMA,
    PhaseAnnotation,
    analyze_protocol_phases,
    build_phase_definitions,
    build_thermal_diagnostic,
    detect_thermal_phase_proposal,
    load_phase_annotation,
    phase_annotation_path,
    phase_results_to_dataframe,
    save_phase_annotation,
)
from fermentlab_analyzer.processing import analyze_session


def exponential_analysis(duration_h: float = 4.0, rate_h: float = 0.2) -> pd.DataFrame:
    times_h = np.linspace(0.0, duration_h, int(duration_h * 60) + 1)
    timestamps = pd.Timestamp("2026-08-01T10:00:00Z") + pd.to_timedelta(
        times_h, unit="h"
    )
    return analyze_session(
        pd.DataFrame(
            {
                "_time": timestamps,
                "elapsed_ms": times_h * 3_600_000.0,
                "volume_ml": 100.0 * np.exp(rate_h * times_h),
                "temperature_dough_c": np.linspace(5.0, 22.0, len(times_h)),
                "temperature_ambient_c": np.linspace(4.0, 21.0, len(times_h)),
            }
        ),
        smoothing_minutes=1,
        baseline_minutes=1,
        rate_window_minutes=30,
    )


def fridge_analysis(*, dough_reaches_plateau: bool) -> pd.DataFrame:
    analysis = exponential_analysis(duration_h=8.0)
    elapsed = analysis["elapsed_hours"].to_numpy(dtype=float)
    analysis["temperature_ambient_c"] = np.piecewise(
        elapsed,
        [elapsed < 1.0, (elapsed >= 1.0) & (elapsed < 5.0), elapsed >= 5.0],
        [
            lambda values: 18.0 - 14.0 * values,
            4.0,
            lambda values: np.minimum(28.0, 4.0 + 120.0 * (values - 5.0)),
        ],
    )
    if dough_reaches_plateau:
        analysis["temperature_dough_c"] = np.piecewise(
            elapsed,
            [elapsed < 3.0, (elapsed >= 3.0) & (elapsed < 5.0), elapsed >= 5.0],
            [
                lambda values: 18.0 - (13.0 / 3.0) * values,
                5.0,
                lambda values: np.minimum(28.0, 5.0 + 23.0 * (values - 5.0)),
            ],
        )
    else:
        analysis["temperature_dough_c"] = np.where(
            elapsed < 5.0,
            np.maximum(5.0, 18.0 - (13.0 / 3.0) * elapsed),
            5.0 + 3.0 * (elapsed - 5.0),
        )
    return analysis


class PhaseAnalysisTests(unittest.TestCase):
    def test_legacy_fridge_protocol_keeps_settling_open(self) -> None:
        annotation = PhaseAnnotation("session-a", "fridge_to_ambient", 2.0)

        phases = build_phase_definitions(annotation, 4.0)

        self.assertEqual([phase.key for phase in phases], ["cold", "settling"])
        self.assertEqual(phases[0].start_h, 0.0)
        self.assertEqual(phases[0].end_h, 2.0)
        self.assertEqual(phases[1].start_h, 2.0)
        self.assertEqual(phases[1].end_h, 4.0)
        self.assertFalse(phases[1].complete)

    def test_cooling_boundary_builds_four_thermal_phases(self) -> None:
        annotation = PhaseAnnotation(
            "session-a",
            "fridge_to_ambient",
            fridge_exit_h=4.0,
            warm_stable_h=5.0,
            cold_stable_h=1.0,
        )

        phases = build_phase_definitions(annotation, 6.0)

        self.assertEqual(
            [phase.key for phase in phases],
            ["cooling", "cold", "settling", "warm_stable"],
        )
        self.assertEqual(
            [(phase.start_h, phase.end_h) for phase in phases],
            [(0.0, 1.0), (1.0, 4.0), (4.0, 5.0), (5.0, 6.0)],
        )

    def test_fridge_protocol_builds_three_thermal_phases(self) -> None:
        annotation = PhaseAnnotation(
            "session-a",
            "fridge_to_ambient",
            fridge_exit_h=2.0,
            warm_stable_h=3.5,
        )

        phases = build_phase_definitions(annotation, 5.0)

        self.assertEqual(
            [phase.key for phase in phases],
            ["cold", "settling", "warm_stable"],
        )
        self.assertEqual(
            [(phase.start_h, phase.end_h) for phase in phases],
            [(0.0, 2.0), (2.0, 3.5), (3.5, 5.0)],
        )

    def test_unfinished_settling_does_not_invent_a_stable_phase(self) -> None:
        annotation = PhaseAnnotation(
            "session-a",
            "fridge_to_ambient",
            fridge_exit_h=2.0,
            warm_stable_h=8.0,
        )

        phases = build_phase_definitions(annotation, 5.0)

        self.assertEqual([phase.key for phase in phases], ["cold", "settling"])
        self.assertFalse(phases[-1].complete)
        self.assertEqual(phases[-1].end_h, 5.0)

    def test_exit_after_observation_is_an_incomplete_cold_phase(self) -> None:
        annotation = PhaseAnnotation("session-a", "fridge_to_ambient", 48.0)

        phases = build_phase_definitions(annotation, 24.0)

        self.assertEqual(len(phases), 1)
        self.assertEqual(phases[0].key, "cold")
        self.assertFalse(phases[0].complete)
        self.assertEqual(phases[0].duration_h, 24.0)

    def test_phase_metrics_restart_threshold_clock_at_each_boundary(self) -> None:
        analysis = exponential_analysis(duration_h=6.0)
        original_growth = analysis["growth_pct"].copy()
        original_baseline = analysis.attrs["baseline_value"]
        annotation = PhaseAnnotation(
            "session-a",
            "fridge_to_ambient",
            fridge_exit_h=2.0,
            warm_stable_h=4.0,
        )

        results = analyze_protocol_phases(
            analysis,
            "session-a",
            annotation,
            baseline_minutes=1.0,
        )

        self.assertEqual(len(results), 3)
        for result in results:
            self.assertAlmostEqual(result.fingerprint.metrics.t25_h, 1.12, delta=0.06)
            self.assertIsNone(result.fingerprint.metrics.t50_h)
            self.assertAlmostEqual(
                result.mean_specific_growth_rate_h,
                0.2,
                delta=0.01,
            )
            self.assertAlmostEqual(
                result.estimated_doubling_time_h,
                np.log(2.0) / 0.2,
                delta=0.15,
            )
            self.assertGreater(result.observed_growth_percent, 45.0)
        pd.testing.assert_series_equal(analysis["growth_pct"], original_growth)
        self.assertEqual(analysis.attrs["baseline_value"], original_baseline)

    def test_phase_export_keeps_numeric_values(self) -> None:
        results = analyze_protocol_phases(
            exponential_analysis(),
            "session-a",
            PhaseAnnotation("session-a", "ambient"),
        )

        frame = phase_results_to_dataframe(results)

        self.assertEqual(frame.loc[0, "phase_key"], "ambient")
        self.assertTrue(np.issubdtype(frame["observed_growth_percent"].dtype, np.number))

    def test_thermal_diagnostic_exposes_a_real_slope_change(self) -> None:
        analysis = exponential_analysis()
        elapsed = analysis["elapsed_hours"].to_numpy(dtype=float)
        ambient = np.where(
            elapsed <= 2.0,
            20.0 - 2.0 * elapsed,
            16.0 + 5.0 * (elapsed - 2.0),
        )
        analysis["temperature_ambient_c"] = ambient
        original = analysis["temperature_ambient_c"].copy()

        diagnostic = build_thermal_diagnostic(
            analysis,
            temperature_smoothing_minutes=5.0,
            slope_smoothing_minutes=5.0,
        )

        before = diagnostic.loc[
            diagnostic["elapsed_hours"].between(0.5, 1.5),
            "ambient_temp_slope_c_h",
        ].median()
        after = diagnostic.loc[
            diagnostic["elapsed_hours"].between(2.5, 3.5),
            "ambient_temp_slope_c_h",
        ].median()
        self.assertAlmostEqual(before, -2.0, delta=0.2)
        self.assertAlmostEqual(after, 5.0, delta=0.2)
        expected_gap = (
            diagnostic["dough_temp_slope_c_h"]
            - diagnostic["ambient_temp_slope_c_h"]
        ).abs()
        pd.testing.assert_series_equal(
            diagnostic["thermal_slope_gap_c_h"],
            expected_gap,
            check_names=False,
        )
        pd.testing.assert_series_equal(analysis["temperature_ambient_c"], original)

    def test_thermal_diagnostic_requires_at_least_one_temperature_curve(self) -> None:
        analysis = exponential_analysis().drop(
            columns=["temperature_dough_c", "temperature_ambient_c"]
        )

        with self.assertRaisesRegex(ValueError, "curve di temperatura"):
            build_thermal_diagnostic(analysis)

    def test_detector_proposes_cooling_cold_and_open_settling(self) -> None:
        analysis = fridge_analysis(dough_reaches_plateau=False)
        original = analysis.copy(deep=True)

        proposal = detect_thermal_phase_proposal(analysis, "session-fridge")

        self.assertIsNotNone(proposal.annotation)
        annotation = proposal.annotation
        self.assertEqual(annotation.protocol, "fridge_to_ambient")
        self.assertAlmostEqual(annotation.cold_stable_h, 3.0, delta=0.25)
        self.assertAlmostEqual(annotation.fridge_exit_h, 5.0, delta=0.2)
        self.assertIsNone(annotation.warm_stable_h)
        self.assertGreater(proposal.confidence, 0.6)
        self.assertEqual(
            [phase.key for phase in build_phase_definitions(annotation, 8.0)],
            ["cooling", "cold", "settling"],
        )
        pd.testing.assert_frame_equal(analysis, original)

    def test_detector_requires_dough_plateau_for_warm_stable_phase(self) -> None:
        proposal = detect_thermal_phase_proposal(
            fridge_analysis(dough_reaches_plateau=True),
            "session-fridge",
        )

        self.assertIsNotNone(proposal.annotation)
        self.assertIsNotNone(proposal.annotation.warm_stable_h)
        self.assertGreater(proposal.annotation.warm_stable_h, 5.5)

    def test_detector_is_invariant_to_constant_sensor_offsets(self) -> None:
        calibrated = fridge_analysis(dough_reaches_plateau=True)
        offset = calibrated.copy(deep=True)
        offset["temperature_ambient_c"] += 11.0
        offset["temperature_dough_c"] -= 7.0

        calibrated_proposal = detect_thermal_phase_proposal(
            calibrated,
            "session-calibrated",
        )
        offset_proposal = detect_thermal_phase_proposal(
            offset,
            "session-offset",
        )

        self.assertIsNotNone(calibrated_proposal.annotation)
        self.assertIsNotNone(offset_proposal.annotation)
        self.assertAlmostEqual(
            offset_proposal.annotation.fridge_exit_h,
            calibrated_proposal.annotation.fridge_exit_h,
            delta=0.05,
        )
        self.assertAlmostEqual(
            offset_proposal.annotation.cold_stable_h,
            calibrated_proposal.annotation.cold_stable_h,
            delta=0.05,
        )
        self.assertAlmostEqual(
            offset_proposal.annotation.warm_stable_h,
            calibrated_proposal.annotation.warm_stable_h,
            delta=0.05,
        )

    def test_detector_leaves_ambiguous_session_unclassified(self) -> None:
        analysis = exponential_analysis()
        analysis["temperature_ambient_c"] = 22.0
        analysis["temperature_dough_c"] = 22.0

        proposal = detect_thermal_phase_proposal(analysis, "session-ambient")

        self.assertIsNone(proposal.annotation)
        self.assertEqual(proposal.confidence, 0.0)

    def test_sidecar_save_is_atomic_and_preserves_previous_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            first = PhaseAnnotation("../../session-a", "ambient")
            path = save_phase_annotation(first, directory)

            self.assertEqual(path.parent, directory)
            self.assertNotIn("session-a", path.name)
            first_loaded = load_phase_annotation(first.session_id, directory)
            self.assertIsNotNone(first_loaded)
            self.assertEqual(first_loaded.session_id, first.session_id)
            self.assertEqual(first_loaded.protocol, "ambient")
            self.assertIsNotNone(first_loaded.updated_at)

            second = PhaseAnnotation(
                first.session_id,
                "fridge_to_ambient",
                fridge_exit_h=24.0,
                warm_stable_h=30.0,
                cold_stable_h=2.0,
            )
            save_phase_annotation(second, directory)
            loaded = load_phase_annotation(first.session_id, directory)

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.protocol, "fridge_to_ambient")
            self.assertEqual(loaded.fridge_exit_h, 24.0)
            self.assertEqual(loaded.warm_stable_h, 30.0)
            self.assertEqual(loaded.cold_stable_h, 2.0)
            backup = path.with_suffix(".json.bak")
            self.assertTrue(backup.exists())
            backup_payload = json.loads(backup.read_text(encoding="utf-8"))
            self.assertEqual(backup_payload["schema"], PHASE_SIDECAR_SCHEMA)
            self.assertEqual(backup_payload["protocol"], "ambient")
            self.assertFalse(list(directory.glob("*.tmp")))
            self.assertEqual(path, phase_annotation_path(first.session_id, directory))

    def test_v1_sidecar_loads_without_modification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            session_id = "legacy-session"
            path = phase_annotation_path(session_id, directory)
            path.write_text(
                json.dumps(
                    {
                        "schema": "fermentlab.phase-annotation.v1",
                        "session_id": session_id,
                        "protocol": "fridge_to_ambient",
                        "fridge_exit_h": 24.0,
                        "updated_at": "2026-08-01T12:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_phase_annotation(session_id, directory)

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.fridge_exit_h, 24.0)
            self.assertIsNone(loaded.warm_stable_h)
            self.assertIsNone(loaded.cold_stable_h)

    def test_v2_sidecar_loads_without_cooling_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            session_id = "v2-session"
            phase_annotation_path(session_id, directory).write_text(
                json.dumps(
                    {
                        "schema": "fermentlab.phase-annotation.v2",
                        "session_id": session_id,
                        "protocol": "fridge_to_ambient",
                        "fridge_exit_h": 24.0,
                        "warm_stable_h": 30.0,
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_phase_annotation(session_id, directory)

            self.assertIsNotNone(loaded)
            self.assertIsNone(loaded.cold_stable_h)

    def test_stabilization_must_follow_fridge_exit(self) -> None:
        annotation = PhaseAnnotation(
            "session-a",
            "fridge_to_ambient",
            fridge_exit_h=24.0,
            warm_stable_h=23.0,
        )

        with self.assertRaisesRegex(ValueError, "dopo l'uscita"):
            annotation.validate()

    def test_cold_stabilization_must_precede_fridge_exit(self) -> None:
        annotation = PhaseAnnotation(
            "session-a",
            "fridge_to_ambient",
            fridge_exit_h=24.0,
            cold_stable_h=25.0,
        )

        with self.assertRaisesRegex(ValueError, "precedere"):
            annotation.validate()


if __name__ == "__main__":
    unittest.main()
