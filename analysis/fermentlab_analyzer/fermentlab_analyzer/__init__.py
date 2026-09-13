"""Core components for the FermentLab Analyzer."""

from .config import InfluxSettings
from .fingerprint import (
    FermentationAnalysisConfig,
    FermentationFingerprint,
    FermentationMetrics,
    MetricQuality,
    compute_fermentation_fingerprint,
    fingerprints_to_dataframe,
    fingerprints_to_json,
    time_to_growth,
)
from .influx import InfluxRepository
from .phases import (
    PhaseAnalysis,
    PhaseAnnotation,
    ThermalPhaseProposal,
    analyze_protocol_phases,
    build_thermal_diagnostic,
    detect_thermal_phase_proposal,
    default_phase_sidecar_dir,
    load_phase_annotation,
    phase_results_to_dataframe,
    phase_results_to_json,
    save_phase_annotation,
)
from .processing import (
    AnalysisSummary,
    add_relative_time,
    analyze_session,
    build_recipe_sections,
    build_recipe_summary,
    summarize_session,
)

__all__ = [
    "AnalysisSummary",
    "FermentationAnalysisConfig",
    "FermentationFingerprint",
    "FermentationMetrics",
    "InfluxRepository",
    "InfluxSettings",
    "MetricQuality",
    "PhaseAnalysis",
    "PhaseAnnotation",
    "ThermalPhaseProposal",
    "add_relative_time",
    "analyze_session",
    "analyze_protocol_phases",
    "build_thermal_diagnostic",
    "detect_thermal_phase_proposal",
    "build_recipe_summary",
    "compute_fermentation_fingerprint",
    "fingerprints_to_dataframe",
    "fingerprints_to_json",
    "default_phase_sidecar_dir",
    "load_phase_annotation",
    "phase_results_to_dataframe",
    "phase_results_to_json",
    "save_phase_annotation",
    "summarize_session",
    "time_to_growth",
]
