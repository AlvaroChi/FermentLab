"""Local Streamlit UI for exploring FermentLab sessions in InfluxDB."""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from fermentlab_analyzer import (
    InfluxRepository,
    InfluxSettings,
    PhaseAnalysis,
    PhaseAnnotation,
    add_relative_time,
    analyze_protocol_phases,
    analyze_session,
    build_thermal_diagnostic,
    build_recipe_sections,
    build_recipe_summary,
    compute_fermentation_fingerprint,
    default_phase_sidecar_dir,
    detect_thermal_phase_proposal,
    fingerprints_to_dataframe,
    fingerprints_to_json,
    load_phase_annotation,
    phase_results_to_dataframe,
    phase_results_to_json,
    save_phase_annotation,
    summarize_session,
)


st.set_page_config(
    page_title="FermentLab Â· Analyzer",
    page_icon="ðŸ«§",
    layout="wide",
    initial_sidebar_state="expanded",
)


APP_CSS = """
<style>
    :root {
        --fl-ink: #20332b;
        --fl-muted: #64736c;
        --fl-green: #247a52;
        --fl-green-soft: #eaf5ef;
        --fl-amber: #d28a26;
        --fl-border: rgba(32, 51, 43, 0.12);
    }
    .stApp { background: #fbfcfa; }
    .block-container {
        max-width: 1440px;
        padding-top: 2.2rem;
        padding-bottom: 4rem;
    }
    [data-testid="stSidebar"] { background: #f3f7f4; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: var(--fl-muted);
    }
    .fl-hero {
        padding: 1.25rem 1.4rem;
        margin-bottom: 1.25rem;
        border: 1px solid var(--fl-border);
        border-radius: 18px;
        background:
            radial-gradient(circle at 92% 10%, rgba(210,138,38,.13), transparent 28%),
            linear-gradient(135deg, #f2f8f4 0%, #ffffff 72%);
    }
    .fl-eyebrow {
        color: var(--fl-green);
        font-size: .76rem;
        font-weight: 750;
        letter-spacing: .11em;
        text-transform: uppercase;
        margin-bottom: .35rem;
    }
    .fl-hero h1 {
        color: var(--fl-ink);
        font-size: clamp(1.8rem, 3vw, 2.55rem);
        line-height: 1.05;
        margin: 0 0 .55rem 0;
    }
    .fl-hero p {
        color: var(--fl-muted);
        font-size: 1rem;
        margin: 0;
        max-width: 780px;
    }
    .fl-section-title { margin: .2rem 0 1rem 0; }
    .fl-section-title h2 {
        color: var(--fl-ink);
        font-size: 1.35rem;
        margin: 0 0 .2rem 0;
    }
    .fl-section-title p { color: var(--fl-muted); margin: 0; }
    [data-testid="stMetric"] {
        min-height: 112px;
        padding: 1rem 1.05rem;
        border: 1px solid var(--fl-border);
        border-radius: 14px;
        background: #ffffff;
        box-shadow: 0 4px 18px rgba(32, 51, 43, .035);
    }
    [data-testid="stMetricLabel"] { color: var(--fl-muted); }
    [data-testid="stMetricValue"] { color: var(--fl-ink); }
    [data-testid="stExpander"] {
        border-color: var(--fl-border);
        border-radius: 14px;
        background: rgba(255,255,255,.72);
    }
    .stButton > button { border-radius: 10px; font-weight: 650; }
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div { border-radius: 10px; }
    [data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
    @media (max-width: 700px) {
        .block-container { padding-top: 1rem; }
        .fl-hero { padding: 1rem; border-radius: 14px; }
        [data-testid="stMetric"] { min-height: 96px; }
    }
</style>
"""

st.markdown(APP_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=30, show_spinner=False)
def list_sessions(
    url: str,
    org: str,
    bucket: str,
    token: str,
    measurement: str,
    lookback_days: int,
) -> pd.DataFrame:
    settings = InfluxSettings(url, org, bucket, token, measurement)
    return InfluxRepository(settings).list_sessions(lookback_days)


@st.cache_data(ttl=30, show_spinner=False)
def load_session(
    url: str,
    org: str,
    bucket: str,
    token: str,
    measurement: str,
    session_id: str,
    lookback_days: int,
) -> pd.DataFrame:
    settings = InfluxSettings(url, org, bucket, token, measurement)
    return InfluxRepository(settings).load_session(session_id, lookback_days)


@st.cache_data(ttl=30, show_spinner=False)
def load_session_metadata(
    url: str,
    org: str,
    bucket: str,
    token: str,
    measurement: str,
    session_id: str,
    lookback_days: int,
) -> dict[str, object]:
    settings = InfluxSettings(url, org, bucket, token, measurement)
    return InfluxRepository(settings).load_session_metadata(session_id, lookback_days)


@st.cache_data(ttl=30, show_spinner=False)
def load_session_admin_info(
    url: str,
    org: str,
    bucket: str,
    token: str,
    measurement: str,
    session_id: str,
    lookback_days: int,
) -> dict[str, object]:
    settings = InfluxSettings(url, org, bucket, token, measurement)
    return InfluxRepository(settings).load_session_admin_info(session_id, lookback_days)


@st.cache_data(ttl=30, show_spinner=False)
def preview_session_merge(
    url: str,
    org: str,
    bucket: str,
    token: str,
    measurement: str,
    source_session_id: str,
    target_session_id: str,
    lookback_days: int,
) -> dict[str, object]:
    settings = InfluxSettings(url, org, bucket, token, measurement)
    return InfluxRepository(settings).preview_merge_sessions(
        source_session_id,
        target_session_id,
        lookback_days,
    )


@st.cache_data(ttl=30, show_spinner=False)
def load_management_catalog(
    url: str,
    org: str,
    bucket: str,
    token: str,
    measurement: str,
    lookback_days: int,
    session_ids: tuple[str, ...],
) -> pd.DataFrame:
    settings = InfluxSettings(url, org, bucket, token, measurement)
    repository = InfluxRepository(settings)
    rows: list[dict[str, object]] = []
    for session_id in session_ids:
        try:
            info = repository.load_session_admin_info(session_id, lookback_days)
        except Exception as error:
            info = {
                "session_id": session_id,
                "kind": "error",
                "is_test": False,
                "is_failed": False,
                "is_suspicious": True,
                "reasons": [str(error)],
            }
        rows.append(
            {
                "session_id": session_id,
                "first_seen": info.get("first_seen"),
                "last_seen": info.get("last_seen"),
                "duration_hours": float(info.get("duration_hours") or 0.0),
                "record_count": int(info.get("record_count") or 0),
                "sample_count": int(info.get("sample_count") or 0),
                "kind": str(info.get("kind") or "normal"),
                "is_test": bool(info.get("is_test")),
                "is_failed": bool(info.get("is_failed")),
                "is_suspicious": bool(info.get("is_suspicious")),
                "reasons": ", ".join(str(reason) for reason in info.get("reasons", [])),
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    if "last_seen" in frame:
        frame["last_seen"] = pd.to_datetime(frame["last_seen"], utc=True, errors="coerce")
    if "first_seen" in frame:
        frame["first_seen"] = pd.to_datetime(frame["first_seen"], utc=True, errors="coerce")
    return frame.sort_values("last_seen", ascending=False, na_position="last")


def delete_session_from_influx(
    url: str,
    org: str,
    bucket: str,
    token: str,
    measurement: str,
    session_id: str,
    lookback_days: int,
) -> dict[str, object]:
    settings = InfluxSettings(url, org, bucket, token, measurement)
    return InfluxRepository(settings).delete_session(session_id, lookback_days)


def merge_sessions_influx(
    url: str,
    org: str,
    bucket: str,
    token: str,
    measurement: str,
    source_session_id: str,
    target_session_id: str,
    lookback_days: int,
    delete_source: bool,
) -> dict[str, object]:
    settings = InfluxSettings(url, org, bucket, token, measurement)
    return InfluxRepository(settings).merge_sessions(
        source_session_id,
        target_session_id,
        lookback_days,
        delete_source,
    )


def fmt_number(value: float, suffix: str, digits: int = 1) -> str:
    if not math.isfinite(value):
        return "â€”"
    return f"{value:.{digits}f}{suffix}"


def fmt_timestamp(value: object) -> str:
    if value is None:
        return "â€”"
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return "â€”"
    return f"{timestamp:%Y-%m-%d %H:%M:%S} UTC"


def fmt_duration(value_hours: float | None) -> str:
    """Format a duration without implying sub-sample precision."""

    if value_hours is None or not math.isfinite(float(value_hours)):
        return "N.A."
    total_seconds = max(0, int(round(float(value_hours) * 3600.0)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if total_seconds < 600 and seconds:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{hours:02d}:{minutes:02d}"


def fmt_optional(
    value: float | None,
    suffix: str = "",
    digits: int = 1,
    *,
    signed: bool = False,
) -> str:
    if value is None or not math.isfinite(float(value)):
        return "N.A."
    sign = "+" if signed and float(value) >= 0 else ""
    return f"{sign}{float(value):.{digits}f}{suffix}"


FINGERPRINT_COMPARISON_FIELDS = (
    ("t25_h", "t25", "h", True),
    ("t50_h", "t50", "h", True),
    ("t75_h", "t75", "h", True),
    ("t100_h", "Raddoppio", "h", True),
    ("t150_h", "t150", "h", True),
    ("t200_h", "Triplicazione", "h", True),
    ("maximum_growth_percent", "Crescita massima", "%", True),
    ("max_growth_rate_value_h", "VelocitÃ  massima", "signal/h", True),
    ("max_specific_growth_rate_h", "VelocitÃ  specifica massima", "1/h", True),
    ("lag_time_h", "Lag time", "h", True),
    ("inflection_time_h", "Punto di flesso", "h", True),
    ("plateau_start_time_h", "Inizio plateau", "h", True),
    ("active_phase_duration_h", "Durata fase attiva", "h", True),
    ("late_early_ratio", "Rapporto late/early", "Ã—", True),
    ("dough_temp_mean_c", "Temperatura media impasto", "Â°C", False),
    ("dough_temp_at_max_growth_rate_c", "Temperatura a vmax", "Â°C", False),
    ("ambient_temp_mean_c", "Temperatura media ambiente", "Â°C", False),
    ("delta_t_max_c", "Î”T massimo", "Â°C", False),
    ("thermal_integral_20c_c_h", "Integrale termico (20 Â°C)", "Â°CÂ·h", True),
    ("loss_from_peak_percent", "Perdita dal picco", "%", True),
)

FINGERPRINT_EVENT_LABELS = {
    "lag": "Lag",
    "t25": "t25",
    "t50": "t50",
    "t75": "t75",
    "t100": "t100",
    "max_rate": "vmax",
    "inflection": "Flesso",
    "plateau": "Plateau",
    "collapse": "Collasso",
}

PHASE_VISUAL_STYLES = {
    "cooling": ("rgba(201, 154, 255, 0.20)", "#C99AFF"),
    "cold": ("rgba(121, 184, 255, 0.22)", "#79B8FF"),
    "settling": ("rgba(241, 185, 94, 0.22)", "#F1B95E"),
    "warm_stable": ("rgba(105, 215, 160, 0.18)", "#69D7A0"),
    "post_fridge": ("rgba(241, 185, 94, 0.18)", "#F1B95E"),
    "ambient": ("rgba(105, 215, 160, 0.18)", "#69D7A0"),
}


def phase_boundary_style(phase_key: str) -> tuple[str, str]:
    return {
        "cold": ("Freddo stabilizzato", "dot"),
        "settling": ("Uscita dal frigo", "dash"),
        "post_fridge": ("Uscita dal frigo", "dash"),
        "warm_stable": ("Impasto stabilizzato", "dashdot"),
    }.get(phase_key, ("Cambio fase", "dash"))


def render_fingerprint_exports(
    fingerprints: list[FermentationFingerprint], *, key_prefix: str
) -> None:
    export_frame = fingerprints_to_dataframe(fingerprints)
    csv_bytes = export_frame.to_csv(index=False, na_rep="").encode("utf-8")
    json_text = fingerprints_to_json(fingerprints)
    file_stem = "fermentation_fingerprint" if len(fingerprints) == 1 else "fermentation_comparison"
    with st.container(horizontal=True):
        st.download_button(
            "Esporta CSV",
            data=csv_bytes,
            file_name=f"{file_stem}.csv",
            mime="text/csv",
            key=f"{key_prefix}_csv",
            icon=":material/download:",
            on_click="ignore",
        )
        st.download_button(
            "Esporta JSON",
            data=json_text,
            file_name=f"{file_stem}.json",
            mime="application/json",
            key=f"{key_prefix}_json",
            icon=":material/data_object:",
            on_click="ignore",
        )


def build_single_fingerprint_table(
    fingerprint: FermentationFingerprint,
) -> pd.DataFrame:
    metrics = fingerprint.metrics
    rate_unit = f" {metrics.signal_unit}/h"
    specs = [
        ("Crescita", "Durata sessione", fmt_duration(metrics.duration_h), metrics.duration_h, None),
        ("Crescita", "Valore iniziale", fmt_optional(metrics.initial_value, f" {metrics.signal_unit}"), metrics.initial_value, None),
        ("Crescita", "Valore massimo", fmt_optional(metrics.max_value, f" {metrics.signal_unit}"), metrics.max_value, None),
        ("Crescita", "Crescita massima", fmt_optional(metrics.maximum_growth_percent, "%", signed=True), metrics.maximum_growth_percent, None),
        ("Tempi", "t10", fmt_duration(metrics.t10_h), metrics.t10_h, "t10_h"),
        ("Tempi", "t25", fmt_duration(metrics.t25_h), metrics.t25_h, "t25_h"),
        ("Tempi", "t50", fmt_duration(metrics.t50_h), metrics.t50_h, "t50_h"),
        ("Tempi", "t75", fmt_duration(metrics.t75_h), metrics.t75_h, "t75_h"),
        ("Tempi", "Raddoppio (t100)", fmt_duration(metrics.t100_h), metrics.t100_h, "t100_h"),
        ("Tempi", "t150", fmt_duration(metrics.t150_h), metrics.t150_h, "t150_h"),
        ("Tempi", "Triplicazione (t200)", fmt_duration(metrics.t200_h), metrics.t200_h, "t200_h"),
        ("Tempi", "Lag time", fmt_duration(metrics.lag_time_h), metrics.lag_time_h, "lag_time_h"),
        ("Dinamica", "VelocitÃ  massima", fmt_optional(metrics.max_growth_rate_value_h, rate_unit), metrics.max_growth_rate_value_h, "max_growth_rate_value_h"),
        ("Dinamica", "Tempo vmax", fmt_duration(metrics.time_of_max_growth_rate_h), metrics.time_of_max_growth_rate_h, "max_growth_rate_value_h"),
        ("Dinamica", "VelocitÃ  specifica massima", fmt_optional(metrics.max_specific_growth_rate_h, " 1/h", 3), metrics.max_specific_growth_rate_h, "max_specific_growth_rate_h"),
        ("Dinamica", "Punto di flesso", fmt_duration(metrics.inflection_time_h), metrics.inflection_time_h, "inflection_time_h"),
        ("Dinamica", "Early rate (25â€“50%)", fmt_optional(metrics.early_rate_value_h, rate_unit), metrics.early_rate_value_h, None),
        ("Dinamica", "Late rate (75â€“100%)", fmt_optional(metrics.late_rate_value_h, rate_unit), metrics.late_rate_value_h, None),
        ("Dinamica", "Rapporto late/early", fmt_optional(metrics.late_early_ratio, "Ã—", 2), metrics.late_early_ratio, "late_early_ratio"),
        ("Temperatura", "Temperatura iniziale impasto", fmt_optional(metrics.dough_temp_initial_c, " Â°C"), metrics.dough_temp_initial_c, None),
        ("Temperatura", "Temperatura finale impasto", fmt_optional(metrics.dough_temp_final_c, " Â°C"), metrics.dough_temp_final_c, None),
        ("Temperatura", "Temperatura media impasto", fmt_optional(metrics.dough_temp_mean_c, " Â°C"), metrics.dough_temp_mean_c, None),
        ("Temperatura", "Temperatura min / max impasto", f"{fmt_optional(metrics.dough_temp_min_c)} / {fmt_optional(metrics.dough_temp_max_c)} Â°C", metrics.dough_temp_mean_c, None),
        ("Temperatura", "Temperatura a vmax", fmt_optional(metrics.dough_temp_at_max_growth_rate_c, " Â°C"), metrics.dough_temp_at_max_growth_rate_c, None),
        ("Temperatura", "Temperatura media ambiente", fmt_optional(metrics.ambient_temp_mean_c, " Â°C"), metrics.ambient_temp_mean_c, None),
        ("Temperatura", "Î”T medio", fmt_optional(metrics.delta_t_mean_c, " Â°C", signed=True), metrics.delta_t_mean_c, None),
        ("Temperatura", "Î”T massimo", fmt_optional(metrics.delta_t_max_c, " Â°C", signed=True), metrics.delta_t_max_c, None),
        ("Termica", "Integrale termico 0 Â°C", fmt_optional(metrics.thermal_integral_0c_c_h, " Â°CÂ·h"), metrics.thermal_integral_0c_c_h, "thermal_integral"),
        ("Termica", "Integrale termico 4 Â°C", fmt_optional(metrics.thermal_integral_4c_c_h, " Â°CÂ·h"), metrics.thermal_integral_4c_c_h, "thermal_integral"),
        ("Termica", "Integrale termico 20 Â°C", fmt_optional(metrics.thermal_integral_20c_c_h, " Â°CÂ·h"), metrics.thermal_integral_20c_c_h, "thermal_integral"),
        ("Fasi", "Inizio plateau", fmt_duration(metrics.plateau_start_time_h), metrics.plateau_start_time_h, "plateau_start_time_h"),
        ("Fasi", "Inizio fase attiva", fmt_duration(metrics.active_phase_start_h), metrics.active_phase_start_h, "active_phase_duration_h"),
        ("Fasi", "Fine fase attiva", fmt_duration(metrics.active_phase_end_h), metrics.active_phase_end_h, "active_phase_duration_h"),
        ("Fasi", "Durata fase attiva", fmt_duration(metrics.active_phase_duration_h), metrics.active_phase_duration_h, "active_phase_duration_h"),
        ("Fasi", "Collasso", "Rilevato" if metrics.collapse_detected else "Non rilevato", True, "collapse_detected"),
        ("Fasi", "Inizio collasso", fmt_duration(metrics.collapse_start_time_h), metrics.collapse_start_time_h, None),
        ("Fasi", "Perdita dal picco", fmt_optional(metrics.loss_from_peak_percent, "%"), metrics.loss_from_peak_percent, None),
    ]
    status_labels = {
        "valid": "Valida",
        "unavailable": "Non disponibile",
        "low_confidence": "Bassa confidenza",
    }
    rows: list[dict[str, str]] = []
    for group, label, display_value, raw_value, quality_key in specs:
        quality = fingerprint.quality.get(quality_key) if quality_key else None
        if quality is not None:
            status = quality.status
            reason = quality.reason or ""
        elif raw_value is None or (
            isinstance(raw_value, float) and not math.isfinite(raw_value)
        ):
            status = "unavailable"
            reason = "dato non disponibile"
        else:
            status = "valid"
            reason = ""
        rows.append(
            {
                "Gruppo": group,
                "Parametro": label,
                "Valore": display_value,
                "QualitÃ ": status_labels[status],
                "Nota": reason,
            }
        )
    return pd.DataFrame(rows)


def render_fingerprint_summary(fingerprint: FermentationFingerprint) -> None:
    if fingerprint.warnings:
        for warning in fingerprint.warnings:
            st.warning(warning)
    st.dataframe(
        build_single_fingerprint_table(fingerprint),
        width="stretch",
        hide_index=True,
        column_config={
            "Gruppo": st.column_config.TextColumn(pinned=True),
            "Parametro": st.column_config.TextColumn(pinned=True),
        },
    )
    render_fingerprint_exports([fingerprint], key_prefix="single_fingerprint")


def fmt_phase_threshold(
    value_h: float | None,
    duration_h: float,
    maximum_growth_percent: float | None,
    threshold_percent: float,
) -> str:
    """Format an observed threshold or its right-censored observation window."""

    if value_h is not None and math.isfinite(float(value_h)):
        return fmt_duration(value_h)
    if (
        maximum_growth_percent is not None
        and math.isfinite(float(maximum_growth_percent))
        and float(maximum_growth_percent) < threshold_percent
    ):
        return f"> {fmt_duration(duration_h)}"
    return "N.A."


def build_phase_diagnostic_figure(
    analysis: pd.DataFrame,
    results: list[PhaseAnalysis],
) -> go.Figure:
    diagnostic = build_thermal_diagnostic(analysis)
    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.09,
        row_heights=[0.64, 0.36],
        subplot_titles=("Temperature smussate", "Cambio di pendenza termica"),
    )
    legend_phase_keys: set[str] = set()
    for result in results:
        definition = result.definition
        fill_color, solid_color = PHASE_VISUAL_STYLES.get(
            definition.key,
            ("rgba(197, 212, 204, 0.14)", "#C5D4CC"),
        )
        figure.add_vrect(
            x0=definition.start_h,
            x1=definition.end_h,
            fillcolor=fill_color,
            line_width=0,
            layer="below",
            annotation_text=f"<b>{definition.label}</b>",
            annotation_position="top left",
            annotation_font_color=solid_color,
            annotation_font_size=12,
            row=1,
            col=1,
            exclude_empty_subplots=False,
        )
        figure.add_vrect(
            x0=definition.start_h,
            x1=definition.end_h,
            fillcolor=fill_color,
            line_width=0,
            layer="below",
            row=2,
            col=1,
            exclude_empty_subplots=False,
        )
        if definition.key not in legend_phase_keys:
            figure.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    marker={"symbol": "square", "size": 12, "color": solid_color},
                    name=f"Fase Â· {definition.label}",
                    legendgroup="phase",
                    hoverinfo="skip",
                ),
                row=1,
                col=1,
                exclude_empty_subplots=False,
            )
            legend_phase_keys.add(definition.key)
        if definition.start_h > 0:
            boundary_label, boundary_dash = phase_boundary_style(definition.key)
            figure.add_vline(
                x=definition.start_h,
                line_width=3,
                line_dash=boundary_dash,
                line_color=solid_color,
                annotation_text=f"<b>{boundary_label}</b>",
                annotation_position="top right",
                annotation_font_color=solid_color,
                row=1,
                col=1,
            )
            figure.add_vline(
                x=definition.start_h,
                line_width=3,
                line_dash=boundary_dash,
                line_color=solid_color,
                row=2,
                col=1,
                exclude_empty_subplots=False,
            )

    trace_specs = (
        (
            "dough_temp_smooth_c",
            "Temperatura impasto",
            "#FF7B72",
            1,
            "Â°C",
            "solid",
        ),
        (
            "ambient_temp_smooth_c",
            "Temperatura ambiente",
            "#79B8FF",
            1,
            "Â°C",
            "solid",
        ),
        (
            "dough_temp_slope_c_h",
            "dT/dt impasto",
            "#FF7B72",
            2,
            "Â°C/h",
            "solid",
        ),
        (
            "ambient_temp_slope_c_h",
            "dT/dt ambiente",
            "#79B8FF",
            2,
            "Â°C/h",
            "solid",
        ),
        (
            "thermal_slope_gap_c_h",
            "Scarto pendenze |Î”dT/dt|",
            "#F1B95E",
            2,
            "Â°C/h",
            "dot",
        ),
    )
    for field, label, color, row, unit, dash in trace_specs:
        if field not in diagnostic or not diagnostic[field].notna().any():
            continue
        figure.add_trace(
            go.Scatter(
                x=diagnostic["elapsed_hours"],
                y=diagnostic[field],
                name=label,
                line={
                    "color": color,
                    "width": 2.3 if row == 1 else 1.8,
                    "dash": dash,
                },
                hovertemplate=f"{label}: %{{y:.2f}} {unit}<extra></extra>",
            ),
            row=row,
            col=1,
        )
    figure.add_hline(
        y=0,
        line_width=1,
        line_color="rgba(197, 212, 204, 0.32)",
        row=2,
        col=1,
    )
    figure.update_yaxes(title_text="Temperatura (Â°C)", row=1, col=1)
    figure.update_yaxes(title_text="dT/dt (Â°C/h)", row=2, col=1)
    figure.update_xaxes(title_text="Ore dall'inizio sessione", row=2, col=1)
    figure.update_layout(
        title="Diagnostica termica dei confini di fase",
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.12, "x": 0},
    )
    return style_figure(figure, height=570)


def add_phase_overlays_to_time_figure(
    figure: go.Figure,
    results: list[PhaseAnalysis],
    session_start: pd.Timestamp,
    *,
    show_phase_legend: bool = False,
) -> go.Figure:
    """Add saved phase bands to a regular datetime Plotly figure."""

    legend_phase_keys: set[str] = set()
    for result in results:
        definition = result.definition
        fill_color, solid_color = PHASE_VISUAL_STYLES.get(
            definition.key,
            ("rgba(197, 212, 204, 0.14)", "#C5D4CC"),
        )
        start = session_start + pd.to_timedelta(definition.start_h, unit="h")
        end = session_start + pd.to_timedelta(definition.end_h, unit="h")
        figure.add_vrect(
            x0=start,
            x1=end,
            fillcolor=fill_color,
            line_width=0,
            layer="below",
            annotation_text=f"<b>{definition.label}</b>",
            annotation_position="top left",
            annotation_font_color=solid_color,
            annotation_font_size=12,
            exclude_empty_subplots=False,
        )
        if show_phase_legend and definition.key not in legend_phase_keys:
            figure.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    marker={"symbol": "square", "size": 12, "color": solid_color},
                    name=f"Fase Â· {definition.label}",
                    legendgroup="phase",
                    hoverinfo="skip",
                )
            )
            legend_phase_keys.add(definition.key)
        if definition.start_h <= 0:
            continue
        boundary_label, boundary_dash = phase_boundary_style(definition.key)
        figure.add_vline(
            x=start,
            line_width=3,
            line_dash=boundary_dash,
            line_color=solid_color,
            annotation_text=f"<b>{boundary_label}</b>",
            annotation_position="top right",
            annotation_font_color=solid_color,
            exclude_empty_subplots=False,
        )
    return figure


def build_phase_results_display(results: list[PhaseAnalysis]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for result in results:
        definition = result.definition
        metrics = result.fingerprint.metrics
        maximum_growth = metrics.maximum_growth_percent
        rows.append(
            {
                "Fase": definition.label,
                "Intervallo sessione": (
                    f"{fmt_duration(definition.start_h)} - "
                    f"{fmt_duration(definition.end_h)}"
                ),
                "Durata osservata": fmt_duration(definition.duration_h),
                "Stato": "Completa" if definition.complete else "In corso",
                "Valore iniziale": fmt_optional(
                    metrics.initial_value, f" {metrics.signal_unit}"
                ),
                "Valore finale": fmt_optional(
                    result.final_value, f" {metrics.signal_unit}"
                ),
                "Crescita osservata": fmt_optional(
                    result.observed_growth_percent, "%", signed=True
                ),
                "t25 locale": fmt_phase_threshold(
                    metrics.t25_h, definition.duration_h, maximum_growth, 25.0
                ),
                "t50 locale": fmt_phase_threshold(
                    metrics.t50_h, definition.duration_h, maximum_growth, 50.0
                ),
                "Raddoppio osservato": fmt_phase_threshold(
                    metrics.t100_h, definition.duration_h, maximum_growth, 100.0
                ),
                "Raddoppio stimato": fmt_duration(result.estimated_doubling_time_h),
                "VelocitÃ  media": fmt_optional(
                    result.mean_growth_rate_value_h,
                    f" {metrics.signal_unit}/h",
                    3,
                ),
                "VelocitÃ  specifica media": fmt_optional(
                    result.mean_specific_growth_rate_h, " 1/h", 4
                ),
                "Temperatura media impasto": fmt_optional(
                    metrics.dough_temp_mean_c, " C", 1
                ),
            }
        )
    return pd.DataFrame(rows)


def render_phase_exports(
    results: list[PhaseAnalysis], *, key_prefix: str, file_stem: str
) -> None:
    export_frame = phase_results_to_dataframe(results)
    with st.container(horizontal=True):
        st.download_button(
            "Esporta fasi CSV",
            data=export_frame.to_csv(index=False, na_rep="").encode("utf-8"),
            file_name=f"{file_stem}.csv",
            mime="text/csv",
            key=f"{key_prefix}_csv",
            icon=":material/download:",
            on_click="ignore",
        )
        st.download_button(
            "Esporta fasi JSON",
            data=phase_results_to_json(results),
            file_name=f"{file_stem}.json",
            mime="application/json",
            key=f"{key_prefix}_json",
            icon=":material/data_object:",
            on_click="ignore",
        )


def render_phase_results(results: list[PhaseAnalysis], *, key_prefix: str) -> None:
    if not results:
        st.info("Nessuna fase analizzabile con la configurazione corrente.")
        return
    st.dataframe(
        build_phase_results_display(results),
        width="stretch",
        hide_index=True,
        column_config={"Fase": st.column_config.TextColumn(pinned=True)},
    )
    st.caption(
        "Un tempo preceduto da > non Ã¨ stato raggiunto nella finestra osservata. "
        "Il raddoppio stimato deriva dalla velocitÃ  specifica media della fase e "
        "non sostituisce un raddoppio realmente osservato."
    )
    render_phase_exports(
        results,
        key_prefix=key_prefix,
        file_stem="fermentation_phases",
    )


def build_phase_comparison_display(results: list[PhaseAnalysis]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    specifications = (
        (
            "Durata osservata",
            "h",
            lambda result: fmt_duration(result.definition.duration_h),
        ),
        (
            "Stato fase",
            "",
            lambda result: (
                "Completa" if result.definition.complete else "In corso"
            ),
        ),
        (
            "Valore iniziale",
            "unitÃ  sessione",
            lambda result: fmt_optional(
                result.fingerprint.metrics.initial_value,
                f" {result.fingerprint.metrics.signal_unit}",
                digits=2,
            ),
        ),
        (
            "Valore finale",
            "unitÃ  sessione",
            lambda result: fmt_optional(
                result.final_value,
                f" {result.fingerprint.metrics.signal_unit}",
                digits=2,
            ),
        ),
        (
            "Crescita osservata",
            "%",
            lambda result: fmt_optional(
                result.observed_growth_percent, digits=2, signed=True
            ),
        ),
        (
            "t25 locale",
            "h",
            lambda result: fmt_phase_threshold(
                result.fingerprint.metrics.t25_h,
                result.definition.duration_h,
                result.fingerprint.metrics.maximum_growth_percent,
                25.0,
            ),
        ),
        (
            "t50 locale",
            "h",
            lambda result: fmt_phase_threshold(
                result.fingerprint.metrics.t50_h,
                result.definition.duration_h,
                result.fingerprint.metrics.maximum_growth_percent,
                50.0,
            ),
        ),
        (
            "Raddoppio osservato",
            "h",
            lambda result: fmt_phase_threshold(
                result.fingerprint.metrics.t100_h,
                result.definition.duration_h,
                result.fingerprint.metrics.maximum_growth_percent,
                100.0,
            ),
        ),
        (
            "Raddoppio stimato",
            "h",
            lambda result: fmt_duration(result.estimated_doubling_time_h),
        ),
        (
            "VelocitÃ  media",
            "unitÃ  sessione/h",
            lambda result: fmt_optional(
                result.mean_growth_rate_value_h,
                f" {result.fingerprint.metrics.signal_unit}/h",
                digits=3,
            ),
        ),
        (
            "VelocitÃ  specifica media",
            "1/h",
            lambda result: fmt_optional(
                result.mean_specific_growth_rate_h, digits=4
            ),
        ),
        (
            "VelocitÃ  massima",
            "unitÃ  sessione/h",
            lambda result: fmt_optional(
                result.fingerprint.metrics.max_growth_rate_value_h,
                f" {result.fingerprint.metrics.signal_unit}/h",
                digits=3,
            ),
        ),
        (
            "Temperatura media impasto",
            "Â°C",
            lambda result: fmt_optional(
                result.fingerprint.metrics.dough_temp_mean_c, digits=1
            ),
        ),
    )
    for label, unit, formatter in specifications:
        row = {"Metrica": label, "UnitÃ ": unit}
        for result in results:
            row[result.fingerprint.metrics.session_id] = formatter(result)
        rows.append(row)
    return pd.DataFrame(rows)


def render_phase_comparison(
    results: list[PhaseAnalysis], *, phase_key: str
) -> None:
    st.dataframe(
        build_phase_comparison_display(results),
        width="stretch",
        hide_index=True,
        column_config={
            "Metrica": st.column_config.TextColumn(pinned=True),
            "UnitÃ ": st.column_config.TextColumn(pinned=True),
        },
    )
    st.caption(
        "Ogni tempo riparte dall'inizio della fase. > indica una soglia non "
        "raggiunta durante la finestra osservata."
    )
    render_phase_exports(
        results,
        key_prefix=f"multi_phase_{phase_key}",
        file_stem=f"fermentation_comparison_{phase_key}",
    )


def build_fingerprint_comparison(
    fingerprints: list[FermentationFingerprint],
) -> tuple[pd.DataFrame, set[str]]:
    signal_units = {fingerprint.metrics.signal_unit for fingerprint in fingerprints}
    rows: list[dict[str, object]] = []
    comparable_labels: set[str] = set()
    for field_name, label, unit, _percentage_allowed in FINGERPRINT_COMPARISON_FIELDS:
        display_unit = (
            f"{next(iter(signal_units))}/h"
            if unit == "signal/h" and len(signal_units) == 1
            else "unitÃ  segnale/h"
            if unit == "signal/h"
            else unit
        )
        row: dict[str, object] = {"Metrica": label, "UnitÃ ": display_unit}
        for fingerprint in fingerprints:
            row[fingerprint.metrics.session_id] = getattr(
                fingerprint.metrics, field_name
            )
        rows.append(row)
        if unit != "signal/h" or len(signal_units) == 1:
            comparable_labels.add(label)
    return pd.DataFrame(rows).set_index("Metrica"), comparable_labels


def build_fingerprint_comparison_display(
    comparison: pd.DataFrame, comparable_labels: set[str]
) -> pd.DataFrame:
    """Build a robust text-only comparison table for the Streamlit UI."""

    display = comparison.reset_index().copy()
    session_columns = [
        column for column in display.columns if column not in {"Metrica", "UnitÃ "}
    ]
    display[session_columns] = display[session_columns].astype(object)

    def format_value(value: object, unit: str) -> str:
        if value is None or pd.isna(value):
            return "N.A."
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return str(value)
        if not math.isfinite(numeric):
            return "N.A."
        if unit == "h":
            return fmt_duration(numeric)
        if unit == "1/h":
            return f"{numeric:.3f}"
        return f"{numeric:.2f}"

    for row_index in display.index:
        metric = str(display.at[row_index, "Metrica"])
        unit = str(display.at[row_index, "UnitÃ "])
        numeric = pd.to_numeric(
            display.loc[row_index, session_columns], errors="coerce"
        ).dropna()
        minimum_column = None
        maximum_column = None
        if (
            metric in comparable_labels
            and len(numeric) >= 2
            and float(numeric.min()) != float(numeric.max())
        ):
            minimum_column = numeric.idxmin()
            maximum_column = numeric.idxmax()

        for column in session_columns:
            formatted = format_value(display.at[row_index, column], unit)
            if column == minimum_column:
                formatted = f"MIN Â· {formatted}"
            elif column == maximum_column:
                formatted = f"MAX Â· {formatted}"
            display.at[row_index, column] = formatted

    return display


def build_reference_difference(
    fingerprints: list[FermentationFingerprint],
    reference_session_id: str,
    target_session_id: str,
) -> pd.DataFrame:
    by_session = {
        fingerprint.metrics.session_id: fingerprint.metrics
        for fingerprint in fingerprints
    }
    reference = by_session[reference_session_id]
    target = by_session[target_session_id]
    signal_units = {reference.signal_unit, target.signal_unit}
    rows: list[dict[str, object]] = []
    for field_name, label, unit, percentage_allowed in FINGERPRINT_COMPARISON_FIELDS:
        if unit == "signal/h" and len(signal_units) > 1:
            continue
        display_unit = (
            f"{reference.signal_unit}/h" if unit == "signal/h" else unit
        )
        reference_value = getattr(reference, field_name)
        target_value = getattr(target, field_name)
        difference = (
            float(target_value) - float(reference_value)
            if reference_value is not None and target_value is not None
            else None
        )
        percentage_difference = (
            difference / abs(float(reference_value)) * 100.0
            if percentage_allowed
            and difference is not None
            and abs(float(reference_value)) > np.finfo(float).eps
            else None
        )
        rows.append(
            {
                "Metrica": label,
                "UnitÃ ": display_unit,
                "Riferimento": reference_value,
                "Confronto": target_value,
                "Differenza": difference,
                "Differenza %": percentage_difference,
            }
        )
    return pd.DataFrame(rows)


def render_multi_fingerprint_summary(
    fingerprints: list[FermentationFingerprint],
) -> None:
    comparison, comparable_labels = build_fingerprint_comparison(fingerprints)
    display_comparison = build_fingerprint_comparison_display(
        comparison, comparable_labels
    )
    low_confidence_sessions = [
        fingerprint.metrics.session_id
        for fingerprint in fingerprints
        if fingerprint.warnings
    ]
    if low_confidence_sessions:
        st.warning(
            "Metriche a bassa confidenza per: "
            + ", ".join(low_confidence_sessions)
            + ". Il JSON esportato include i motivi dettagliati."
        )
    st.caption(
        "MIN e MAX indicano gli estremi tra le sessioni, non quale risultato "
        "sia migliore. N.A. indica un parametro non disponibile."
    )
    st.dataframe(
        display_comparison,
        width="stretch",
        hide_index=True,
        column_config={
            "Metrica": st.column_config.TextColumn(pinned=True),
            "UnitÃ ": st.column_config.TextColumn(pinned=True),
        },
    )
    render_fingerprint_exports(
        fingerprints,
        key_prefix="multi_fingerprint",
    )

    with st.expander("Differenze rispetto a una sessione", expanded=False):
        session_ids = [
            fingerprint.metrics.session_id for fingerprint in fingerprints
        ]
        reference_session_id = st.selectbox(
            "Sessione di riferimento",
            session_ids,
            key="fingerprint_reference_session",
        )
        target_session_id = st.selectbox(
            "Sessione da confrontare",
            [value for value in session_ids if value != reference_session_id],
            key="fingerprint_target_session",
        )
        difference_frame = build_reference_difference(
            fingerprints,
            reference_session_id,
            target_session_id,
        )
        st.dataframe(
            difference_frame,
            width="stretch",
            hide_index=True,
            column_config={
                "Riferimento": st.column_config.NumberColumn(format="%.2f"),
                "Confronto": st.column_config.NumberColumn(format="%.2f"),
                "Differenza": st.column_config.NumberColumn(format="%+.2f"),
                "Differenza %": st.column_config.NumberColumn(format="%+.1f%%"),
            },
        )


def build_admin_info_rows(admin_info: dict[str, object]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key, label, formatter in (
        ("session_id", "Session ID", str),
        ("first_seen", "Primo record", fmt_timestamp),
        ("last_seen", "Ultimo record", fmt_timestamp),
        ("duration_hours", "Durata (h)", lambda value: f"{float(value):.2f}"),
        ("record_count", "Numero record", lambda value: f"{int(value)}"),
        ("sample_count", "Numero campioni temporali", lambda value: f"{int(value)}"),
        ("measurement_count", "Numero measurement", lambda value: f"{int(value)}"),
        ("field_count", "Numero campi", lambda value: f"{int(value)}"),
        ("device_id", "Device ID", str),
        ("schema", "Schema", str),
        ("type", "Tipo", str),
        ("kind", "Classificazione", str),
    ):
        value = admin_info.get(key)
        if value is not None and value != "":
            rows.append((label, formatter(value)))
    return rows


def get_compare_metric_options(analyses: list[pd.DataFrame]) -> list[tuple[str, str]]:
    metric_candidates = [
        ("volume_ml", "Volume"),
        ("dough_height_mm", "Altezza impasto"),
        ("growth_pct", "Crescita (%)"),
        ("temperature_dough_c", "Temperatura impasto"),
        ("temperature_ambient_c", "Temperatura ambiente"),
        ("growth_rate_pct_h", "VelocitÃ  crescita (%/h)"),
        ("growth_accel_pct_h2", "Accelerazione crescita (%/h^2)"),
    ]
    return [
        (name, label)
        for name, label in metric_candidates
        if any(
            isinstance(analysis, pd.DataFrame)
            and name in analysis.columns
            and analysis[name].notna().any()
            for analysis in analyses
        )
    ]


def render_section_title(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="fl-section-title">
            <h2>{title}</h2>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def style_figure(figure: go.Figure, *, height: int = 440) -> go.Figure:
    """Apply one quiet, readable visual language to every Plotly chart."""

    figure.update_layout(
        height=height,
        margin={"l": 24, "r": 24, "t": 64, "b": 24},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, ui-sans-serif, system-ui, sans-serif", "color": "#35453e"},
        title={"font": {"size": 19, "color": "#20332b"}, "x": 0.01},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "bgcolor": "rgba(255,255,255,.72)",
        },
        hoverlabel={"bgcolor": "#ffffff", "font_size": 13},
    )
    figure.update_xaxes(
        showgrid=True,
        gridcolor="rgba(32,51,43,.08)",
        zeroline=False,
        showline=True,
        linecolor="rgba(32,51,43,.16)",
    )
    figure.update_yaxes(
        showgrid=True,
        gridcolor="rgba(32,51,43,.08)",
        zeroline=False,
        showline=False,
    )
    return figure


def render_metadata(
    metadata: dict[str, object], *, show_recipe: bool = True
) -> None:
    metadata_rows = []
    for key, label in (
        ("_time", "Avvio sessione"),
        ("session_id", "ID sessione"),
        ("device_id", "Dispositivo"),
        ("schema", "Schema"),
        ("type", "Tipo record"),
    ):
        if key in metadata and metadata[key] is not None:
            metadata_rows.append((label, str(metadata[key])))

    if metadata_rows:
        st.dataframe(
            pd.DataFrame(metadata_rows, columns=["Informazione", "Valore"]),
            width="stretch",
            hide_index=True,
        )

    if not show_recipe:
        return

    recipe = metadata.get("recipe", {}) if isinstance(metadata, dict) else {}
    recipe_sections = build_recipe_sections(recipe if isinstance(recipe, dict) else None)
    if not recipe_sections:
        st.info("Questa sessione non contiene ancora una ricetta completa nel record di avvio.")
        return

    st.markdown("#### Ricetta")
    for title, rows in recipe_sections:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.dataframe(
                pd.DataFrame(rows, columns=["Parametro", "Valore"]),
                width="stretch",
                hide_index=True,
            )


defaults = InfluxSettings.from_environment()

st.markdown(
    """
    <div class="fl-hero">
        <div class="fl-eyebrow">FermentLab Â· controllo fermentazione</div>
        <h1>Dal sensore a una decisione chiara.</h1>
        <p>Analizza crescita e temperatura dell'impasto, confronta le sessioni e individua subito i cambi di ritmo.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### ðŸ«§ FermentLab")
    st.caption("Pannello locale di analisi")

    lookback_days = st.number_input(
        "Intervallo sessioni",
        min_value=1,
        max_value=3650,
        value=365,
        format="%d",
        help="Numero di giorni passati in cui cercare le sessioni.",
    )
    st.caption("giorni precedenti")
    if st.button("â†»  Aggiorna dati", width="stretch", type="primary"):
        st.cache_data.clear()

    with st.expander("Connessione InfluxDB", expanded=not bool(defaults.token)):
        url = st.text_input("Indirizzo server", value=defaults.url)
        org = st.text_input("Organizzazione", value=defaults.org)
        bucket = st.text_input("Bucket", value=defaults.bucket)
        measurement = st.text_input("Measurement", value=defaults.measurement)
        token_override = st.text_input(
            "Token (override)",
            value="",
            type="password",
            help="Lascia vuoto per usare il token configurato nell'ambiente locale.",
        )
        token = token_override or defaults.token
        if defaults.token:
            st.success("Credenziali locali caricate", icon="âœ…")
        else:
            st.caption("Il token resta nella sessione corrente e non viene salvato.")

    management_enabled = st.toggle(
        "Gestione sessioni",
        value=False,
        help="Apre diagnostica, unione e cancellazione delle sessioni.",
    )
    app_view = "Gestione sessioni" if management_enabled else "Analisi"
    if management_enabled:
        st.caption("Unione e cancellazione richiedono permessi di scrittura.")

if not token:
    render_section_title(
        "Collega il database",
        "Apri â€œConnessione InfluxDBâ€ nella barra laterale e inserisci il token per iniziare.",
    )
    st.info("La configurazione resta locale e il token non viene salvato dall'app.", icon="ðŸ”’")
    st.stop()

try:
    sessions = list_sessions(
        url, org, bucket, token, measurement, int(lookback_days)
    )
except Exception as error:
    st.error(f"Connessione a InfluxDB non riuscita: {error}")
    st.stop()

if sessions.empty:
    st.warning("Nessuna sessione trovata nell'intervallo selezionato.")
    st.stop()

session_labels = {
    row.session_id: f"{row.session_id} Â· {row.last_seen:%Y-%m-%d %H:%M} UTC"
    for row in sessions.itertuples()
}

if app_view == "Gestione sessioni":
    render_section_title(
        "Gestione sessioni",
        "Controlla le anomalie, unisci sessioni spezzate o rimuovi dati non validi.",
    )

    with st.spinner("Carico il catalogo amministrativo delle sessioni..."):
        management_catalog = load_management_catalog(
            url,
            org,
            bucket,
            token,
            measurement,
            int(lookback_days),
            tuple(sessions["session_id"].tolist()),
        )

    if management_catalog.empty:
        st.warning("Nessuna sessione disponibile per la gestione.")
        st.stop()

    filter_col_a, filter_col_b = st.columns([1, 1])
    category_filter = filter_col_a.selectbox(
        "Filtro sessioni",
        ["Tutte", "Solo test", "Solo failed", "Solo sospette", "Test o failed"],
    )
    max_records_filter = filter_col_b.number_input(
        "Mostra anche solo fino a N record",
        min_value=0,
        max_value=1_000_000,
        value=0,
        step=10,
        help="0 disabilita questo filtro.",
    )

    filtered_catalog = management_catalog.copy()
    if category_filter == "Solo test":
        filtered_catalog = filtered_catalog[filtered_catalog["is_test"]]
    elif category_filter == "Solo failed":
        filtered_catalog = filtered_catalog[filtered_catalog["is_failed"]]
    elif category_filter == "Solo sospette":
        filtered_catalog = filtered_catalog[filtered_catalog["is_suspicious"]]
    elif category_filter == "Test o failed":
        filtered_catalog = filtered_catalog[
            filtered_catalog["is_test"] | filtered_catalog["is_failed"]
        ]

    if max_records_filter > 0:
        filtered_catalog = filtered_catalog[
            filtered_catalog["record_count"] <= int(max_records_filter)
        ]

    if filtered_catalog.empty:
        st.info("Nessuna sessione corrisponde ai filtri attuali.")
        st.stop()

    summary_cols = st.columns(4)
    summary_cols[0].metric("Sessioni filtrate", f"{len(filtered_catalog)}")
    summary_cols[1].metric("Sessioni test", f"{int(filtered_catalog['is_test'].sum())}")
    summary_cols[2].metric("Sessioni failed", f"{int(filtered_catalog['is_failed'].sum())}")
    summary_cols[3].metric("Sessioni sospette", f"{int(filtered_catalog['is_suspicious'].sum())}")

    st.dataframe(
        filtered_catalog[
            [
                "session_id",
                "last_seen",
                "duration_hours",
                "record_count",
                "sample_count",
                "kind",
                "reasons",
            ]
        ],
        width="stretch",
        hide_index=True,
    )

    managed_session_id = st.selectbox(
        "Sessione da gestire",
        filtered_catalog["session_id"].tolist(),
        format_func=lambda value: session_labels.get(value, value),
    )
    admin_info = load_session_admin_info(
        url,
        org,
        bucket,
        token,
        measurement,
        managed_session_id,
        int(lookback_days),
    )

    info_tab, merge_tab, delete_tab = st.tabs(
        ["Informazioni", "Unisci sessioni", "Elimina"]
    )

    with info_tab:
        info_rows = build_admin_info_rows(admin_info)
        if info_rows:
            st.dataframe(
                pd.DataFrame(info_rows, columns=["Campo", "Valore"]),
                width="stretch",
                hide_index=True,
            )
        reasons = admin_info.get("reasons", []) if isinstance(admin_info, dict) else []
        if isinstance(reasons, list) and reasons:
            st.caption("Motivi classificazione")
            st.write(", ".join(str(reason) for reason in reasons))
        measurements = admin_info.get("measurements", []) if isinstance(admin_info, dict) else []
        if isinstance(measurements, list) and measurements:
            st.caption("Measurement coinvolti")
            st.write(", ".join(str(item) for item in measurements))
        fields = admin_info.get("fields", []) if isinstance(admin_info, dict) else []
        if isinstance(fields, list) and fields:
            st.caption("Campi trovati")
            st.write(", ".join(str(item) for item in fields))

    with merge_tab:
        merge_targets = [value for value in sessions["session_id"].tolist() if value != managed_session_id]
        if not merge_targets:
            st.info("Serve almeno un'altra sessione per eseguire un merge.")
        else:
            merge_target = st.selectbox(
                "Sessione destinazione",
                merge_targets,
                format_func=lambda value: session_labels.get(value, value),
                key=f"manager_merge_target_{managed_session_id}",
            )
            preview = preview_session_merge(
                url,
                org,
                bucket,
                token,
                measurement,
                managed_session_id,
                merge_target,
                int(lookback_days),
            )
            preview_cols = st.columns(4)
            preview_cols[0].metric("Record sorgente", f"{preview['source_record_count']}")
            preview_cols[1].metric("Record target", f"{preview['target_record_count']}")
            preview_cols[2].metric("Overlap punti", f"{preview['overlap_point_count']}")
            preview_cols[3].metric("Nuovi punti stimati", f"{preview['new_point_count']}")
            st.caption(
                f"Timestamp sovrapposti: {preview['overlap_timestamp_count']}. "
                "L'overlap confronta timestamp, measurement, field e tag, ignorando il session_id."
            )
            if preview.get("would_create_target"):
                st.info("La sessione destinazione oggi non esiste ancora: il merge la creerÃ .")

            delete_source_after_merge = st.checkbox(
                "Elimina la sessione sorgente dopo la copia",
                value=False,
                key=f"manager_merge_delete_source_{managed_session_id}",
            )
            merge_phrase = f"MERGE {managed_session_id} -> {merge_target}"
            merge_confirmation = st.text_input(
                "Conferma merge",
                value="",
                help=f"Scrivi esattamente: {merge_phrase}",
                key=f"manager_merge_confirmation_{managed_session_id}",
            )
            if st.button(
                "Unisci le sessioni",
                key=f"manager_merge_button_{managed_session_id}",
                type="primary",
            ):
                if merge_confirmation.strip() != merge_phrase:
                    st.error("Conferma non valida. Copia la frase completa prima di procedere.")
                else:
                    with st.spinner("Merge in corso su InfluxDB..."):
                        result = merge_sessions_influx(
                            url,
                            org,
                            bucket,
                            token,
                            measurement,
                            managed_session_id,
                            merge_target,
                            int(lookback_days),
                            delete_source_after_merge,
                        )
                    st.cache_data.clear()
                    st.success(
                        "Merge completato: "
                        f"copiati {result['copied_records']} record in {result['target_session_id']}."
                    )
                    st.rerun()

    with delete_tab:
        delete_phrase = f"DELETE {managed_session_id}"
        delete_confirmation = st.text_input(
            "Conferma delete",
            value="",
            help=f"Scrivi esattamente: {delete_phrase}",
            key=f"manager_delete_confirmation_{managed_session_id}",
        )
        st.warning(
            "Questa operazione elimina definitivamente tutti i record con questo session_id dal bucket InfluxDB."
        )
        if st.button(
            "Elimina definitivamente",
            key=f"manager_delete_button_{managed_session_id}",
            type="primary",
        ):
            if delete_confirmation.strip() != delete_phrase:
                st.error("Conferma non valida. Copia la frase completa prima di procedere.")
            else:
                with st.spinner("Eliminazione sessione in corso..."):
                    deleted_summary = delete_session_from_influx(
                        url,
                        org,
                        bucket,
                        token,
                        measurement,
                        managed_session_id,
                        int(lookback_days),
                    )
                st.cache_data.clear()
                st.success(
                    "Sessione eliminata: "
                    f"rimossi {deleted_summary['record_count']} record da InfluxDB."
                )
                st.rerun()

    st.stop()

render_section_title(
    "Esplora le sessioni",
    "Scegli una fermentazione oppure metti piÃ¹ prove sullo stesso asse temporale.",
)
analysis_mode = st.segmented_control(
    "ModalitÃ  di analisi",
    ["Single Session", "Compare Sessions"],
    default="Single Session",
    format_func=lambda value: {
        "Single Session": "Sessione singola",
        "Compare Sessions": "Confronta sessioni",
    }[value],
    width="stretch",
)

if analysis_mode == "Single Session":
    session_id = st.selectbox(
        "Sessione da analizzare",
        sessions["session_id"].tolist(),
        format_func=lambda value: session_labels[value],
    )
    single_section = st.segmented_control(
        "Sezione",
        ["Sintesi", "Fasi", "Grafici", "Dettagli"],
        default="Sintesi",
        required=True,
        format_func=lambda value: {
            "Sintesi": ":material/table_rows: Sintesi",
            "Fasi": ":material/timeline: Fasi",
            "Grafici": ":material/show_chart: Grafici",
            "Dettagli": ":material/description: Dettagli",
        }[value],
        key="single_section",
        width="stretch",
    )
else:
    if "compare_offsets" not in st.session_state:
        st.session_state.compare_offsets = {}
    for selected_session in sessions["session_id"].tolist():
        st.session_state.compare_offsets.setdefault(selected_session, 0.0)
    selected_session_ids = st.multiselect(
        "Sessioni da confrontare",
        sessions["session_id"].tolist(),
        format_func=lambda value: session_labels[value],
        placeholder="Seleziona almeno due sessioni",
    )
    if len(selected_session_ids) < 2:
        st.info("Seleziona almeno due sessioni per la modalitÃ  Compare Sessions.")
        st.stop()
    compare_section = st.segmented_control(
        "Sezione",
        ["Tabella", "Curve", "Correlazione"],
        default="Tabella",
        required=True,
        format_func=lambda value: {
            "Tabella": ":material/table_rows: Tabella",
            "Curve": ":material/show_chart: Curve",
            "Correlazione": ":material/scatter_plot: Correlazione",
        }[value],
        key="compare_section",
        width="stretch",
    )

with st.expander(
    "Impostazioni avanzate",
    expanded=False,
    icon=":material/tune:",
):
    st.caption(
        "I valori predefiniti sono adatti alla maggior parte delle sessioni. "
        "Modificali solo per correggere rumore, picchi o una baseline instabile."
    )
    st.markdown("**Segnale e baseline**")
    col_a, col_b = st.columns(2)
    smoothing_minutes = col_a.slider(
        "Filtro mediano", 1, 30, 5,
        help="Riduce il rumore preservando i cambi di tendenza.",
    )
    post_smoothing_minutes = col_b.slider(
        "Smussatura finale", 0, 30, 3,
        help="Rende piÃ¹ leggibile la curva elaborata.",
    )
    col_c, col_d = st.columns(2)
    despike_window_minutes = col_c.slider(
        "Rimozione picchi (min)", 0, 20, 3
    )
    despike_sigma = col_d.slider(
        "SensibilitÃ  picchi (sigma)", 0.0, 8.0, 3.5, 0.5
    )
    col_e, col_f = st.columns(2)
    baseline_offset_minutes = col_e.slider(
        "Ignora l'avvio (min)", 0, 180, 0, 5,
        help="Utile se il campione non era stabile al momento dello START.",
    )
    baseline_minutes = col_f.slider("Finestra baseline (min)", 1, 30, 5)

    st.markdown("**Dinamica ed eventi**")
    col_g, col_h = st.columns(2)
    rate_window_minutes = col_g.slider(
        "Finestra velocitÃ  (min)", 5, 120, 30, 5
    )
    acceleration_window_minutes = col_h.slider(
        "Finestra accelerazione (min)", 10, 180, 60, 5
    )
    minimum_slope_points = st.slider(
        "Campioni minimi per la stima", 3, 15, 5
    )
    st.caption(
        "Le soglie controllano lag, plateau, fase attiva e collasso; "
        "valgono solo per eventi persistenti."
    )
    phase_col_a, phase_col_b = st.columns(2)
    lag_rate_percent = phase_col_a.slider(
        "Soglia lag e fase attiva (%)", 5, 50, 20, 5,
        help="Percentuale di vmax che identifica crescita significativa.",
    )
    plateau_rate_percent = phase_col_b.slider(
        "Soglia plateau (%)", 2, 30, 10, 1,
        help="Il plateau richiede una velocitÃ  inferiore a questa quota di vmax.",
    )
    phase_col_c, phase_col_d = st.columns(2)
    lag_persistence_minutes = phase_col_c.slider(
        "Persistenza lag (min)", 5, 120, 15, 5
    )
    plateau_persistence_minutes = phase_col_d.slider(
        "Persistenza plateau (min)", 10, 180, 30, 5
    )
    phase_col_e, phase_col_f = st.columns(2)
    collapse_loss_percent = phase_col_e.slider(
        "Perdita minima collasso (%)", 1, 30, 5, 1
    )
    collapse_persistence_minutes = phase_col_f.slider(
        "Persistenza collasso (min)", 10, 180, 30, 5
    )

fingerprint_config = FermentationAnalysisConfig(
    derivative_window_minutes=float(rate_window_minutes),
    minimum_derivative_points=max(5, int(minimum_slope_points)),
    lag_rate_fraction=float(lag_rate_percent) / 100.0,
    lag_persistence_minutes=float(lag_persistence_minutes),
    plateau_rate_fraction=float(plateau_rate_percent) / 100.0,
    plateau_persistence_minutes=float(plateau_persistence_minutes),
    collapse_loss_percent=float(collapse_loss_percent),
    collapse_persistence_minutes=float(collapse_persistence_minutes),
    active_rate_fraction=float(lag_rate_percent) / 100.0,
)

if analysis_mode == "Single Session":
    try:
        raw = load_session(
            url,
            org,
            bucket,
            token,
            measurement,
            session_id,
            int(lookback_days),
        )
        session_metadata = load_session_metadata(
            url,
            org,
            bucket,
            token,
            measurement,
            session_id,
            int(lookback_days),
        )
        analysis = analyze_session(
            raw,
            smoothing_minutes=smoothing_minutes,
            post_smoothing_minutes=post_smoothing_minutes,
            despike_window_minutes=despike_window_minutes,
            despike_sigma=despike_sigma,
            baseline_offset_minutes=baseline_offset_minutes,
            baseline_minutes=baseline_minutes,
            rate_window_minutes=rate_window_minutes,
            acceleration_window_minutes=acceleration_window_minutes,
            minimum_slope_points=minimum_slope_points,
        )
        summary = summarize_session(analysis)

        single_view = st.segmented_control(
            "Vista grafico",
            ["Serie temporali", "Correlazione 2 variabili"],
            default="Serie temporali",
            format_func=lambda value: {
                "Serie temporali": "Andamento nel tempo",
                "Correlazione 2 variabili": "Correlazione",
            }[value],
        )
        if single_view == "Correlazione 2 variabili":
            metric_options = get_compare_metric_options([analysis])
            if not metric_options:
                st.info("Le metriche disponibili per questo dataframe non permettono una correlazione utile.")
            else:
                metric_names = [name for name, _label in metric_options]
                x_metric = st.selectbox(
                    "Variabile X",
                    metric_names,
                    format_func=lambda value: next(
                        label for name, label in metric_options if name == value
                    ),
                    index=0,
                )
                y_metric = st.selectbox(
                    "Variabile Y",
                    metric_names,
                    format_func=lambda value: next(
                        label for name, label in metric_options if name == value
                    ),
                    index=1 if len(metric_names) > 1 else 0,
                )
                if x_metric == y_metric:
                    st.info("Scegli due variabili distinte per il grafico di correlazione.")
    except Exception as error:
        st.error(f"Analisi della sessione non riuscita: {error}")
        st.stop()
    try:
        single_phase_annotation = load_phase_annotation(session_id)
        single_phase_annotation_error = None
    except ValueError as error:
        single_phase_annotation = None
        single_phase_annotation_error = str(error)
    single_phase_proposal = detect_thermal_phase_proposal(analysis, session_id)
    single_saved_phase_results: list[PhaseAnalysis] = []
    single_saved_phase_error: str | None = None
    if single_phase_annotation is not None:
        try:
            single_saved_phase_results = analyze_protocol_phases(
                analysis,
                session_id,
                single_phase_annotation,
                fingerprint_config,
                baseline_minutes=baseline_minutes,
            )
        except ValueError as error:
            single_saved_phase_error = str(error)
else:
    compare_analyses: list[dict[str, object]] = []
    compare_errors: list[str] = []
    offset_hours: dict[str, float] = {}
    compare_metadata: dict[str, dict[str, object]] = {}
    compare_phase_results: dict[str, list[PhaseAnalysis]] = {}
    compare_phase_errors: list[str] = []

    if compare_section == "Curve":
        with st.expander("Offset temporali", expanded=True):
            for session_name in selected_session_ids:
                current_offset = float(
                    st.session_state.compare_offsets.get(session_name, 0.0)
                )
                col_offset_h, col_offset_m = st.columns(2)
                offset_hours_value = col_offset_h.number_input(
                    f"Offset Â· {session_name} (h)",
                    min_value=-1000.0,
                    max_value=1000.0,
                    value=current_offset,
                    step=0.25,
                    format="%.2f",
                    key=f"offset_h_{session_name}",
                )
                offset_minutes_value = col_offset_m.number_input(
                    f"Offset Â· {session_name} (min)",
                    min_value=-60000.0,
                    max_value=60000.0,
                    value=current_offset * 60.0,
                    step=1.0,
                    format="%.0f",
                    key=f"offset_m_{session_name}",
                )
                offset_hours_value = (
                    float(offset_hours_value)
                    + float(offset_minutes_value) / 60.0
                )
                st.session_state.compare_offsets[session_name] = float(
                    offset_hours_value
                )
                offset_hours[session_name] = float(offset_hours_value)
        alignment_event = st.text_input(
            "Etichetta dell'evento di allineamento",
            value="Evento di riferimento",
        )
    else:
        offset_hours = {
            session_name: 0.0
            for session_name in selected_session_ids
        }
        alignment_event = "Evento di riferimento"

    for session_name in selected_session_ids:
        try:
            raw = load_session(
                url,
                org,
                bucket,
                token,
                measurement,
                session_name,
                int(lookback_days),
            )
            analysis = analyze_session(
                raw,
                smoothing_minutes=smoothing_minutes,
                post_smoothing_minutes=post_smoothing_minutes,
                despike_window_minutes=despike_window_minutes,
                despike_sigma=despike_sigma,
                baseline_offset_minutes=baseline_offset_minutes,
                baseline_minutes=baseline_minutes,
                rate_window_minutes=rate_window_minutes,
                acceleration_window_minutes=acceleration_window_minutes,
                minimum_slope_points=minimum_slope_points,
            )
            transformed = add_relative_time(
                analysis,
                float(offset_hours[session_name]) * 3_600_000.0,
            )
            metadata = load_session_metadata(
                url,
                org,
                bucket,
                token,
                measurement,
                session_name,
                int(lookback_days),
            )
            compare_metadata[session_name] = metadata if isinstance(metadata, dict) else {}
            compare_analyses.append(
                {"session_id": session_name, "analysis": transformed}
            )
            compare_fingerprints.append(fingerprint)
            try:
                phase_annotation = load_phase_annotation(session_name)
                compare_phase_results[session_name] = (
                    analyze_protocol_phases(
                        analysis,
                        session_name,
                        phase_annotation,
                        fingerprint_config,
                        baseline_minutes=baseline_minutes,
                    )
                    if phase_annotation is not None
                    else []
                )
            except (ValueError, OSError) as phase_error:
                compare_phase_results[session_name] = []
                compare_phase_errors.append(
                    f"{session_name}: annotazione fasi non disponibile ({phase_error})"
                )
        except Exception as error:
            compare_errors.append(f"{session_name}: {error}")

    if compare_errors:
        for error_text in compare_errors:
            st.warning(error_text)
    if compare_phase_errors:
        for error_text in compare_phase_errors:
            st.warning(error_text)

    if not compare_analyses:
        st.error("Nessuna sessione comparabile Ã¨ stata caricata.")
        st.stop()

    if compare_section == "Tabella":
        render_section_title(
            "Confronto dei parametri",
            "Le metriche sono calcolate sulla timeline originale di ogni sessione. "
            "I valori mancanti restano esplicitamente N.A.",
        )
        results_by_phase: dict[str, list[PhaseAnalysis]] = {
            "cooling": [],
            "cold": [],
            "settling": [],
            "warm_stable": [],
            "post_fridge": [],
            "ambient": [],
        }
        for session_results in compare_phase_results.values():
            for phase_result in session_results:
                results_by_phase.setdefault(phase_result.definition.key, []).append(
                    phase_result
                )
        available_phase_keys = [
            phase_key
            for phase_key in (
                "cooling",
                "cold",
                "settling",
                "warm_stable",
                "post_fridge",
                "ambient",
            )
            if results_by_phase.get(phase_key)
        ]
        scope_options = ["global", *available_phase_keys]
        scope_labels = {
            "global": "Sessione completa",
            "cooling": "Raffreddamento",
            "cold": "Freddo stabile",
            "settling": "Assestamento termico",
            "warm_stable": "Ambiente stabilizzato",
            "post_fridge": "Post-frigo (vecchia configurazione)",
            "ambient": "Temperatura ambiente",
        }
        comparison_scope = st.selectbox(
            "Periodo da confrontare",
            scope_options,
            index=0,
            format_func=lambda value: scope_labels[value],
            key="comparison_phase_scope",
            width="stretch",
        )
        if comparison_scope == "global":
            render_multi_fingerprint_summary(compare_fingerprints)
        else:
            selected_phase_results = results_by_phase[comparison_scope]
            included_sessions = {
                result.fingerprint.metrics.session_id
                for result in selected_phase_results
            }
            excluded_sessions = [
                session_name
                for session_name in selected_session_ids
                if session_name not in included_sessions
            ]
            st.subheader(f"Confronto locale: {scope_labels[comparison_scope]}")
            st.caption(
                "Baseline e orologio sono ricalcolati dall'inizio di questa fase; "
                "le metriche globali non vengono modificate."
            )
            if excluded_sessions:
                st.info(
                    "Escluse perchÃ© prive di questa fase: "
                    + ", ".join(excluded_sessions)
                )
            render_phase_comparison(
                selected_phase_results,
                phase_key=comparison_scope,
            )
        if not available_phase_keys:
            st.info(
                "Per confrontare le fasi, configurale prima nella vista TESTO "
                "di ciascuna sessione."
            )
        with st.expander("Metadati sessioni", expanded=False):
            for session_name in selected_session_ids:
                metadata = compare_metadata.get(session_name, {})
                st.markdown(f"#### {session_name}")
                if not metadata:
                    st.caption("Nessun metadato disponibile per questa sessione.")
                    continue
                render_metadata(metadata)
        st.stop()

    if compare_section == "Curve":
        render_section_title(
            "Curve di confronto",
            "Allinea le timeline con gli offset senza modificare metriche o dati.",
        )
    else:
        render_section_title(
            "Correlazione",
            "Confronta direttamente due variabili per tutte le sessioni selezionate.",
        )

    metric_options = get_compare_metric_options(
        [entry["analysis"] for entry in compare_analyses]
    )
    if not metric_options:
        st.info("Le sessioni non hanno metriche comparabili con i dati attuali.")
        st.stop()

    metric_names = [name for name, _label in metric_options]

    compare_view = (
        "Serie temporali"
        if compare_section == "Curve"
        else "Correlazione 2 variabili"
    )

    if compare_view == "Serie temporali":
        compare_metrics = st.multiselect(
            "Metriche da confrontare",
            metric_names,
            default=[metric_names[0]] if metric_names else [],
            format_func=lambda value: next(
                label for name, label in metric_options if name == value
            ),
        )
        if not compare_metrics:
            st.info("Seleziona almeno una metrica per la vista temporale.")
            st.stop()
    else:
        compare_metrics = []

    if compare_view == "Correlazione 2 variabili":
        x_metric = st.selectbox(
            "Variabile X",
            metric_names,
            format_func=lambda value: next(
                label for name, label in metric_options if name == value
            ),
            index=0,
        )
        y_metric = st.selectbox(
            "Variabile Y",
            metric_names,
            format_func=lambda value: next(
                label for name, label in metric_options if name == value
            ),
            index=1 if len(metric_names) > 1 else 0,
        )
        if x_metric == y_metric:
            st.info("Scegli due variabili distinte per il grafico di correlazione.")
            st.stop()

    if compare_view == "Correlazione 2 variabili":
        compare_figure = go.Figure()
        for entry in compare_analyses:
            analysis = entry["analysis"]
            if x_metric not in analysis.columns or y_metric not in analysis.columns:
                continue
            x_values = analysis[x_metric]
            y_values = analysis[y_metric]
            valid = x_values.notna() & y_values.notna()
            if not valid.any():
                continue
            compare_figure.add_trace(
                go.Scatter(
                    x=x_values[valid],
                    y=y_values[valid],
                    mode="lines+markers",
                    name=str(entry["session_id"]),
                    hovertemplate=(
                        f"{entry['session_id']}<br>{x_metric} = %{{x:.3f}}"
                        f"<br>{y_metric} = %{{y:.3f}}<extra></extra>"
                    ),
                )
            )

        if len(compare_figure.data) == 0:
            st.info("Nessuna curva disponibile per la correlazione selezionata.")
            st.stop()

        compare_figure.update_layout(
            title="Correlazione tra due variabili",
            xaxis_title=next(
                label for name, label in metric_options if name == x_metric
            ),
            yaxis_title=next(
                label for name, label in metric_options if name == y_metric
            ),
            hovermode="closest",
        )
        style_figure(compare_figure)
        st.plotly_chart(
            compare_figure, width="stretch", config={"displaylogo": False}
        )
    else:
        metric_labels = {
            name: label for name, label in metric_options if name in compare_metrics
        }
        compare_figure = make_subplots(
            rows=1,
            cols=len(compare_metrics),
            subplot_titles=[metric_labels[metric] for metric in compare_metrics],
            shared_yaxes=False,
        )
        for metric_index, metric_name in enumerate(compare_metrics, start=1):
            for entry in compare_analyses:
                analysis = entry["analysis"]
                offset_hours_value = float(st.session_state.compare_offsets.get(str(entry["session_id"]), 0.0))
                if metric_name not in analysis.columns:
                    continue
                values = analysis[metric_name]
                if not values.notna().any():
                    continue
                compare_figure.add_trace(
                    go.Scatter(
                        x=analysis["t_relative_h"],
                        y=values,
                        mode="lines+markers",
                        name=f"{entry['session_id']} Â· {metric_labels[metric_name]}",
                        hovertemplate=(
                            f"{entry['session_id']}<br>offset = {offset_hours_value:+.2f} h<br>{metric_labels[metric_name]} = %{{y:.3f}}<br>t = %{{x:.2f}} h<extra></extra>"
                        ),
                    ),
                    row=1,
                    col=metric_index,
                )
            compare_figure.add_vline(
                x=0,
                line_dash="dash",
                line_color="rgba(90, 90, 90, 0.8)",
                annotation_text=alignment_event if metric_index == 1 else "",
                annotation_position="top left",
                row=1,
                col=metric_index,
            )
            compare_figure.update_xaxes(title_text="Tempo relativo (h)", row=1, col=metric_index)
            compare_figure.update_yaxes(
                title_text=metric_labels[metric_name],
                row=1,
                col=metric_index,
            )

        if len(compare_figure.data) == 0:
            st.info("Nessuna curva disponibile per le metriche selezionate.")
            st.stop()

        compare_figure.update_layout(
            title="Confronto sessioni su tempo relativo",
            hovermode="x unified",
        )
        style_figure(compare_figure, height=460)
        st.plotly_chart(
            compare_figure, width="stretch", config={"displaylogo": False}
        )

    with st.expander("Metadati sessioni", expanded=False):
        for session_name in selected_session_ids:
            metadata = compare_metadata.get(session_name, {})
            st.markdown(f"#### {session_name}")
            if not metadata:
                st.caption("Nessun metadato disponibile per questa sessione.")
                continue
            render_metadata(metadata)
    st.stop()

if analysis_mode == "Single Session":
    render_section_title(
        "Risultati",
        f"Sintesi della sessione {session_id} con i parametri di analisi correnti.",
    )
    metric_row_primary = st.columns(4)
    metric_row_primary[0].metric("Durata", fmt_number(summary.duration_hours, " h"))
    metric_row_primary[1].metric(
        "Crescita attuale", fmt_number(summary.current_growth_pct, "%")
    )
    metric_row_primary[2].metric(
        f"{summary.signal_label} attuale",
        fmt_number(summary.current_value, f" {summary.signal_unit}"),
    )
    metric_row_primary[3].metric(
        "VelocitÃ  attuale",
        fmt_number(summary.current_growth_rate_pct_h, "%/h"),
    )

    metric_row_secondary = st.columns(3)
    metric_row_secondary[0].metric(
        "Crescita massima", fmt_number(summary.maximum_growth_pct, "%")
    )
    metric_row_secondary[1].metric(
        "Rapporto attuale / iniziale",
        fmt_number(summary.current_ratio_x, "Ã—", 2),
    )
    metric_row_secondary[2].metric(
        "Accelerazione",
        fmt_number(summary.current_growth_accel_pct_h2, "%/hÂ²"),
    )

    if summary.signal_field == "dough_height_mm":
        st.warning(
            "Questa sessione non contiene `volume_ml`: la crescita percentuale Ã¨ "
            "calcolata dall'altezza. Configurando la sezione del contenitore nel "
            "firmware, le sessioni future includeranno anche il volume."
        )
    if analysis["growth_pct"].min() < -5:
        st.info(
            "Il segnale scende oltre il 5% dopo la baseline. Se il campione non era "
            "ancora stabile allo START, aumenta â€˜Ignora i primi minutiâ€™."
        )

    volume_figure = make_subplots(specs=[[{"secondary_y": True}]])
    volume_figure.add_trace(
        go.Scatter(
            x=analysis.index,
            y=analysis[summary.signal_field],
            name=f"{summary.signal_label} grezza",
            line={"color": "rgba(120, 130, 125, 0.35)", "width": 1},
        ),
        secondary_y=False,
    )
    if "signal_despiked" in analysis and despike_window_minutes > 0 and despike_sigma > 0:
        volume_figure.add_trace(
            go.Scatter(
                x=analysis.index,
                y=analysis["signal_despiked"],
                name=f"{summary.signal_label} ripulita",
                line={"color": "rgba(70, 110, 160, 0.6)", "width": 1.5},
            ),
            secondary_y=False,
        )
    volume_figure.add_trace(
        go.Scatter(
            x=analysis.index,
            y=analysis["signal_smooth"],
            name=f"{summary.signal_label} filtrata",
            line={"color": "#2E8B57", "width": 3},
        ),
        secondary_y=False,
    )
    volume_figure.add_trace(
        go.Scatter(
            x=analysis.index,
            y=analysis["growth_pct"],
            name="Crescita",
            line={"color": "#D18B2C", "width": 2},
        ),
        secondary_y=True,
    )
    volume_figure.update_yaxes(
        title_text=f"{summary.signal_label} ({summary.signal_unit})", secondary_y=False
    )
    volume_figure.update_yaxes(title_text="Crescita (%)", secondary_y=True)
    volume_figure.update_layout(
        title=f"{summary.signal_label} e crescita", hovermode="x unified"
    )
    style_figure(volume_figure)

    temperature_figure = make_subplots(specs=[[{"secondary_y": True}]])
    if "temperature_dough_c" in analysis:
        temperature_figure.add_trace(
            go.Scatter(
                x=analysis.index,
                y=analysis["temperature_dough_c"],
                name="Temperatura impasto",
                line={"color": "#B94A48", "width": 2},
            ),
            secondary_y=False,
        )
    if "temperature_ambient_c" in analysis:
        temperature_figure.add_trace(
            go.Scatter(
                x=analysis.index,
                y=analysis["temperature_ambient_c"],
                name="Temperatura ambiente",
                line={"color": "#5677A6", "width": 2},
            ),
            secondary_y=False,
        )
    temperature_figure.add_trace(
        go.Scatter(
            x=analysis.index,
            y=analysis["growth_rate_pct_h"],
            name="VelocitÃ  crescita",
            line={"color": "#6E4BA3", "width": 2},
        ),
        secondary_y=True,
    )
    temperature_figure.add_trace(
        go.Scatter(
            x=analysis.index,
            y=analysis["growth_accel_pct_h2"],
            name="Accelerazione crescita",
            line={"color": "#AA4C8F", "width": 2, "dash": "dot"},
        ),
        secondary_y=True,
    )
    temperature_figure.update_yaxes(title_text="Temperatura (Â°C)", secondary_y=False)
    temperature_figure.update_yaxes(
        title_text="VelocitÃ  (%/h) e accelerazione (%/h^2)", secondary_y=True
    )
    temperature_figure.update_layout(
        title="Temperatura e velocitÃ  di crescita", hovermode="x unified"
    )
    style_figure(temperature_figure)

    chart_tab, dynamics_tab, details_tab, data_tab = st.tabs(
        ["Andamento", "Temperatura e dinamica", "Ricetta e dettagli", "Dati"]
    )
    derived_series = (
        (
            "growth_rate_value_h",
            f"VelocitÃ  ({summary.signal_unit}/h)",
            "#69D7A0",
            1,
        ),
        ("specific_growth_rate_h", "VelocitÃ  specifica (1/h)", "#C99AFF", 2),
        ("delta_t_c", "Î”T (Â°C)", "#F1B95E", 3),
    )
    for field_name, label, color, row in derived_series:
        if field_name not in analysis or not analysis[field_name].notna().any():
            continue
        derived_figure.add_trace(
            go.Scatter(
                x=analysis.index,
                y=analysis[field_name],
                name=label,
                line={"color": color, "width": 2},
                hovertemplate=f"{label}: %{{y:.3f}}<extra></extra>",
            ),
            row=row,
            col=1,
        )
        derived_figure.add_hline(
            y=0,
            line_width=1,
            line_color="rgba(197, 212, 204, 0.25)",
            row=row,
            col=1,
        )
    derived_figure.update_yaxes(
        title_text=f"{summary.signal_unit}/h", row=1, col=1
    )
    derived_figure.update_yaxes(title_text="1/h", row=2, col=1)
    derived_figure.update_yaxes(title_text="Â°C", row=3, col=1)
    derived_figure.update_xaxes(title_text="Tempo sessione", row=3, col=1)
    derived_figure.update_layout(
        title="Curve quantitative derivate",
        hovermode="x unified",
    )
    style_figure(derived_figure, height=760)

    if single_section == "Sintesi":
        with st.container():
            st.subheader("Parametri della lievitazione")
            st.caption(
                "Fingerprint quantitativo calcolato sulla timeline originale della sessione."
            )
            render_fingerprint_summary(fingerprint)

    elif single_section == "Fasi":
        with st.container():
            st.subheader("Protocollo e metriche locali")
            st.caption(
                "La sessione Influx resta intatta. Salviamo soltanto il confine "
                "di fase in un file JSON locale separato, con backup automatico."
            )
            if single_phase_annotation_error:
                st.warning(single_phase_annotation_error)

            proposed_annotation = single_phase_proposal.annotation
            initial_annotation = single_phase_annotation or proposed_annotation
            saved_protocol = (
                initial_annotation.protocol
                if initial_annotation is not None
                else "unclassified"
            )
            phase_protocol = st.segmented_control(
                "Protocollo della sessione",
                ["unclassified", "ambient", "fridge_to_ambient"],
                default=saved_protocol,
                required=True,
                format_func=lambda value: {
                    "unclassified": "Non classificata",
                    "ambient": "Sempre a temperatura ambiente",
                    "fridge_to_ambient": "Frigo, poi temperatura ambiente",
                }[value],
                key=f"phase_protocol_v3_{session_id}",
                width="stretch",
            )
            if single_phase_annotation is None and proposed_annotation is not None:
                with st.container(border=True):
                    st.markdown("**Proposta automatica Â· non salvata**")
                    st.caption(
                        f"Confidenza {single_phase_proposal.confidence:.0%}. "
                        "Controlla linee e fasce; il file locale nasce soltanto "
                        "quando premi Salva."
                    )
                    for note in single_phase_proposal.notes:
                        st.markdown(f"- {note}")
            elif single_phase_annotation is None and proposed_annotation is None:
                st.info(" ".join(single_phase_proposal.notes))

            active_phase_annotation: PhaseAnnotation | None = None
            cold_stable_h: float | None = None
            fridge_exit_h: float | None = None
            warm_stable_h: float | None = None
            if phase_protocol == "fridge_to_ambient":
                session_duration_h = float(
                    (analysis.index[-1] - analysis.index[0]).total_seconds()
                    / 3600.0
                )
                default_exit_h = (
                    float(initial_annotation.fridge_exit_h)
                    if initial_annotation is not None
                    and initial_annotation.fridge_exit_h is not None
                    else min(24.0, max(0.25, session_duration_h / 2.0))
                )
                starts_cold = st.toggle(
                    "La sessione parte giÃ  a freddo stabile",
                    value=(
                        initial_annotation is None
                        or initial_annotation.cold_stable_h is None
                    ),
                    key=f"phase_starts_cold_v3_{session_id}",
                    help=(
                        "Disattiva se all'inizio si vede il raffreddamento: comparirÃ  "
                        "un confine separato per l'inizio del freddo stabile."
                    ),
                )
                boundary_columns = st.columns(3)
                if not starts_cold:
                    default_cold_h = (
                        float(initial_annotation.cold_stable_h)
                        if initial_annotation is not None
                        and initial_annotation.cold_stable_h is not None
                        else max(0.01, min(default_exit_h / 3.0, 2.0))
                    )
                    cold_stable_h = float(
                        boundary_columns[0].number_input(
                            "1 Â· Freddo stabilizzato (h)",
                            min_value=0.01,
                            max_value=10000.0,
                            value=default_cold_h,
                            step=0.25,
                            format="%.2f",
                            key=f"phase_cold_stable_v3_{session_id}",
                            help="Qui termina il raffreddamento e inizia il freddo stabile.",
                        )
                    )
                else:
                    boundary_columns[0].caption(
                        "La fase iniziale Ã¨ trattata direttamente come freddo stabile."
                    )
                fridge_exit_h = float(
                    boundary_columns[1].number_input(
                        "2 Â· Uscita dal frigo (h)",
                        min_value=0.01,
                        max_value=10000.0,
                        value=default_exit_h,
                        step=0.25,
                        format="%.2f",
                        key=f"phase_fridge_exit_v3_{session_id}",
                        help=(
                            "Primo aumento persistente della temperatura ambiente: "
                            "qui termina il Freddo e inizia l'Assestamento."
                        ),
                    )
                )
                settling_open = st.toggle(
                    "L'impasto Ã¨ ancora in assestamento alla fine",
                    value=(
                        initial_annotation is None
                        or initial_annotation.warm_stable_h is None
                    ),
                    key=f"phase_settling_open_v3_{session_id}",
                    help=(
                        "Mantieni attivo finchÃ© la temperatura dell'impasto continua "
                        "a salire: non verrÃ  inventata una fase calda stabile."
                    ),
                )
                if not settling_open:
                    default_stable_h = (
                        float(initial_annotation.warm_stable_h)
                        if initial_annotation is not None
                        and initial_annotation.warm_stable_h is not None
                        else fridge_exit_h
                        + max(1.0, (session_duration_h - fridge_exit_h) / 2.0)
                    )
                    warm_stable_h = float(
                        boundary_columns[2].number_input(
                            "3 Â· Impasto stabilizzato (h)",
                            min_value=0.02,
                            max_value=10000.0,
                            value=max(fridge_exit_h + 0.01, default_stable_h),
                            step=0.25,
                            format="%.2f",
                            key=f"phase_warm_stable_v3_{session_id}",
                            help=(
                                "Le pendenze di impasto e ambiente restano quasi "
                                "nulle e vicine: qui inizia l'Ambiente stabilizzato."
                            ),
                        )
                    )
                else:
                    boundary_columns[2].caption(
                        "Nessuna fase calda stabile: l'assestamento resta aperto."
                    )

                active_phase_annotation = PhaseAnnotation(
                    session_id=session_id,
                    protocol="fridge_to_ambient",
                    fridge_exit_h=fridge_exit_h,
                    warm_stable_h=warm_stable_h,
                    cold_stable_h=cold_stable_h,
                )
            elif phase_protocol == "ambient":
                active_phase_annotation = PhaseAnnotation(session_id, "ambient")

            single_phase_results: list[PhaseAnalysis] = []
            phase_analysis_error: str | None = None
            if active_phase_annotation is not None:
                try:
                    single_phase_results = analyze_protocol_phases(
                        analysis,
                        session_id,
                        active_phase_annotation,
                        fingerprint_config,
                        baseline_minutes=baseline_minutes,
                    )
                except ValueError as error:
                    phase_analysis_error = str(error)

            with st.container(border=True):
                st.markdown("**Individua visivamente il cambio di fase**")
                st.caption(
                    "Le fasce sono una proposta o un'anteprima: i cambi improvvisi "
                    "si leggono nel pannello dT/dt. Lo scarto giallo confronta le "
                    "pendenze senza dipendere dall'offset dei sensori; nulla viene "
                    "salvato automaticamente."
                )
                try:
                    phase_diagnostic_figure = build_phase_diagnostic_figure(
                        analysis,
                        single_phase_results,
                    )
                except ValueError as error:
                    st.info(f"Diagnostica termica non disponibile: {error}")
                else:
                    st.plotly_chart(
                        phase_diagnostic_figure,
                        width="stretch",
                        config={"displaylogo": False},
                        key=f"phase_diagnostic_{session_id}",
                    )
                if active_phase_annotation is None:
                    st.caption(
                        "Nessuna fascia applicata: scegli un protocollo per classificare "
                        "manualmente la sessione."
                    )
                elif single_phase_results:
                    if (
                        phase_protocol == "fridge_to_ambient"
                        and fridge_exit_h is not None
                        and fridge_exit_h
                        > float(
                            (analysis.index[-1] - analysis.index[0]).total_seconds()
                            / 3600.0
                        )
                    ):
                        st.info(
                            "L'uscita impostata Ã¨ oltre la durata osservata: il "
                            "grafico mostra soltanto la fase Freddo ancora in corso."
                        )
                    elif (
                        phase_protocol == "fridge_to_ambient"
                        and warm_stable_h is not None
                        and warm_stable_h
                        > float(
                            (analysis.index[-1] - analysis.index[0]).total_seconds()
                            / 3600.0
                        )
                    ):
                        st.info(
                            "La stabilizzazione Ã¨ oltre la durata osservata: "
                            "l'Assestamento termico Ã¨ ancora in corso."
                        )

            annotation_changed = (
                active_phase_annotation is None
                or single_phase_annotation is None
                or single_phase_annotation.protocol != phase_protocol
                or single_phase_annotation.fridge_exit_h != fridge_exit_h
                or single_phase_annotation.warm_stable_h != warm_stable_h
                or single_phase_annotation.cold_stable_h != cold_stable_h
            )
            save_column, status_column = st.columns([1, 3])
            if save_column.button(
                "Salva configurazione fasi",
                type="primary",
                key=f"save_phase_annotation_{session_id}",
                icon=":material/save:",
                disabled=active_phase_annotation is None,
            ):
                try:
                    if active_phase_annotation is None:
                        raise ValueError("Scegli un protocollo prima di salvare.")
                    saved_path = save_phase_annotation(active_phase_annotation)
                except (OSError, ValueError) as error:
                    st.error(f"Configurazione fasi non salvata: {error}")
                else:
                    st.success(f"Configurazione salvata in {saved_path}")
                    st.rerun()
            if active_phase_annotation is None:
                status_column.info(
                    "Sessione non classificata: nessun metadato di fase verrÃ  salvato."
                )
            elif annotation_changed:
                status_column.info(
                    "Anteprima attiva: salva per ritrovare queste fasi e usarle "
                    "nei confronti."
                )
            else:
                status_column.success("Configurazione fasi salvata.")
            st.caption(f"Archivio locale: {default_phase_sidecar_dir()}")

            if phase_analysis_error:
                st.warning(
                    f"Analisi per fase non disponibile: {phase_analysis_error}"
                )
            else:
                render_phase_results(
                    single_phase_results,
                    key_prefix=f"single_phase_{session_id}",
                )

    elif single_section == "Dettagli":
        with st.container():
            if session_metadata:
                render_metadata(session_metadata)
            else:
                st.info("Nessun metadato disponibile per questa sessione.")

            with st.expander("Dati elaborati", expanded=False):
                st.caption("Valori con i parametri di analisi attualmente selezionati.")
                st.dataframe(
                    analysis.reset_index(), width="stretch", hide_index=True
                )
    else:
        with st.container():
            with st.container():
                selected_fingerprint_events = st.multiselect(
                    "Eventi caratteristici sul grafico",
                    list(FINGERPRINT_EVENT_LABELS),
                    default=["t25", "t50", "t100", "max_rate", "plateau"],
                    format_func=lambda value: FINGERPRINT_EVENT_LABELS[value],
                    help="Le metriche usano sempre la timeline originale della sessione.",
                    key="single_graph_events",
                )
                event_figure = go.Figure(volume_figure)
                if single_saved_phase_results:
                    add_phase_overlays_to_time_figure(
                        event_figure,
                        single_saved_phase_results,
                        analysis.index[0],
                    )
                for event_name in selected_fingerprint_events:
                    event_time_h = fingerprint.events_h.get(event_name)
                    if event_time_h is None:
                        continue
                    event_timestamp = (
                        analysis.index[0] + pd.to_timedelta(event_time_h, unit="h")
                    ).to_pydatetime(warn=False)
                    event_color = (
                        "#F1B95E" if event_name == "collapse" else "#A9BBB1"
                    )
                    event_figure.add_vline(
                        x=event_timestamp,
                        line_width=1,
                        line_dash="dot",
                        line_color=event_color,
                    )
                    event_figure.add_annotation(
                        x=event_timestamp,
                        y=1.0,
                        xref="x",
                        yref="paper",
                        text=FINGERPRINT_EVENT_LABELS[event_name],
                        textangle=-90,
                        showarrow=False,
                        yanchor="bottom",
                        font={"size": 11, "color": event_color},
                    )
                st.plotly_chart(
                    event_figure,
                    width="stretch",
                    config={"displaylogo": False},
                )
                if temperature_overview_figure.data:
                    temperature_with_phases = go.Figure(
                        temperature_overview_figure
                    )
                    if single_saved_phase_results:
                        add_phase_overlays_to_time_figure(
                            temperature_with_phases,
                            single_saved_phase_results,
                            analysis.index[0],
                            show_phase_legend=True,
                        )
                    st.plotly_chart(
                        temperature_with_phases,
                        width="stretch",
                        config={"displaylogo": False},
                    )
                else:
                    st.caption("Questa sessione non contiene dati di temperatura.")
                if single_saved_phase_error:
                    st.warning(
                        "Fasi salvate non visualizzabili: "
                        + single_saved_phase_error
                    )
                elif single_phase_annotation is None:
                    st.caption(
                        "Per mostrare le fasce anche qui, configura e salva i "
                        "confini nella sezione Fasi."
                    )
            with st.expander(
                "Correlazione fra due variabili",
                expanded=False,
                icon=":material/scatter_plot:",
            ):
                metric_options = get_compare_metric_options([analysis])
                if len(metric_options) < 2:
                    st.info(
                        "I dati disponibili non permettono una correlazione tra due variabili."
                    )
                else:
                    metric_names = [name for name, _label in metric_options]
                    x_metric = st.selectbox(
                        "Variabile X",
                        metric_names,
                        format_func=lambda value: next(
                            label for name, label in metric_options if name == value
                        ),
                        index=0,
                        key="single_correlation_x",
                    )
                    y_metric = st.selectbox(
                        "Variabile Y",
                        metric_names,
                        format_func=lambda value: next(
                            label for name, label in metric_options if name == value
                        ),
                        index=1,
                        key="single_correlation_y",
                    )
                    if x_metric == y_metric:
                        st.info(
                            "Scegli due variabili diverse per visualizzare la correlazione."
                        )
                    else:
                        correlation_figure = go.Figure()
                        x_values = analysis[x_metric]
                        y_values = analysis[y_metric]
                        valid = x_values.notna() & y_values.notna()
                        correlation_figure.add_trace(
                            go.Scatter(
                                x=x_values[valid],
                                y=y_values[valid],
                                mode="lines+markers",
                                name=session_id,
                                line={"color": "#69D7A0", "width": 2},
                                marker={"size": 5, "color": "#F1B95E"},
                                hovertemplate=(
                                    f"{session_id}<br>{x_metric} = %{{x:.3f}}"
                                    f"<br>{y_metric} = %{{y:.3f}}<extra></extra>"
                                ),
                            )
                        )
                        correlation_figure.update_layout(
                            title="Correlazione tra due variabili",
                            xaxis_title=next(
                                label
                                for name, label in metric_options
                                if name == x_metric
                            ),
                            yaxis_title=next(
                                label
                                for name, label in metric_options
                                if name == y_metric
                            ),
                            hovermode="closest",
                        )
                        style_figure(correlation_figure)
                        st.plotly_chart(
                            correlation_figure,
                            width="stretch",
                            config={"displaylogo": False},
                        )

        with st.expander(
            "Curve derivate",
            expanded=False,
            icon=":material/query_stats:",
        ):
            if derived_figure.data:
                st.plotly_chart(
                    derived_figure,
                    width="stretch",
                    config={"displaylogo": False},
                )
            else:
                st.info("Dati insufficienti per calcolare le curve derivate.")

        with st.expander(
            "Temperatura e dinamica",
            expanded=False,
            icon=":material/thermostat:",
        ):
            st.plotly_chart(
                correlation_figure,
                width="stretch",
                config={"displaylogo": False},
            )
