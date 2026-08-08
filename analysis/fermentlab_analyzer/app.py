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
    add_relative_time,
    analyze_session,
    build_recipe_sections,
    build_recipe_summary,
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
        return "—"
    return f"{value:.{digits}f}{suffix}"


def fmt_timestamp(value: object) -> str:
    if value is None:
        return "—"
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return "—"
    return f"{timestamp:%Y-%m-%d %H:%M:%S} UTC"


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
        <h1>Dal sensore a una decisione chiara.</h1>
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
else:
    compare_analyses: list[dict[str, object]] = []
    compare_errors: list[str] = []
    offset_hours: dict[str, float] = {}
    compare_metadata: dict[str, dict[str, object]] = {}

    with st.expander("Offset temporali", expanded=True):
        for session_name in selected_session_ids:
            current_offset = float(st.session_state.compare_offsets.get(session_name, 0.0))
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
            offset_hours_value = float(offset_hours_value) + float(offset_minutes_value) / 60.0
            st.session_state.compare_offsets[session_name] = float(offset_hours_value)
            offset_hours[session_name] = float(offset_hours_value)

    alignment_event = st.text_input(
        "Etichetta dell'evento di allineamento",
        value="Evento di riferimento",
    )

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
        except Exception as error:
            compare_errors.append(f"{session_name}: {error}")

    if compare_errors:
        for error_text in compare_errors:
            st.warning(error_text)

    if not compare_analyses:
        st.error("Nessuna sessione comparabile è stata caricata.")
        st.stop()

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
    style_figure(temperature_figure)

    chart_tab, dynamics_tab, details_tab, data_tab = st.tabs(
        ["Andamento", "Temperatura e dinamica", "Ricetta e dettagli", "Dati"]
    )
    with chart_tab:
        if single_view == "Serie temporali":
            st.plotly_chart(volume_figure, width="stretch", config={"displaylogo": False})
        elif "metric_options" in locals() and x_metric != y_metric:
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
                    line={"color": "#247a52", "width": 2},
                    marker={"size": 5, "color": "#d28a26"},
                    hovertemplate=(
                        f"{session_id}<br>{x_metric} = %{{x:.3f}}"
                        f"<br>{y_metric} = %{{y:.3f}}<extra></extra>"
                    ),
                )
            )
            correlation_figure.update_layout(
                title="Correlazione tra due variabili",
                xaxis_title=next(
                    label for name, label in metric_options if name == x_metric
                ),
                yaxis_title=next(
                    label for name, label in metric_options if name == y_metric
                ),
                hovermode="closest",
            )
            style_figure(correlation_figure)
            st.plotly_chart(
                correlation_figure,
                width="stretch",
                config={"displaylogo": False},
            )
        else:
            st.info("Scegli due variabili diverse per visualizzare la correlazione.")

    with dynamics_tab:
        st.plotly_chart(
            temperature_figure,
            width="stretch",
            config={"displaylogo": False},
        )

    with details_tab:
        if session_metadata:
            render_metadata(session_metadata)
        else:
            st.info("Nessun metadato disponibile per questa sessione.")

    with data_tab:
        st.caption("Dati elaborati con i parametri attualmente selezionati.")
        st.dataframe(analysis.reset_index(), width="stretch", hide_index=True)
