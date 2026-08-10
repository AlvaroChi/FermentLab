"""Local Streamlit UI for exploring FermentLab sessions in InfluxDB."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from fermentlab_analyzer import (
    FermentationAnalysisConfig,
    FermentationFingerprint,
    InfluxRepository,
    InfluxSettings,
    add_relative_time,
    analyze_session,
    build_recipe_sections,
    build_recipe_summary,
    compute_fermentation_fingerprint,
    fingerprints_to_dataframe,
    fingerprints_to_json,
    summarize_session,
)


st.set_page_config(
    page_title="FermentLab · Analyzer",
    page_icon="🫧",
    layout="wide",
    initial_sidebar_state="expanded",
)


APP_CSS = """
<style>
    :root {
        color-scheme: dark;
        --fl-bg: #0b1210;
        --fl-sidebar: #0f1814;
        --fl-surface: #131e19;
        --fl-surface-raised: #19261f;
        --fl-ink: #edf6f1;
        --fl-muted: #a9bbb1;
        --fl-green: #69d7a0;
        --fl-green-soft: #193c2c;
        --fl-amber: #f1b95e;
        --fl-border: rgba(218, 239, 228, 0.15);
    }
    .stApp { background: var(--fl-bg); color: var(--fl-ink); }
    [data-testid="stHeader"] { background: rgba(11, 18, 16, .86); }
    .block-container {
        max-width: 1440px;
        padding-top: 2.2rem;
        padding-bottom: 4rem;
    }
    [data-testid="stSidebar"] {
        background: var(--fl-sidebar);
        border-right: 1px solid var(--fl-border);
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: var(--fl-muted);
    }
    .fl-hero {
        padding: 1.25rem 1.4rem;
        margin-bottom: 1.25rem;
        border: 1px solid var(--fl-border);
        border-radius: 18px;
        background:
            radial-gradient(circle at 92% 10%, rgba(241,185,94,.13), transparent 30%),
            linear-gradient(135deg, #14271e 0%, #101915 72%);
        box-shadow: 0 14px 38px rgba(0, 0, 0, .22);
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
        background: var(--fl-surface);
        box-shadow: 0 6px 20px rgba(0, 0, 0, .16);
    }
    [data-testid="stMetricLabel"] { color: var(--fl-muted); }
    [data-testid="stMetricValue"] { color: var(--fl-ink); }
    [data-testid="stExpander"] {
        border-color: var(--fl-border);
        border-radius: 14px;
        background: rgba(19, 30, 25, .82);
    }
    .stButton > button {
        border-radius: 10px;
        font-weight: 650;
        border-color: var(--fl-border);
    }
    .stButton > button:focus-visible,
    div[data-baseweb="select"] *:focus-visible,
    div[data-baseweb="input"] *:focus-visible {
        outline: 2px solid var(--fl-green);
        outline-offset: 2px;
    }
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div { border-radius: 10px; }
    [data-testid="stDataFrame"] {
        border: 1px solid var(--fl-border);
        border-radius: 12px;
        overflow: hidden;
    }
    [data-testid="stCaptionContainer"],
    [data-testid="stWidgetLabel"] p { color: var(--fl-muted); }
    hr { border-color: var(--fl-border); }
    a { color: #7ee2ae; }
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


@st.cache_data(show_spinner=False, max_entries=50)
def build_fingerprint(
    analysis: pd.DataFrame,
    session_id: str,
    config: FermentationAnalysisConfig,
) -> FermentationFingerprint:
    """Cache the deterministic, CPU-bound post-processing step."""

    return compute_fermentation_fingerprint(analysis, session_id, config)


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


@st.dialog("Conferma cancellazione")
def confirm_batch_session_delete(
    url: str,
    org: str,
    bucket: str,
    token: str,
    measurement: str,
    lookback_days: int,
    selected_session_ids: tuple[str, ...],
    total_minutes: int,
    total_records: int,
) -> None:
    session_count = len(selected_session_ids)
    session_word = "sessione" if session_count == 1 else "sessioni"
    st.warning(
        f"Sei sicuro di voler cancellare **{session_count} {session_word}** "
        f"con una durata totale di **{total_minutes} minuti** "
        f"(**{total_records} record**)?"
    )
    st.caption("La cancellazione è definitiva e rimuove i dati da InfluxDB.")
    with st.expander("Sessioni selezionate", expanded=False):
        for session_id in selected_session_ids:
            st.write(f"• {session_id}")

    with st.container(horizontal=True):
        if st.button(
            "Annulla",
            icon=":material/close:",
            key="cancel_batch_session_delete",
            width="stretch",
        ):
            st.rerun(scope="app")
        if st.button(
            f"Sì, cancella {session_count}",
            icon=":material/delete:",
            key="confirm_batch_session_delete",
            type="primary",
            width="stretch",
        ):
            deleted_session_ids: list[str] = []
            deleted_records = 0
            failures: list[str] = []
            with st.spinner("Cancellazione in corso..."):
                for session_id in selected_session_ids:
                    try:
                        result = delete_session_from_influx(
                            url,
                            org,
                            bucket,
                            token,
                            measurement,
                            session_id,
                            lookback_days,
                        )
                        deleted_session_ids.append(session_id)
                        deleted_records += int(result.get("record_count") or 0)
                    except Exception as error:
                        failures.append(f"{session_id}: {error}")

            st.cache_data.clear()
            st.session_state["manager_delete_feedback"] = {
                "deleted_session_ids": deleted_session_ids,
                "deleted_records": deleted_records,
                "failures": failures,
            }
            st.rerun(scope="app")


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
        return "—"
    return f"{value:.{digits}f}{suffix}"


def fmt_timestamp(value: object) -> str:
    if value is None:
        return "—"
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return "—"
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
    ("max_growth_rate_value_h", "Velocità massima", "signal/h", True),
    ("max_specific_growth_rate_h", "Velocità specifica massima", "1/h", True),
    ("lag_time_h", "Lag time", "h", True),
    ("inflection_time_h", "Punto di flesso", "h", True),
    ("plateau_start_time_h", "Inizio plateau", "h", True),
    ("active_phase_duration_h", "Durata fase attiva", "h", True),
    ("late_early_ratio", "Rapporto late/early", "×", True),
    ("dough_temp_mean_c", "Temperatura media impasto", "°C", False),
    ("dough_temp_at_max_growth_rate_c", "Temperatura a vmax", "°C", False),
    ("ambient_temp_mean_c", "Temperatura media ambiente", "°C", False),
    ("delta_t_max_c", "ΔT massimo", "°C", False),
    ("thermal_integral_20c_c_h", "Integrale termico (20 °C)", "°C·h", True),
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
        ("Dinamica", "Velocità massima", fmt_optional(metrics.max_growth_rate_value_h, rate_unit), metrics.max_growth_rate_value_h, "max_growth_rate_value_h"),
        ("Dinamica", "Tempo vmax", fmt_duration(metrics.time_of_max_growth_rate_h), metrics.time_of_max_growth_rate_h, "max_growth_rate_value_h"),
        ("Dinamica", "Velocità specifica massima", fmt_optional(metrics.max_specific_growth_rate_h, " 1/h", 3), metrics.max_specific_growth_rate_h, "max_specific_growth_rate_h"),
        ("Dinamica", "Punto di flesso", fmt_duration(metrics.inflection_time_h), metrics.inflection_time_h, "inflection_time_h"),
        ("Dinamica", "Early rate (25–50%)", fmt_optional(metrics.early_rate_value_h, rate_unit), metrics.early_rate_value_h, None),
        ("Dinamica", "Late rate (75–100%)", fmt_optional(metrics.late_rate_value_h, rate_unit), metrics.late_rate_value_h, None),
        ("Dinamica", "Rapporto late/early", fmt_optional(metrics.late_early_ratio, "×", 2), metrics.late_early_ratio, "late_early_ratio"),
        ("Temperatura", "Temperatura iniziale impasto", fmt_optional(metrics.dough_temp_initial_c, " °C"), metrics.dough_temp_initial_c, None),
        ("Temperatura", "Temperatura finale impasto", fmt_optional(metrics.dough_temp_final_c, " °C"), metrics.dough_temp_final_c, None),
        ("Temperatura", "Temperatura media impasto", fmt_optional(metrics.dough_temp_mean_c, " °C"), metrics.dough_temp_mean_c, None),
        ("Temperatura", "Temperatura min / max impasto", f"{fmt_optional(metrics.dough_temp_min_c)} / {fmt_optional(metrics.dough_temp_max_c)} °C", metrics.dough_temp_mean_c, None),
        ("Temperatura", "Temperatura a vmax", fmt_optional(metrics.dough_temp_at_max_growth_rate_c, " °C"), metrics.dough_temp_at_max_growth_rate_c, None),
        ("Temperatura", "Temperatura media ambiente", fmt_optional(metrics.ambient_temp_mean_c, " °C"), metrics.ambient_temp_mean_c, None),
        ("Temperatura", "ΔT medio", fmt_optional(metrics.delta_t_mean_c, " °C", signed=True), metrics.delta_t_mean_c, None),
        ("Temperatura", "ΔT massimo", fmt_optional(metrics.delta_t_max_c, " °C", signed=True), metrics.delta_t_max_c, None),
        ("Termica", "Integrale termico 0 °C", fmt_optional(metrics.thermal_integral_0c_c_h, " °C·h"), metrics.thermal_integral_0c_c_h, "thermal_integral"),
        ("Termica", "Integrale termico 4 °C", fmt_optional(metrics.thermal_integral_4c_c_h, " °C·h"), metrics.thermal_integral_4c_c_h, "thermal_integral"),
        ("Termica", "Integrale termico 20 °C", fmt_optional(metrics.thermal_integral_20c_c_h, " °C·h"), metrics.thermal_integral_20c_c_h, "thermal_integral"),
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
                "Qualità": status_labels[status],
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
            else "unità segnale/h"
            if unit == "signal/h"
            else unit
        )
        row: dict[str, object] = {"Metrica": label, "Unità": display_unit}
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
        column for column in display.columns if column not in {"Metrica", "Unità"}
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
        unit = str(display.at[row_index, "Unità"])
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
                formatted = f"MIN · {formatted}"
            elif column == maximum_column:
                formatted = f"MAX · {formatted}"
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
                "Unità": display_unit,
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
            "Unità": st.column_config.TextColumn(pinned=True),
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
        ("relative_growth", "Crescita relativa (×)"),
        ("growth_pct", "Crescita (%)"),
        ("growth_rate_value_h", "Velocità assoluta"),
        ("specific_growth_rate_h", "Velocità specifica (1/h)"),
        ("delta_t_c", "ΔT impasto-ambiente"),
        ("temperature_dough_c", "Temperatura impasto"),
        ("temperature_ambient_c", "Temperatura ambiente"),
        ("growth_rate_pct_h", "Velocità crescita (%/h)"),
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
        font={"family": "Inter, ui-sans-serif, system-ui, sans-serif", "color": "#c5d4cc"},
        title={"font": {"size": 19, "color": "#edf6f1"}, "x": 0.01},
        colorway=[
            "#69d7a0",
            "#f1b95e",
            "#79b8ff",
            "#ff7b72",
            "#c99aff",
            "#f29ac2",
            "#7fdfe6",
        ],
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "bgcolor": "rgba(19,30,25,.88)",
        },
        hoverlabel={
            "bgcolor": "#1b2922",
            "bordercolor": "#52685d",
            "font": {"color": "#f4faf7", "size": 13},
        },
    )
    figure.update_xaxes(
        showgrid=True,
        gridcolor="rgba(218,239,228,.10)",
        zeroline=False,
        showline=True,
        linecolor="rgba(218,239,228,.20)",
    )
    figure.update_yaxes(
        showgrid=True,
        gridcolor="rgba(218,239,228,.10)",
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
    recipe_tabs = st.tabs([title for title, _rows in recipe_sections])
    for recipe_tab, (_title, rows) in zip(recipe_tabs, recipe_sections):
        with recipe_tab:
            st.dataframe(
                pd.DataFrame(rows, columns=["Parametro", "Valore"]),
                width="stretch",
                hide_index=True,
            )


defaults = InfluxSettings.from_environment()

st.markdown(
    """
    <div class="fl-hero">
        <div class="fl-eyebrow">FermentLab · controllo fermentazione</div>
        <h1>Analisi della fermentazione</h1>
        <p>Analizza crescita e temperatura dell'impasto, confronta le sessioni e individua subito i cambi di ritmo.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### 🫧 FermentLab")
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
    if st.button("↻  Aggiorna dati", width="stretch", type="primary"):
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
            st.success("Credenziali locali caricate", icon="✅")
        else:
            st.caption("Il token resta nella sessione corrente e non viene salvato.")

    st.divider()
    management_enabled = st.toggle(
        "Strumenti amministrativi",
        value=False,
        help="Abilita diagnostica, unione e cancellazione delle sessioni.",
    )
    app_view = (
        st.radio(
            "Area di lavoro",
            ["Analisi", "Gestione sessioni"],
            index=0,
        )
        if management_enabled
        else "Analisi"
    )
    if management_enabled:
        st.caption("Unione e cancellazione richiedono permessi di scrittura.")

if not token:
    render_section_title(
        "Collega il database",
        "Apri “Connessione InfluxDB” nella barra laterale e inserisci il token per iniziare.",
    )
    st.info("La configurazione resta locale e il token non viene salvato dall'app.", icon="🔒")
    st.stop()

try:
    sessions = list_sessions(
        url, org, bucket, token, measurement, int(lookback_days)
    )
except Exception as error:
    st.error(f"Connessione a InfluxDB non riuscita: {error}")
    st.stop()

delete_feedback = st.session_state.pop("manager_delete_feedback", None)
if isinstance(delete_feedback, dict):
    deleted_session_ids = delete_feedback.get("deleted_session_ids", [])
    deleted_records = int(delete_feedback.get("deleted_records") or 0)
    failures = delete_feedback.get("failures", [])
    if deleted_session_ids:
        deleted_count = len(deleted_session_ids)
        deleted_word = "sessione" if deleted_count == 1 else "sessioni"
        st.success(
            f"Cancellazione completata: eliminate {deleted_count} {deleted_word} "
            f"e {deleted_records} record."
        )
    if failures:
        st.error("Alcune sessioni non sono state eliminate:")
        for failure in failures:
            st.write(f"• {failure}")

if sessions.empty:
    st.warning("Nessuna sessione trovata nell'intervallo selezionato.")
    st.stop()

session_labels = {
    row.session_id: f"{row.session_id} · {row.last_seen:%Y-%m-%d %H:%M} UTC"
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

    info_tab, merge_tab, delete_tab = st.tabs(
        ["Informazioni", "Unisci sessioni", "Elimina sessioni"]
    )

    with info_tab:
        info_session_id = st.selectbox(
            "Sessione da ispezionare",
            filtered_catalog["session_id"].tolist(),
            format_func=lambda value: session_labels.get(value, value),
            key="manager_info_session",
        )
        admin_info = load_session_admin_info(
            url,
            org,
            bucket,
            token,
            measurement,
            info_session_id,
            int(lookback_days),
        )
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
        managed_session_id = st.selectbox(
            "Sessione sorgente",
            filtered_catalog["session_id"].tolist(),
            format_func=lambda value: session_labels.get(value, value),
            key="manager_merge_source",
        )
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
                st.info("La sessione destinazione oggi non esiste ancora: il merge la creerà.")

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
        st.caption(
            "Seleziona una o più sessioni. Prima della cancellazione vedrai il "
            "totale di durata e record e potrai confermare o annullare."
        )
        header_select, header_name, header_duration, header_records = st.columns(
            [0.5, 4.5, 1.4, 1.2],
            vertical_alignment="center",
        )
        header_select.caption("Scegli")
        header_name.caption("Sessione")
        header_duration.caption("Durata")
        header_records.caption("Record")

        selected_session_ids: list[str] = []
        with st.container(border=True, gap=None):
            for row in filtered_catalog.itertuples(index=False):
                session_id_value = str(row.session_id)
                select_col, name_col, duration_col, records_col = st.columns(
                    [0.5, 4.5, 1.4, 1.2],
                    vertical_alignment="center",
                )
                selected = select_col.checkbox(
                    f"Seleziona {session_id_value}",
                    key=f"manager_delete_select_{session_id_value}",
                    label_visibility="collapsed",
                )
                name_col.write(session_id_value)
                duration_col.write(f"{float(row.duration_hours) * 60.0:.0f} min")
                records_col.write(f"{int(row.record_count):,}".replace(",", "."))
                if selected:
                    selected_session_ids.append(session_id_value)

        if selected_session_ids:
            selected_catalog = filtered_catalog[
                filtered_catalog["session_id"].isin(selected_session_ids)
            ]
            total_minutes = int(
                round(float(selected_catalog["duration_hours"].sum()) * 60.0)
            )
            total_records = int(selected_catalog["record_count"].sum())
            session_count = len(selected_session_ids)
            session_word = "sessione" if session_count == 1 else "sessioni"
            st.info(
                f"Hai selezionato **{session_count} {session_word}**: "
                f"**{total_minutes} minuti** totali e **{total_records} record**."
            )
            if st.button(
                "Elimina selezionate",
                icon=":material/delete:",
                key="open_batch_session_delete",
                type="primary",
                width="stretch",
            ):
                allowed_session_ids = set(
                    filtered_catalog["session_id"].astype(str).tolist()
                )
                validated_session_ids = tuple(
                    session_id
                    for session_id in selected_session_ids
                    if session_id in allowed_session_ids
                )
                if len(validated_session_ids) != len(selected_session_ids):
                    st.error("La selezione contiene sessioni non valide. Aggiorna la pagina.")
                else:
                    confirm_batch_session_delete(
                        url,
                        org,
                        bucket,
                        token,
                        measurement,
                        int(lookback_days),
                        validated_session_ids,
                        total_minutes,
                        total_records,
                    )
        else:
            st.info("Seleziona almeno una sessione da eliminare.")

    st.stop()

render_section_title(
    "Esplora le sessioni",
    "Scegli una fermentazione oppure metti più prove sullo stesso asse temporale.",
)
analysis_mode = st.segmented_control(
    "Modalità di analisi",
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
    single_results_view = st.segmented_control(
        "Vista risultati · passa da testo a grafici",
        ["TESTO", "GRAFICI"],
        default="TESTO",
        required=True,
        format_func=lambda value: {
            "TESTO": ":material/table_rows: TESTO",
            "GRAFICI": ":material/show_chart: GRAFICI",
        }[value],
        key="single_results_view",
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
        st.info("Seleziona almeno due sessioni per la modalità Compare Sessions.")
        st.stop()
    compare_results_view = st.segmented_control(
        "Vista risultati · passa da testo a grafici",
        ["TESTO", "GRAFICI"],
        default="TESTO",
        required=True,
        format_func=lambda value: {
            "TESTO": ":material/table_rows: TESTO",
            "GRAFICI": ":material/show_chart: GRAFICI",
        }[value],
        key="compare_results_view",
        width="stretch",
    )

with st.expander("Regolazioni analisi", expanded=False):
    st.caption(
        "I valori predefiniti sono adatti alla maggior parte delle sessioni. "
        "Modificali solo per correggere rumore, picchi o una baseline instabile."
    )
    smoothing_tab, baseline_tab, dynamics_tab = st.tabs(
        ["Pulizia segnale", "Baseline", "Dinamica"]
    )

    with smoothing_tab:
        col_a, col_b = st.columns(2)
        smoothing_minutes = col_a.slider(
            "Filtro mediano",
            1,
            30,
            5,
            help="Riduce il rumore preservando i cambi di tendenza.",
        )
        col_a.caption("minuti")
        post_smoothing_minutes = col_b.slider(
            "Smussatura finale",
            0,
            30,
            3,
            help="Rende più leggibile la curva elaborata.",
        )
        col_b.caption("minuti")

        col_c, col_d = st.columns(2)
        despike_window_minutes = col_c.slider(
            "Finestra rimozione picchi", 0, 20, 3
        )
        col_c.caption("minuti · 0 per disattivare")
        despike_sigma = col_d.slider(
            "Sensibilità ai picchi", 0.0, 8.0, 3.5, 0.5
        )
        col_d.caption("sigma · 0 per disattivare")

    with baseline_tab:
        col_e, col_f = st.columns(2)
        baseline_offset_minutes = col_e.slider(
            "Ignora l'avvio", 0, 180, 0, 5,
            help="Utile se il campione non era stabile al momento dello START.",
        )
        col_e.caption("minuti iniziali")
        baseline_minutes = col_f.slider("Finestra baseline", 1, 30, 5)
        col_f.caption("minuti")

    with dynamics_tab:
        col_g, col_h = st.columns(2)
        rate_window_minutes = col_g.slider(
            "Finestra velocità", 5, 120, 30, 5
        )
        col_g.caption("minuti")
        acceleration_window_minutes = col_h.slider(
            "Finestra accelerazione", 10, 180, 60, 5
        )
        col_h.caption("minuti")
        minimum_slope_points = st.slider(
            "Campioni minimi per la stima", 3, 15, 5
        )

        st.divider()
        st.caption(
            "Le soglie seguenti controllano lag, plateau, fase attiva e collasso. "
            "Sono applicate solo a eventi persistenti, non a singoli campioni."
        )
        phase_col_a, phase_col_b = st.columns(2)
        lag_rate_percent = phase_col_a.slider(
            "Soglia lag e fase attiva",
            5,
            50,
            20,
            5,
            help="Percentuale della velocità massima che identifica crescita significativa.",
        )
        plateau_rate_percent = phase_col_b.slider(
            "Soglia plateau",
            2,
            30,
            10,
            1,
            help="Il plateau richiede una velocità inferiore a questa percentuale di vmax.",
        )
        phase_col_c, phase_col_d = st.columns(2)
        lag_persistence_minutes = phase_col_c.slider(
            "Persistenza lag", 5, 120, 15, 5
        )
        plateau_persistence_minutes = phase_col_d.slider(
            "Persistenza plateau", 10, 180, 30, 5
        )
        phase_col_e, phase_col_f = st.columns(2)
        collapse_loss_percent = phase_col_e.slider(
            "Perdita minima per collasso (%)", 1, 30, 5, 1
        )
        collapse_persistence_minutes = phase_col_f.slider(
            "Persistenza collasso", 10, 180, 30, 5
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
        fingerprint = build_fingerprint(
            analysis,
            session_id,
            fingerprint_config,
        )
        analysis_attrs = analysis.attrs.copy()
        analysis = analysis.join(fingerprint.curves)
        analysis.attrs.update(analysis_attrs)
    except Exception as error:
        st.error(f"Analisi della sessione non riuscita: {error}")
        st.stop()
else:
    compare_analyses: list[dict[str, object]] = []
    compare_fingerprints: list[FermentationFingerprint] = []
    compare_errors: list[str] = []
    offset_hours: dict[str, float] = {}
    compare_metadata: dict[str, dict[str, object]] = {}

    if compare_results_view == "GRAFICI":
        with st.expander("Offset temporali", expanded=True):
            for session_name in selected_session_ids:
                current_offset = float(
                    st.session_state.compare_offsets.get(session_name, 0.0)
                )
                col_offset_h, col_offset_m = st.columns(2)
                offset_hours_value = col_offset_h.number_input(
                    f"Offset · {session_name} (h)",
                    min_value=-1000.0,
                    max_value=1000.0,
                    value=current_offset,
                    step=0.25,
                    format="%.2f",
                    key=f"offset_h_{session_name}",
                )
                offset_minutes_value = col_offset_m.number_input(
                    f"Offset · {session_name} (min)",
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
            session_name: float(
                st.session_state.compare_offsets.get(session_name, 0.0)
            )
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
            fingerprint = build_fingerprint(
                analysis,
                session_name,
                fingerprint_config,
            )
            analysis_attrs = analysis.attrs.copy()
            analysis = analysis.join(fingerprint.curves)
            analysis.attrs.update(analysis_attrs)
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
                {
                    "session_id": session_name,
                    "analysis": transformed,
                    "fingerprint": fingerprint,
                }
            )
            compare_fingerprints.append(fingerprint)
        except Exception as error:
            compare_errors.append(f"{session_name}: {error}")

    if compare_errors:
        for error_text in compare_errors:
            st.warning(error_text)

    if not compare_analyses:
        st.error("Nessuna sessione comparabile è stata caricata.")
        st.stop()

    if compare_results_view == "TESTO":
        render_section_title(
            "Confronto dei parametri",
            "Le metriche sono calcolate sulla timeline originale di ogni sessione. "
            "I valori mancanti restano esplicitamente N.A.",
        )
        render_multi_fingerprint_summary(compare_fingerprints)
        with st.expander("Metadati sessioni", expanded=False):
            for session_name in selected_session_ids:
                metadata = compare_metadata.get(session_name, {})
                st.markdown(f"#### {session_name}")
                if not metadata:
                    st.caption("Nessun metadato disponibile per questa sessione.")
                    continue
                render_metadata(metadata)
        st.stop()

    render_section_title(
        "Grafici di confronto",
        "Le curve possono essere allineate con offset senza modificare le metriche "
        "o i dati originali.",
    )

    metric_options = get_compare_metric_options(
        [entry["analysis"] for entry in compare_analyses]
    )
    if not metric_options:
        st.info("Le sessioni non hanno metriche comparabili con i dati attuali.")
        st.stop()

    metric_names = [name for name, _label in metric_options]

    compare_view = st.segmented_control(
        "Vista grafico",
        ["Serie temporali", "Correlazione 2 variabili"],
        default="Serie temporali",
        format_func=lambda value: {
            "Serie temporali": "Andamento nel tempo",
            "Correlazione 2 variabili": "Correlazione",
        }[value],
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
        compare_event_markers = st.multiselect(
            "Eventi caratteristici sulle timeline allineate",
            list(FINGERPRINT_EVENT_LABELS),
            default=[],
            format_func=lambda value: FINGERPRINT_EVENT_LABELS[value],
            help="Ogni evento usa il tempo della sessione meno il relativo offset di visualizzazione.",
        )
    else:
        compare_metrics = []
        compare_event_markers = []

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
            offset_hours_value = float(st.session_state.compare_offsets.get(str(entry["session_id"]), 0.0))
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
                    name=f"{entry['session_id']} (offset {offset_hours_value:+.2f} h)",
                    hovertemplate=(
                        f"{entry['session_id']}<br>offset = {offset_hours_value:+.2f} h<br>{x_metric} = %{{x:.3f}}<br>{y_metric} = %{{y:.3f}}<extra></extra>"
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
                        name=f"{entry['session_id']} · {metric_labels[metric_name]}",
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
                line_color="rgba(197, 212, 204, 0.72)",
                annotation_text=alignment_event if metric_index == 1 else "",
                annotation_position="top left",
                row=1,
                col=metric_index,
            )
            for session_index, entry in enumerate(compare_analyses):
                fingerprint = entry["fingerprint"]
                session_name = str(entry["session_id"])
                offset_value = float(
                    st.session_state.compare_offsets.get(session_name, 0.0)
                )
                event_color = (
                    "#69D7A0",
                    "#F1B95E",
                    "#79B8FF",
                    "#FF7B72",
                    "#C99AFF",
                )[session_index % 5]
                for event_name in compare_event_markers:
                    event_time_h = fingerprint.events_h.get(event_name)
                    if event_time_h is None:
                        continue
                    display_time_h = float(event_time_h) - offset_value
                    compare_figure.add_vline(
                        x=display_time_h,
                        line_width=1,
                        line_dash="dot",
                        line_color=event_color,
                        annotation_text=(
                            f"{session_name} · {FINGERPRINT_EVENT_LABELS[event_name]}"
                            if metric_index == 1
                            else ""
                        ),
                        annotation_position="top",
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

    with st.expander("Metadati sessioni", expanded=True):
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
        "Velocità attuale",
        fmt_number(summary.current_growth_rate_pct_h, "%/h"),
    )

    metric_row_secondary = st.columns(3)
    metric_row_secondary[0].metric(
        "Crescita massima", fmt_number(summary.maximum_growth_pct, "%")
    )
    metric_row_secondary[1].metric(
        "Rapporto attuale / iniziale",
        fmt_number(summary.current_ratio_x, "×", 2),
    )
    metric_row_secondary[2].metric(
        "Accelerazione",
        fmt_number(summary.current_growth_accel_pct_h2, "%/h²"),
    )

    if summary.signal_field == "dough_height_mm":
        st.warning(
            "Questa sessione non contiene `volume_ml`: la crescita percentuale è "
            "calcolata dall'altezza. Configurando la sezione del contenitore nel "
            "firmware, le sessioni future includeranno anche il volume."
        )
    if analysis["growth_pct"].min() < -5:
        st.info(
            "Il segnale scende oltre il 5% dopo la baseline. Se il campione non era "
            "ancora stabile allo START, aumenta ‘Ignora i primi minuti’."
        )

    volume_figure = make_subplots(specs=[[{"secondary_y": True}]])
    volume_figure.add_trace(
        go.Scatter(
            x=analysis.index,
            y=analysis[summary.signal_field],
            name=f"{summary.signal_label} grezza",
            line={"color": "rgba(197, 212, 204, 0.48)", "width": 1},
        ),
        secondary_y=False,
    )
    if "signal_despiked" in analysis and despike_window_minutes > 0 and despike_sigma > 0:
        volume_figure.add_trace(
            go.Scatter(
                x=analysis.index,
                y=analysis["signal_despiked"],
                name=f"{summary.signal_label} ripulita",
                line={"color": "rgba(121, 184, 255, 0.78)", "width": 1.5},
            ),
            secondary_y=False,
        )
    volume_figure.add_trace(
        go.Scatter(
            x=analysis.index,
            y=analysis["signal_smooth"],
            name=f"{summary.signal_label} filtrata",
            line={"color": "#69D7A0", "width": 3},
        ),
        secondary_y=False,
    )
    volume_figure.add_trace(
        go.Scatter(
            x=analysis.index,
            y=analysis["growth_pct"],
            name="Crescita",
            line={"color": "#F1B95E", "width": 2},
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

    temperature_overview_figure = go.Figure()
    if (
        "temperature_dough_c" in analysis
        and analysis["temperature_dough_c"].notna().any()
    ):
        temperature_overview_figure.add_trace(
            go.Scatter(
                x=analysis.index,
                y=analysis["temperature_dough_c"],
                name="Temperatura impasto",
                line={"color": "#FF7B72", "width": 2},
            )
        )
    if (
        "temperature_ambient_c" in analysis
        and analysis["temperature_ambient_c"].notna().any()
    ):
        temperature_overview_figure.add_trace(
            go.Scatter(
                x=analysis.index,
                y=analysis["temperature_ambient_c"],
                name="Temperatura ambiente",
                line={"color": "#79B8FF", "width": 2},
            )
        )
    temperature_overview_figure.update_layout(
        title="Temperature",
        hovermode="x unified",
    )
    temperature_overview_figure.update_yaxes(title_text="Temperatura (°C)")
    style_figure(temperature_overview_figure, height=340)

    temperature_figure = make_subplots(specs=[[{"secondary_y": True}]])
    if "temperature_dough_c" in analysis:
        temperature_figure.add_trace(
            go.Scatter(
                x=analysis.index,
                y=analysis["temperature_dough_c"],
                name="Temperatura impasto",
                line={"color": "#FF7B72", "width": 2},
            ),
            secondary_y=False,
        )
    if "temperature_ambient_c" in analysis:
        temperature_figure.add_trace(
            go.Scatter(
                x=analysis.index,
                y=analysis["temperature_ambient_c"],
                name="Temperatura ambiente",
                line={"color": "#79B8FF", "width": 2},
            ),
            secondary_y=False,
        )
    temperature_figure.add_trace(
        go.Scatter(
            x=analysis.index,
            y=analysis["growth_rate_pct_h"],
            name="Velocità crescita",
            line={"color": "#C99AFF", "width": 2},
        ),
        secondary_y=True,
    )
    temperature_figure.add_trace(
        go.Scatter(
            x=analysis.index,
            y=analysis["growth_accel_pct_h2"],
            name="Accelerazione crescita",
            line={"color": "#F29AC2", "width": 2, "dash": "dot"},
        ),
        secondary_y=True,
    )
    temperature_figure.update_yaxes(title_text="Temperatura (°C)", secondary_y=False)
    temperature_figure.update_yaxes(
        title_text="Velocità (%/h) e accelerazione (%/h^2)", secondary_y=True
    )
    temperature_figure.update_layout(
        title="Temperatura e velocità di crescita", hovermode="x unified"
    )
    style_figure(temperature_figure)

    derived_figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.10,
        subplot_titles=[
            "Velocità di crescita",
            "Velocità specifica",
            "Differenza termica impasto-ambiente",
        ],
    )
    derived_series = (
        (
            "growth_rate_value_h",
            f"Velocità ({summary.signal_unit}/h)",
            "#69D7A0",
            1,
        ),
        ("specific_growth_rate_h", "Velocità specifica (1/h)", "#C99AFF", 2),
        ("delta_t_c", "ΔT (°C)", "#F1B95E", 3),
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
    derived_figure.update_yaxes(title_text="°C", row=3, col=1)
    derived_figure.update_xaxes(title_text="Tempo sessione", row=3, col=1)
    derived_figure.update_layout(
        title="Curve quantitative derivate",
        hovermode="x unified",
    )
    style_figure(derived_figure, height=760)

    if single_results_view == "TESTO":
        parameters_tab, details_tab, data_tab = st.tabs(
            ["Parametri", "Ricetta e dettagli", "Dati"]
        )

        with parameters_tab:
            st.subheader("Parametri della lievitazione")
            st.caption(
                "Fingerprint quantitativo calcolato sulla timeline originale della sessione."
            )
            render_fingerprint_summary(fingerprint)

        with details_tab:
            if session_metadata:
                render_metadata(session_metadata)
            else:
                st.info("Nessun metadato disponibile per questa sessione.")

        with data_tab:
            st.caption("Dati elaborati con i parametri attualmente selezionati.")
            st.dataframe(analysis.reset_index(), width="stretch", hide_index=True)
    else:
        chart_tab, derived_tab, dynamics_tab = st.tabs(
            ["Grafico principale", "Curve derivate", "Temperatura e dinamica"]
        )

        with chart_tab:
            single_view = st.segmented_control(
                "Tipo di grafico",
                ["Serie temporali", "Correlazione 2 variabili"],
                default="Serie temporali",
                required=True,
                format_func=lambda value: {
                    "Serie temporali": "Andamento nel tempo",
                    "Correlazione 2 variabili": "Correlazione",
                }[value],
                key="single_graph_view",
                width="stretch",
            )
            if single_view == "Serie temporali":
                selected_fingerprint_events = st.multiselect(
                    "Eventi caratteristici sul grafico",
                    list(FINGERPRINT_EVENT_LABELS),
                    default=["t25", "t50", "t100", "max_rate", "plateau"],
                    format_func=lambda value: FINGERPRINT_EVENT_LABELS[value],
                    help="Le metriche usano sempre la timeline originale della sessione.",
                    key="single_graph_events",
                )
                event_figure = go.Figure(volume_figure)
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
                    st.plotly_chart(
                        temperature_overview_figure,
                        width="stretch",
                        config={"displaylogo": False},
                    )
                else:
                    st.caption("Questa sessione non contiene dati di temperatura.")
            else:
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

        with derived_tab:
            if derived_figure.data:
                st.plotly_chart(
                    derived_figure,
                    width="stretch",
                    config={"displaylogo": False},
                )
            else:
                st.info("Dati insufficienti per calcolare le curve derivate.")

        with dynamics_tab:
            st.plotly_chart(
                temperature_figure,
                width="stretch",
                config={"displaylogo": False},
            )
