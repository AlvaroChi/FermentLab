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
    analyze_session,
    summarize_session,
)


st.set_page_config(page_title="FermentLab Analyzer", page_icon="🫧", layout="wide")


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


def fmt_number(value: float, suffix: str, digits: int = 1) -> str:
    if not math.isfinite(value):
        return "—"
    return f"{value:.{digits}f}{suffix}"


def format_recipe_value(key: str, value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Sì" if value else "No"
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        if key in {"total_flour_g", "initial_dough_mass_g"}:
            return f"{float(value):.0f} g"
        if key in {"hydration_pct", "salt_pct", "yeast_pct"}:
            return f"{float(value):.1f}%"
        if key == "autolyse_min":
            return f"{float(value):.0f} min"
        if key == "flour_count":
            return f"{int(float(value))}"
        return f"{float(value):.2f}"
    return str(value)


defaults = InfluxSettings.from_environment()

st.title("FermentLab Analyzer")
st.caption("Curve operative lette direttamente da InfluxDB, senza esportazioni manuali.")

with st.sidebar:
    st.header("Connessione InfluxDB")
    url = st.text_input("URL", value=defaults.url)
    org = st.text_input("Organizzazione", value=defaults.org)
    bucket = st.text_input("Bucket", value=defaults.bucket)
    measurement = st.text_input("Measurement", value=defaults.measurement)
    token_override = st.text_input(
        "Token read-only (override facoltativo)", value="", type="password"
    )
    token = token_override or defaults.token
    if defaults.token:
        st.caption("Token caricato dall'ambiente locale.")
    lookback_days = st.number_input(
        "Sessioni degli ultimi giorni", min_value=1, max_value=3650, value=365
    )
    if st.button("Aggiorna dati", width="stretch"):
        st.cache_data.clear()

if not token:
    st.info("Inserisci un token InfluxDB con permessi di sola lettura.")
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

labels = {
    row.session_id: f"{row.session_id} · {row.last_seen:%Y-%m-%d %H:%M} UTC"
    for row in sessions.itertuples()
}
session_id = st.selectbox(
    "Sessione",
    sessions["session_id"].tolist(),
    format_func=lambda value: labels[value],
)

with st.expander("Parametri di elaborazione"):
    col_a, col_b = st.columns(2)
    smoothing_minutes = col_a.slider("Filtro mediana (min)", 1, 30, 5)
    post_smoothing_minutes = col_b.slider(
        "Smussatura finale media (min)", 0, 30, 3
    )

    col_c, col_d = st.columns(2)
    despike_window_minutes = col_c.slider("Finestra despike (min)", 0, 20, 3)
    despike_sigma = col_d.slider("Soglia despike (sigma)", 0.0, 8.0, 3.5, 0.5)

    col_e, col_f = st.columns(2)
    baseline_offset_minutes = col_e.slider(
        "Ignora i primi minuti", 0, 180, 0, 5
    )
    baseline_minutes = col_f.slider("Durata baseline (min)", 1, 30, 5)

    col_g, col_h = st.columns(2)
    rate_window_minutes = col_g.slider("Finestra velocità (min)", 5, 120, 30, 5)
    acceleration_window_minutes = col_h.slider(
        "Finestra accelerazione (min)", 10, 180, 60, 5
    )

    minimum_slope_points = st.slider(
        "Punti minimi per regressione", 3, 15, 5
    )

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
except Exception as error:
    st.error(f"Analisi della sessione non riuscita: {error}")
    st.stop()

metric_row_one = st.columns(2)
metric_row_one[0].metric("Durata", fmt_number(summary.duration_hours, " h"))
metric_row_one[1].metric(
    f"{summary.signal_label} iniziale",
    fmt_number(summary.baseline_value, f" {summary.signal_unit}"),
)
metric_row_two = st.columns(2)
metric_row_two[0].metric(
    f"{summary.signal_label} attuale",
    fmt_number(summary.current_value, f" {summary.signal_unit}"),
)
metric_row_two[1].metric("Crescita", fmt_number(summary.current_growth_pct, "%"))
metric_row_ratio = st.columns(1)
metric_row_ratio[0].metric("Rapporto attuale/iniziale", fmt_number(summary.current_ratio_x, "x", 2))
metric_row_three = st.columns(2)
metric_row_three[0].metric(
    "Velocità attuale", fmt_number(summary.current_growth_rate_pct_h, "%/h")
)
metric_row_three[1].metric(
    "Crescita massima", fmt_number(summary.maximum_growth_pct, "%")
)
metric_row_four = st.columns(1)
metric_row_four[0].metric(
    "Accelerazione attuale", fmt_number(summary.current_growth_accel_pct_h2, "%/h^2")
)

recipe = session_metadata.get("recipe", {}) if isinstance(session_metadata, dict) else {}
recipe_rows = []
if isinstance(recipe, dict) and recipe:
    for key, label in (
        ("name", "Nome ricetta"),
        ("preset_id", "Preset"),
        ("total_flour_g", "Farina totale"),
        ("hydration_pct", "Idratazione"),
        ("salt_pct", "Sale"),
        ("yeast_type", "Lievito"),
        ("yeast_pct", "Lievito %"),
        ("autolyse", "Autolisi"),
        ("autolyse_min", "Autolisi (min)"),
        ("initial_dough_mass_g", "Impasto iniziale"),
        ("notes", "Note"),
        ("flour_count", "Numero farine"),
        ("flours_summary", "Mix farine"),
    ):
        if key in recipe:
            recipe_rows.append((label, format_recipe_value(key, recipe[key])))

if recipe_rows:
    st.subheader("Ricetta letta dallo START")
    st.dataframe(
        pd.DataFrame(recipe_rows, columns=["Parametro", "Valore"]),
        width="stretch",
        hide_index=True,
    )
elif session_metadata:
    st.info(
        "Ho trovato metadati di sessione ma non ancora un blocco ricetta completo."
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
st.plotly_chart(volume_figure, width="stretch")

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
        name="Velocità crescita",
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
temperature_figure.update_yaxes(title_text="Temperatura (°C)", secondary_y=False)
temperature_figure.update_yaxes(
    title_text="Velocità (%/h) e accelerazione (%/h^2)", secondary_y=True
)
temperature_figure.update_layout(
    title="Temperatura e velocità di crescita", hovermode="x unified"
)
st.plotly_chart(temperature_figure, width="stretch")

with st.expander("Dati elaborati"):
    st.dataframe(analysis.reset_index(), width="stretch", hide_index=True)
