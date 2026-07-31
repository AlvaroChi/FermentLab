#!/usr/bin/env python3
"""Analisi dei test di calibrazione ESP32 + VL53L0X.

Accetta sia un CSV pulito sia uno o più log completi del Serial Monitor:
le righe non conformi al formato CSV del firmware vengono ignorate.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd


COLUMNS = [
    "distanza_reale_mm",
    "n_totali",
    "n_valide",
    "n_non_valide",
    "media_mm",
    "mediana_mm",
    "std_mm",
    "min_mm",
    "p05_mm",
    "p25_mm",
    "p75_mm",
    "p95_mm",
    "max_mm",
    "errore_media_mm",
    "errore_mediana_mm",
]

# Una riga firmware ha: reale, tre conteggi interi e undici valori numerici/nan.
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
FLOAT_OR_NAN = rf"(?:{NUMBER}|nan)"
DATA_LINE = re.compile(
    rf"(?<![\d.])("
    rf"{NUMBER},\d+,\d+,\d+"
    rf"(?:,{FLOAT_OR_NAN}){{11}}"
    rf")(?!,)",
    flags=re.IGNORECASE,
)
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analizza CSV o log prodotti dal firmware VL53L0X."
    )
    parser.add_argument(
        "input",
        nargs="+",
        type=Path,
        help="Uno o più file .csv o .log da analizzare.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("analysis/results"),
        help="Cartella risultati (default: analysis/results).",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Mostra anche le finestre dei grafici.",
    )
    return parser.parse_args()


def extract_rows(path: Path) -> list[list[str]]:
    """Estrae soltanto righe CSV firmware valide, anche da log misti."""
    if not path.is_file():
        raise FileNotFoundError(f"File non trovato: {path}")

    rows: list[list[str]] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for raw_line in text.splitlines():
        line = ANSI_ESCAPE.sub("", raw_line)
        match = DATA_LINE.search(line)
        if match:
            fields = match.group(1).split(",")
            if len(fields) == len(COLUMNS):
                rows.append(fields)
    return rows


def load_measurements(paths: list[Path]) -> pd.DataFrame:
    rows: list[list[str]] = []
    for path in paths:
        extracted = extract_rows(path)
        print(f"{path}: {len(extracted)} test trovati")
        rows.extend(extracted)

    if not rows:
        raise ValueError(
            "Nessuna riga CSV valida trovata. Verificare di avere copiato "
            "le righe che iniziano con la distanza reale."
        )

    frame = pd.DataFrame(rows, columns=COLUMNS)
    for column in COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["n_totali"] = frame["n_totali"].astype("Int64")
    frame["n_valide"] = frame["n_valide"].astype("Int64")
    frame["n_non_valide"] = frame["n_non_valide"].astype("Int64")
    frame["percentuale_valide"] = (
        100.0 * frame["n_valide"].astype(float) / frame["n_totali"].astype(float)
    )
    frame["errore_assoluto_media_mm"] = frame["errore_media_mm"].abs()
    frame["errore_assoluto_mediana_mm"] = frame["errore_mediana_mm"].abs()
    return frame


def fit_line(real: np.ndarray, measured: np.ndarray) -> dict[str, float | np.ndarray]:
    if len(real) < 2 or np.unique(real).size < 2:
        raise ValueError("Servono almeno due distanze reali diverse per la regressione.")

    slope, intercept = np.polyfit(real, measured, 1)
    predicted = slope * real + intercept
    residual_sum = float(np.sum((measured - predicted) ** 2))
    total_sum = float(np.sum((measured - np.mean(measured)) ** 2))
    r_squared = 1.0 - residual_sum / total_sum if total_sum > 0 else 1.0
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "r_squared": r_squared,
        "predicted": predicted,
    }


def metric_text(frame: pd.DataFrame, mean_fit: dict[str, float | np.ndarray],
                median_fit: dict[str, float | np.ndarray]) -> str:
    real = frame["distanza_reale_mm"].to_numpy(dtype=float)
    mean = frame["media_mm"].to_numpy(dtype=float)
    median = frame["mediana_mm"].to_numpy(dtype=float)

    raw_rmse = float(np.sqrt(np.mean((mean - real) ** 2)))
    raw_mae = float(np.mean(np.abs(mean - real)))
    median_rmse = float(np.sqrt(np.mean((median - real) ** 2)))
    median_mae = float(np.mean(np.abs(median - real)))

    slope = float(mean_fit["slope"])
    intercept = float(mean_fit["intercept"])
    calibrated = (mean - intercept) / slope
    calibrated_rmse = float(np.sqrt(np.mean((calibrated - real) ** 2)))
    calibrated_mae = float(np.mean(np.abs(calibrated - real)))

    return "\n".join(
        [
            "REGRESSIONE E CALIBRAZIONE VL53L0X",
            "===================================",
            f"Test validi analizzati: {len(frame)}",
            f"Distanze reali distinte: {frame['distanza_reale_mm'].nunique()}",
            "",
            "Modello basato sulla MEDIA:",
            f"  misurata_mm = {slope:.8f} * reale_mm + {intercept:.8f}",
            f"  R^2 = {float(mean_fit['r_squared']):.8f}",
            "  Equazione di calibrazione da applicare a una nuova misura:",
            f"  reale_stimata_mm = (misurata_mm - ({intercept:.8f})) / {slope:.8f}",
            "",
            "Modello basato sulla MEDIANA:",
            f"  misurata_mm = {float(median_fit['slope']):.8f} * reale_mm "
            f"+ {float(median_fit['intercept']):.8f}",
            f"  R^2 = {float(median_fit['r_squared']):.8f}",
            "",
            "Errori grezzi (una riga = una serie di acquisizioni):",
            f"  RMSE media:   {raw_rmse:.4f} mm",
            f"  MAE media:    {raw_mae:.4f} mm",
            f"  RMSE mediana: {median_rmse:.4f} mm",
            f"  MAE mediana:  {median_mae:.4f} mm",
            "",
            "Errori della media dopo calibrazione lineare, sugli stessi dati di fit:",
            f"  RMSE calibrato in-sample: {calibrated_rmse:.4f} mm",
            f"  MAE calibrato in-sample:  {calibrated_mae:.4f} mm",
            "  Nota: questi ultimi valori sono ottimistici; validare su serie separate.",
        ]
    )


def build_summary(frame: pd.DataFrame) -> pd.DataFrame:
    summary = (
        frame.groupby("distanza_reale_mm", as_index=False)
        .agg(
            n_test=("media_mm", "size"),
            n_totali=("n_totali", "sum"),
            n_valide=("n_valide", "sum"),
            n_non_valide=("n_non_valide", "sum"),
            media_misurata_mm=("media_mm", "mean"),
            mediana_misurata_mm=("mediana_mm", "mean"),
            std_intra_serie_media_mm=("std_mm", "mean"),
            std_tra_medie_mm=("media_mm", "std"),
            p05_medio_mm=("p05_mm", "mean"),
            p95_medio_mm=("p95_mm", "mean"),
        )
        .sort_values("distanza_reale_mm")
    )
    summary["percentuale_valide"] = (
        100.0 * summary["n_valide"] / summary["n_totali"]
    )
    summary["errore_media_mm"] = (
        summary["media_misurata_mm"] - summary["distanza_reale_mm"]
    )
    summary["errore_assoluto_media_mm"] = summary["errore_media_mm"].abs()
    summary["errore_mediana_mm"] = (
        summary["mediana_misurata_mm"] - summary["distanza_reale_mm"]
    )
    summary["errore_assoluto_mediana_mm"] = summary["errore_mediana_mm"].abs()
    return summary


def make_plots(frame: pd.DataFrame, summary: pd.DataFrame,
               mean_fit: dict[str, float | np.ndarray], output_dir: Path,
               show: bool) -> None:
    if not show:
        import matplotlib

        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.style.use("seaborn-v0_8-whitegrid")
    x_grid = np.linspace(
        frame["distanza_reale_mm"].min(),
        frame["distanza_reale_mm"].max(),
        300,
    )

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(
        frame["distanza_reale_mm"], frame["media_mm"],
        alpha=0.35, color="tab:blue", label="Media (singole serie)"
    )
    ax.scatter(
        frame["distanza_reale_mm"], frame["mediana_mm"],
        alpha=0.35, color="tab:orange", label="Mediana (singole serie)"
    )
    ax.plot(
        summary["distanza_reale_mm"], summary["media_misurata_mm"],
        "o-", color="tab:blue", linewidth=2, label="Media per distanza"
    )
    ax.plot(
        summary["distanza_reale_mm"], summary["mediana_misurata_mm"],
        "s-", color="tab:orange", linewidth=2, label="Mediana per distanza"
    )
    ax.plot(x_grid, x_grid, "--", color="black", label="Ideale y=x")
    ax.plot(
        x_grid,
        float(mean_fit["slope"]) * x_grid + float(mean_fit["intercept"]),
        color="tab:green",
        label="Regressione della media",
    )
    ax.set(
        title="Distanza reale contro distanza misurata",
        xlabel="Distanza reale [mm]",
        ylabel="Distanza misurata [mm]",
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "01_reale_vs_misurata.png", dpi=180)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.scatter(
        frame["distanza_reale_mm"], frame["errore_assoluto_media_mm"],
        alpha=0.30, color="tab:blue", label="Media (singole serie)"
    )
    ax.scatter(
        frame["distanza_reale_mm"], frame["errore_assoluto_mediana_mm"],
        alpha=0.30, color="tab:orange", label="Mediana (singole serie)"
    )
    ax.plot(
        summary["distanza_reale_mm"], summary["errore_assoluto_media_mm"],
        "o-", color="tab:blue", label="Media per distanza"
    )
    ax.plot(
        summary["distanza_reale_mm"], summary["errore_assoluto_mediana_mm"],
        "s-", color="tab:orange", label="Mediana per distanza"
    )
    ax.set(
        title="Errore assoluto contro distanza",
        xlabel="Distanza reale [mm]",
        ylabel="Errore assoluto [mm]",
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "02_errore_assoluto.png", dpi=180)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.scatter(
        frame["distanza_reale_mm"], frame["std_mm"],
        alpha=0.35, color="tab:purple", label="Singole serie"
    )
    ax.plot(
        summary["distanza_reale_mm"], summary["std_intra_serie_media_mm"],
        "o-", color="tab:purple", linewidth=2, label="Media per distanza"
    )
    ax.set(
        title="Ripetibilità: deviazione standard contro distanza",
        xlabel="Distanza reale [mm]",
        ylabel="Deviazione standard campionaria [mm]",
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "03_deviazione_standard.png", dpi=180)

    if show:
        plt.show()
    else:
        plt.close("all")


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    frame = load_measurements(args.input)
    valid = frame.dropna(
        subset=["distanza_reale_mm", "media_mm", "mediana_mm", "std_mm"]
    ).copy()
    discarded = len(frame) - len(valid)
    if discarded:
        print(f"Attenzione: {discarded} test senza statistiche valide esclusi dal fit.")
    if len(valid) < 2:
        raise ValueError("Non ci sono abbastanza test validi per l'analisi.")

    real = valid["distanza_reale_mm"].to_numpy(dtype=float)
    mean_fit = fit_line(real, valid["media_mm"].to_numpy(dtype=float))
    median_fit = fit_line(real, valid["mediana_mm"].to_numpy(dtype=float))

    summary = build_summary(valid)
    metrics = metric_text(valid, mean_fit, median_fit)

    valid.to_csv(args.output_dir / "dati_estratti.csv", index=False, float_format="%.6f")
    summary.to_csv(
        args.output_dir / "tabella_riassuntiva.csv", index=False, float_format="%.6f"
    )
    (args.output_dir / "regressione_calibrazione.txt").write_text(
        metrics + "\n", encoding="utf-8"
    )
    make_plots(valid, summary, mean_fit, args.output_dir, args.show)

    print("\n" + metrics)
    print("\nTABELLA RIASSUNTIVA")
    print("===================")
    with pd.option_context(
        "display.max_columns", None,
        "display.width", 220,
        "display.float_format", lambda value: f"{value:.3f}",
    ):
        print(summary.to_string(index=False))
    print(f"\nRisultati salvati in: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as error:
        print(f"ERRORE: {error}", file=sys.stderr)
        raise SystemExit(2)
