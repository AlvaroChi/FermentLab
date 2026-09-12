"""Non-destructive protocol-phase analysis and local sidecar annotations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
from typing import Literal, Sequence
import uuid

import numpy as np
import pandas as pd

from .fingerprint import (
    FermentationAnalysisConfig,
    FermentationFingerprint,
    compute_fermentation_fingerprint,
)


PhaseProtocol = Literal["ambient", "fridge_to_ambient"]
PHASE_SIDECAR_SCHEMA = "fermentlab.phase-annotation.v3"
LEGACY_PHASE_SIDECAR_SCHEMAS = {
    "fermentlab.phase-annotation.v1",
    "fermentlab.phase-annotation.v2",
}


@dataclass(frozen=True)
class PhaseAnnotation:
    """User-confirmed protocol boundaries for one immutable session id."""

    session_id: str
    protocol: PhaseProtocol
    fridge_exit_h: float | None = None
    warm_stable_h: float | None = None
    cold_stable_h: float | None = None
    updated_at: str | None = None

    def validate(self) -> None:
        if not self.session_id.strip():
            raise ValueError("Il session_id della definizione fasi è vuoto.")
        if self.protocol not in {"ambient", "fridge_to_ambient"}:
            raise ValueError("Protocollo di fase non riconosciuto.")
        if self.protocol == "fridge_to_ambient":
            if self.fridge_exit_h is None:
                raise ValueError("Indica l'ora di uscita dal frigo.")
            if not math.isfinite(float(self.fridge_exit_h)) or float(
                self.fridge_exit_h
            ) <= 0:
                raise ValueError("L'uscita dal frigo deve essere maggiore di zero.")
            if self.warm_stable_h is not None:
                if not math.isfinite(float(self.warm_stable_h)):
                    raise ValueError("L'ora di stabilizzazione non è valida.")
                if float(self.warm_stable_h) <= float(self.fridge_exit_h):
                    raise ValueError(
                        "La stabilizzazione deve avvenire dopo l'uscita dal frigo."
                    )
            if self.cold_stable_h is not None:
                if not math.isfinite(float(self.cold_stable_h)) or float(
                    self.cold_stable_h
                ) <= 0:
                    raise ValueError(
                        "La stabilizzazione al freddo deve essere maggiore di zero."
                    )
                if float(self.cold_stable_h) >= float(self.fridge_exit_h):
                    raise ValueError(
                        "La stabilizzazione al freddo deve precedere l'uscita dal frigo."
                    )

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "schema": PHASE_SIDECAR_SCHEMA,
            "session_id": self.session_id,
            "protocol": self.protocol,
            "fridge_exit_h": self.fridge_exit_h,
            "warm_stable_h": self.warm_stable_h,
            "cold_stable_h": self.cold_stable_h,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "PhaseAnnotation":
        if payload.get("schema") not in {
            PHASE_SIDECAR_SCHEMA,
            *LEGACY_PHASE_SIDECAR_SCHEMAS,
        }:
            raise ValueError("Schema del sidecar fasi non riconosciuto.")
        annotation = cls(
            session_id=str(payload.get("session_id") or ""),
            protocol=str(payload.get("protocol") or ""),  # type: ignore[arg-type]
            fridge_exit_h=(
                float(payload["fridge_exit_h"])
                if payload.get("fridge_exit_h") is not None
                else None
            ),
            warm_stable_h=(
                float(payload["warm_stable_h"])
                if payload.get("warm_stable_h") is not None
                else None
            ),
            cold_stable_h=(
                float(payload["cold_stable_h"])
                if payload.get("cold_stable_h") is not None
                else None
            ),
            updated_at=(
                str(payload["updated_at"])
                if payload.get("updated_at") is not None
                else None
            ),
        )
        annotation.validate()
        return annotation


@dataclass(frozen=True)
class PhaseDefinition:
    """One protocol interval expressed on the original session clock."""

    key: str
    label: str
    start_h: float
    end_h: float
    complete: bool = True

    @property
    def duration_h(self) -> float:
        return max(0.0, float(self.end_h) - float(self.start_h))


@dataclass(frozen=True)
class PhaseAnalysis:
    """Local fingerprint plus descriptive kinetics for one protocol phase."""

    definition: PhaseDefinition
    fingerprint: FermentationFingerprint
    final_value: float | None
    observed_growth_percent: float | None
    mean_growth_rate_value_h: float | None
    mean_specific_growth_rate_h: float | None
    estimated_doubling_time_h: float | None

    def to_dict(self) -> dict[str, object]:
        metrics = self.fingerprint.metrics
        return {
            "session_id": metrics.session_id,
            "phase_key": self.definition.key,
            "phase_label": self.definition.label,
            "phase_start_h": self.definition.start_h,
            "phase_end_h": self.definition.end_h,
            "phase_duration_h": self.definition.duration_h,
            "phase_complete": self.definition.complete,
            "signal_field": metrics.signal_field,
            "signal_unit": metrics.signal_unit,
            "initial_value": metrics.initial_value,
            "final_value": self.final_value,
            "observed_growth_percent": self.observed_growth_percent,
            "mean_growth_rate_value_h": self.mean_growth_rate_value_h,
            "mean_specific_growth_rate_h": self.mean_specific_growth_rate_h,
            "estimated_doubling_time_h": self.estimated_doubling_time_h,
            "t25_h": metrics.t25_h,
            "t50_h": metrics.t50_h,
            "t100_h": metrics.t100_h,
            "max_growth_rate_value_h": metrics.max_growth_rate_value_h,
            "max_specific_growth_rate_h": metrics.max_specific_growth_rate_h,
            "dough_temp_initial_c": metrics.dough_temp_initial_c,
            "dough_temp_final_c": metrics.dough_temp_final_c,
            "dough_temp_mean_c": metrics.dough_temp_mean_c,
            "ambient_temp_mean_c": metrics.ambient_temp_mean_c,
            "thermal_integral_20c_c_h": metrics.thermal_integral_20c_c_h,
            "warnings": list(self.fingerprint.warnings),
        }


@dataclass(frozen=True)
class ThermalPhaseProposal:
    """Read-only phase proposal inferred from temperature curves."""

    annotation: PhaseAnnotation | None
    confidence: float
    notes: tuple[str, ...]


def default_phase_sidecar_dir() -> Path:
    """Return the local-only metadata directory; never points at InfluxDB."""

    configured = os.getenv("FERMENTLAB_SIDECAR_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".fermentlab" / "session_phases"


def phase_annotation_path(session_id: str, directory: Path | None = None) -> Path:
    if not session_id.strip():
        raise ValueError("Il session_id è vuoto.")
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return (directory or default_phase_sidecar_dir()) / f"{digest}.json"


def load_phase_annotation(
    session_id: str, directory: Path | None = None
) -> PhaseAnnotation | None:
    path = phase_annotation_path(session_id, directory)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Sidecar fasi non leggibile: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("Il sidecar fasi non contiene un oggetto JSON.")
    annotation = PhaseAnnotation.from_dict(payload)
    if annotation.session_id != session_id:
        raise ValueError("Il sidecar fasi appartiene a una sessione diversa.")
    return annotation


def save_phase_annotation(
    annotation: PhaseAnnotation, directory: Path | None = None
) -> Path:
    """Atomically save one sidecar, retaining the previous version as backup."""

    annotation.validate()
    path = phase_annotation_path(annotation.session_id, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamped = PhaseAnnotation(
        session_id=annotation.session_id,
        protocol=annotation.protocol,
        fridge_exit_h=annotation.fridge_exit_h,
        warm_stable_h=annotation.warm_stable_h,
        cold_stable_h=annotation.cold_stable_h,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    payload = timestamped.to_dict()
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            shutil.copy2(path, path.with_suffix(".json.bak"))
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def session_duration_hours(analysis: pd.DataFrame) -> float:
    if analysis.empty or not isinstance(analysis.index, pd.DatetimeIndex):
        raise ValueError("L'analisi non contiene una timeline valida.")
    return float((analysis.index[-1] - analysis.index[0]).total_seconds() / 3600.0)


def build_phase_definitions(
    annotation: PhaseAnnotation, duration_h: float
) -> list[PhaseDefinition]:
    annotation.validate()
    duration = float(duration_h)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("La sessione non ha una durata valida.")
    if annotation.protocol == "ambient":
        return [PhaseDefinition("ambient", "Temperatura ambiente", 0.0, duration)]

    fridge_exit = float(annotation.fridge_exit_h)
    cold_stable = annotation.cold_stable_h
    phases: list[PhaseDefinition] = []
    if cold_stable is not None:
        cold_stable = float(cold_stable)
        cooling_end = min(cold_stable, duration)
        phases.append(
            PhaseDefinition(
                "cooling",
                "Raffreddamento",
                0.0,
                cooling_end,
                complete=cold_stable <= duration,
            )
        )
        if cold_stable >= duration:
            return phases
        cold_start = cold_stable
    else:
        cold_start = 0.0

    cold_end = min(fridge_exit, duration)
    phases.append(
        PhaseDefinition(
            "cold",
            "Freddo stabile",
            cold_start,
            cold_end,
            complete=fridge_exit <= duration,
        )
    )
    if fridge_exit >= duration:
        return phases

    warm_stable = annotation.warm_stable_h
    if warm_stable is None:
        phases.append(
            PhaseDefinition(
                "settling",
                "Assestamento termico",
                fridge_exit,
                duration,
                complete=False,
            )
        )
        return phases

    warm_stable = float(warm_stable)
    settling_end = min(warm_stable, duration)
    phases.append(
        PhaseDefinition(
            "settling",
            "Assestamento termico",
            fridge_exit,
            settling_end,
            complete=warm_stable <= duration,
        )
    )
    if warm_stable < duration:
        phases.append(
            PhaseDefinition(
                "warm_stable",
                "Ambiente stabilizzato",
                warm_stable,
                duration,
            )
        )
    return phases


def build_thermal_diagnostic(
    analysis: pd.DataFrame,
    *,
    temperature_smoothing_minutes: float = 10.0,
    slope_smoothing_minutes: float = 15.0,
) -> pd.DataFrame:
    """Build smoothed temperatures and dT/dt on the real session timeline."""

    if analysis.empty or not isinstance(analysis.index, pd.DatetimeIndex):
        raise ValueError("L'analisi non contiene una timeline valida.")
    frame = analysis.sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    diagnostic = pd.DataFrame(index=frame.index.copy())
    diagnostic["elapsed_hours"] = (
        diagnostic.index - diagnostic.index[0]
    ).total_seconds() / 3600.0
    elapsed_hours = diagnostic["elapsed_hours"].to_numpy(dtype=float)

    field_map = {
        "temperature_dough_c": (
            "dough_temp_smooth_c",
            "dough_temp_slope_c_h",
        ),
        "temperature_ambient_c": (
            "ambient_temp_smooth_c",
            "ambient_temp_slope_c_h",
        ),
    }
    for source_field, (smooth_field, slope_field) in field_map.items():
        if source_field not in frame:
            diagnostic[smooth_field] = np.nan
            diagnostic[slope_field] = np.nan
            continue
        temperature = pd.to_numeric(frame[source_field], errors="coerce")
        smooth = temperature.rolling(
            f"{max(1.0, float(temperature_smoothing_minutes))}min",
            center=True,
            min_periods=1,
        ).median()
        diagnostic[smooth_field] = smooth

        slopes = np.full(len(smooth), np.nan, dtype=float)
        valid = np.isfinite(smooth.to_numpy(dtype=float))
        if int(valid.sum()) >= 2:
            valid_times = elapsed_hours[valid]
            valid_values = smooth.to_numpy(dtype=float)[valid]
            slopes[valid] = np.gradient(valid_values, valid_times)
        diagnostic[slope_field] = pd.Series(
            slopes,
            index=diagnostic.index,
        ).rolling(
            f"{max(1.0, float(slope_smoothing_minutes))}min",
            center=True,
            min_periods=1,
        ).median()

    if not any(
        diagnostic[field].notna().any()
        for field in ("dough_temp_smooth_c", "ambient_temp_smooth_c")
    ):
        raise ValueError("La sessione non contiene curve di temperatura.")
    diagnostic["thermal_slope_gap_c_h"] = (
        diagnostic["dough_temp_slope_c_h"]
        - diagnostic["ambient_temp_slope_c_h"]
    ).abs()
    return diagnostic


def _first_sustained_time(
    elapsed_hours: np.ndarray,
    mask: np.ndarray,
    *,
    minimum_duration_h: float,
) -> float | None:
    """Return the start of the first time-contiguous true interval."""

    if len(elapsed_hours) < 2 or len(mask) != len(elapsed_hours):
        return None
    finite_steps = np.diff(elapsed_hours)
    finite_steps = finite_steps[np.isfinite(finite_steps) & (finite_steps > 0)]
    typical_step = float(np.median(finite_steps)) if len(finite_steps) else 0.0
    maximum_gap = max(0.25, typical_step * 3.0)
    start_index: int | None = None
    previous_index: int | None = None
    for index, is_valid in enumerate(mask):
        if not bool(is_valid) or not math.isfinite(float(elapsed_hours[index])):
            start_index = None
            previous_index = None
            continue
        if (
            previous_index is None
            or float(elapsed_hours[index] - elapsed_hours[previous_index]) > maximum_gap
        ):
            start_index = index
        previous_index = index
        if start_index is not None and (
            float(elapsed_hours[index] - elapsed_hours[start_index])
            >= minimum_duration_h
        ):
            return float(elapsed_hours[start_index])
    return None


def detect_thermal_phase_proposal(
    analysis: pd.DataFrame,
    session_id: str,
    *,
    minimum_stable_minutes: float = 30.0,
) -> ThermalPhaseProposal:
    """Infer fridge boundaries without saving or mutating the source analysis.

    A proposal is emitted only when the ambient curve contains a convincing
    cold-to-warm transition. Constant calibration offsets are ignored: thermal
    coupling and stabilization are evaluated from the two slopes and their lag.
    """

    try:
        diagnostic = build_thermal_diagnostic(analysis)
    except ValueError as error:
        return ThermalPhaseProposal(None, 0.0, (str(error),))

    elapsed = diagnostic["elapsed_hours"].to_numpy(dtype=float)
    ambient = diagnostic["ambient_temp_smooth_c"].to_numpy(dtype=float)
    ambient_slope = diagnostic["ambient_temp_slope_c_h"].to_numpy(dtype=float)
    finite_ambient = np.isfinite(elapsed) & np.isfinite(ambient)
    if int(finite_ambient.sum()) < 8:
        return ThermalPhaseProposal(
            None,
            0.0,
            ("Curva ambiente insufficiente per classificare le fasi.",),
        )

    valid_ambient = ambient[finite_ambient]
    cold_level = float(np.nanpercentile(valid_ambient, 10.0))
    warm_level = float(np.nanpercentile(valid_ambient, 90.0))
    thermal_step = warm_level - cold_level
    if thermal_step < 5.0:
        return ThermalPhaseProposal(
            None,
            0.0,
            (
                "Nessun passaggio frigo → ambiente sufficientemente netto; "
                "la sessione resta non classificata.",
            ),
        )

    slope_candidates = (
        finite_ambient
        & np.isfinite(ambient_slope)
        & (elapsed >= min(0.25, float(elapsed[-1]) * 0.1))
    )
    if not slope_candidates.any():
        return ThermalPhaseProposal(None, 0.0, ("Cambio termico non localizzabile.",))
    candidate_indices = np.flatnonzero(slope_candidates)
    peak_index = int(candidate_indices[np.nanargmax(ambient_slope[candidate_indices])])
    peak_slope = float(ambient_slope[peak_index])
    if peak_slope < 1.5:
        return ThermalPhaseProposal(
            None,
            0.0,
            ("Il riscaldamento ambiente è troppo graduale per definire l'uscita.",),
        )

    departure_threshold = cold_level + max(1.0, thermal_step * 0.12)
    pre_peak = np.flatnonzero(
        finite_ambient
        & (np.arange(len(elapsed)) <= peak_index)
        & (ambient <= departure_threshold)
    )
    if not len(pre_peak):
        return ThermalPhaseProposal(None, 0.0, ("Inizio del salto termico non trovato.",))
    last_cold_index = int(pre_peak[-1])
    exit_index = min(last_cold_index + 1, len(elapsed) - 1)
    fridge_exit_h = float(elapsed[exit_index])
    if not math.isfinite(fridge_exit_h) or fridge_exit_h <= 0:
        return ThermalPhaseProposal(None, 0.0, ("Confine di uscita non valido.",))

    tail_start = max(exit_index, int(len(elapsed) * 0.85))
    warm_tail = ambient[tail_start:]
    warm_tail = warm_tail[np.isfinite(warm_tail)]
    if not len(warm_tail) or float(np.median(warm_tail)) < cold_level + thermal_step * 0.65:
        return ThermalPhaseProposal(
            None,
            0.0,
            ("Il salto caldo non persiste fino alla parte finale della sessione.",),
        )

    stable_duration_h = max(5.0, float(minimum_stable_minutes)) / 60.0
    dough = diagnostic["dough_temp_smooth_c"].to_numpy(dtype=float)
    dough_slope = diagnostic["dough_temp_slope_c_h"].to_numpy(dtype=float)
    slope_gap = diagnostic["thermal_slope_gap_c_h"].to_numpy(dtype=float)
    finite_dough_slope = np.isfinite(dough) & np.isfinite(dough_slope)
    has_dough_dynamics = int(finite_dough_slope.sum()) >= 8

    cold_tolerance = max(0.8, thermal_step * 0.08)
    cold_mask = (
        finite_ambient
        & (elapsed < fridge_exit_h)
        & (np.abs(ambient - cold_level) <= cold_tolerance)
        & np.isfinite(ambient_slope)
        & (np.abs(ambient_slope) <= 0.5)
    )
    if has_dough_dynamics:
        cold_mask &= (
            finite_dough_slope
            & np.isfinite(slope_gap)
            & (np.abs(dough_slope) <= 0.25)
            & (slope_gap <= 0.5)
        )
    cold_stable_h = _first_sustained_time(
        elapsed,
        cold_mask,
        minimum_duration_h=stable_duration_h,
    )
    if cold_stable_h is not None and cold_stable_h >= fridge_exit_h:
        cold_stable_h = None

    dough_response_h: float | None = None
    warm_stable_h: float | None = None
    if has_dough_dynamics:
        response_window_h = min(6.0, max(1.0, float(elapsed[-1]) - fridge_exit_h))
        response_mask = (
            finite_dough_slope
            & (elapsed >= fridge_exit_h)
            & (elapsed <= fridge_exit_h + response_window_h)
            & (dough_slope >= 0.20)
        )
        dough_response_h = _first_sustained_time(
            elapsed,
            response_mask,
            minimum_duration_h=min(stable_duration_h, 10.0 / 60.0),
        )

        exit_dough_values = dough[
            finite_dough_slope & (elapsed <= fridge_exit_h)
        ]
        dough_at_exit = (
            float(exit_dough_values[-1]) if len(exit_dough_values) else math.nan
        )
        minimum_dough_change = max(0.5, thermal_step * 0.02)
        warm_mask = (
            finite_dough_slope
            & finite_ambient
            & np.isfinite(ambient_slope)
            & np.isfinite(slope_gap)
            & (elapsed > fridge_exit_h)
            & (np.abs(ambient_slope) <= 0.5)
            & (np.abs(dough_slope) <= 0.25)
            & (slope_gap <= 0.5)
            & (dough >= dough_at_exit + minimum_dough_change)
        )
        if dough_response_h is not None:
            warm_mask &= elapsed > dough_response_h
            warm_stable_h = _first_sustained_time(
                elapsed,
                warm_mask,
                minimum_duration_h=stable_duration_h,
            )
    if warm_stable_h is not None and warm_stable_h <= fridge_exit_h:
        warm_stable_h = None

    confidence = 0.50 + min(0.20, (thermal_step - 5.0) / 40.0) + min(
        0.15, peak_slope / 80.0
    )
    if dough_response_h is not None:
        confidence += 0.13
    confidence = min(0.98, confidence)
    notes = [
        f"Uscita dal frigo proposta a {fridge_exit_h:.2f} h dal salto persistente dell'ambiente.",
    ]
    if cold_stable_h is None:
        notes.append("Inizio del freddo stabile non riconosciuto con sufficiente continuità.")
    else:
        notes.append(f"Freddo stabile proposto da {cold_stable_h:.2f} h.")
    if not has_dough_dynamics:
        notes.append(
            "Curva impasto insufficiente: il salto ambiente non ha conferma dinamica."
        )
    elif dough_response_h is None:
        notes.append(
            "Nessuna risposta termica persistente dell'impasto dopo il salto ambiente."
        )
    else:
        notes.append(
            f"Risposta dell'impasto rilevata a {dough_response_h:.2f} h, "
            "indipendentemente dall'offset dei sensori."
        )
    if warm_stable_h is None:
        notes.append(
            "Le due pendenze non sono ancora entrambe stabili: "
            "l'assestamento resta aperto."
        )
    else:
        notes.append(f"Impasto stabilizzato proposto da {warm_stable_h:.2f} h.")

    annotation = PhaseAnnotation(
        session_id=session_id,
        protocol="fridge_to_ambient",
        fridge_exit_h=fridge_exit_h,
        warm_stable_h=warm_stable_h,
        cold_stable_h=cold_stable_h,
    )
    annotation.validate()
    return ThermalPhaseProposal(annotation, confidence, tuple(notes))


def _slice_phase_analysis(
    analysis: pd.DataFrame,
    definition: PhaseDefinition,
    *,
    baseline_minutes: float,
) -> pd.DataFrame:
    if analysis.empty or not isinstance(analysis.index, pd.DatetimeIndex):
        raise ValueError("L'analisi non contiene una timeline valida.")
    session_start = analysis.index[0]
    start = session_start + pd.to_timedelta(definition.start_h, unit="h")
    stop = session_start + pd.to_timedelta(definition.end_h, unit="h")
    if stop <= start:
        raise ValueError(f"La fase {definition.label} ha durata nulla.")

    expanded_index = analysis.index.union(pd.DatetimeIndex([start, stop])).sort_values()
    expanded = analysis.reindex(expanded_index)
    numeric_columns = expanded.select_dtypes(include=[np.number]).columns
    expanded[numeric_columns] = expanded[numeric_columns].interpolate(
        method="time", limit_area="inside"
    )
    other_columns = [column for column in expanded.columns if column not in numeric_columns]
    if other_columns:
        expanded[other_columns] = expanded[other_columns].ffill().bfill()
    phase = expanded.loc[start:stop].copy()
    phase.attrs.update(analysis.attrs)
    if len(phase) < 2:
        raise ValueError(f"La fase {definition.label} contiene meno di due campioni.")

    source_field = "signal_smooth"
    if source_field not in phase:
        raise ValueError("L'analisi non contiene il segnale elaborato.")
    baseline_stop = start + pd.to_timedelta(max(0.0, baseline_minutes), unit="min")
    baseline_values = pd.to_numeric(
        phase.loc[start:baseline_stop, source_field], errors="coerce"
    ).dropna()
    if baseline_values.empty:
        baseline_values = pd.to_numeric(phase[source_field], errors="coerce").dropna().head(1)
    if baseline_values.empty:
        raise ValueError(f"Baseline non disponibile per la fase {definition.label}.")
    baseline = float(baseline_values.median())
    if not math.isfinite(baseline) or baseline <= 0:
        raise ValueError(f"Baseline non valida per la fase {definition.label}.")

    phase["elapsed_hours"] = (
        phase.index - phase.index[0]
    ).total_seconds() / 3600.0
    phase["growth_pct"] = (phase[source_field] / baseline - 1.0) * 100.0
    phase.attrs["baseline_value"] = baseline
    return phase


def analyze_protocol_phases(
    analysis: pd.DataFrame,
    session_id: str,
    annotation: PhaseAnnotation,
    config: FermentationAnalysisConfig | None = None,
    *,
    baseline_minutes: float = 5.0,
) -> list[PhaseAnalysis]:
    """Return phase-local metrics without mutating the source analysis."""

    definitions = build_phase_definitions(
        annotation, session_duration_hours(analysis)
    )
    results: list[PhaseAnalysis] = []
    for definition in definitions:
        phase = _slice_phase_analysis(
            analysis,
            definition,
            baseline_minutes=baseline_minutes,
        )
        fingerprint = compute_fermentation_fingerprint(
            phase,
            session_id,
            config,
        )
        initial = fingerprint.metrics.initial_value
        final_series = pd.to_numeric(phase["signal_smooth"], errors="coerce").dropna()
        final = float(final_series.iloc[-1]) if not final_series.empty else None
        duration = definition.duration_h
        observed_growth = (
            (final / initial - 1.0) * 100.0
            if final is not None and initial is not None and initial > 0
            else None
        )
        mean_rate = (
            (final - initial) / duration
            if final is not None and initial is not None and duration > 0
            else None
        )
        mean_specific = (
            math.log(final / initial) / duration
            if final is not None
            and initial is not None
            and final > 0
            and initial > 0
            and duration > 0
            else None
        )
        estimated_doubling = (
            math.log(2.0) / mean_specific
            if mean_specific is not None and mean_specific > np.finfo(float).eps
            else None
        )
        results.append(
            PhaseAnalysis(
                definition=definition,
                fingerprint=fingerprint,
                final_value=final,
                observed_growth_percent=observed_growth,
                mean_growth_rate_value_h=mean_rate,
                mean_specific_growth_rate_h=mean_specific,
                estimated_doubling_time_h=estimated_doubling,
            )
        )
    return results


def phase_results_to_dataframe(results: Sequence[PhaseAnalysis]) -> pd.DataFrame:
    return pd.DataFrame([result.to_dict() for result in results])


def phase_results_to_json(
    results: Sequence[PhaseAnalysis], *, indent: int = 2
) -> str:
    return json.dumps(
        [result.to_dict() for result in results],
        ensure_ascii=False,
        indent=indent,
        allow_nan=False,
    )
