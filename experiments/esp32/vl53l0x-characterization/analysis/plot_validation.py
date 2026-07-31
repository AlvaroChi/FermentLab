#!/usr/bin/env python3
"""Genera grafici di confronto tra sessioni e prima/dopo calibrazione."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import analyze_vl53l0x as analysis


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session",
        action="append",
        required=True,
        metavar="NOME=FILE",
        help="Sessione da confrontare; opzione ripetibile.",
    )
    parser.add_argument("--slope", type=float, required=True)
    parser.add_argument("--intercept", type=float, required=True)
    parser.add_argument("--min-mm", type=float, default=50.0)
    parser.add_argument("--max-mm", type=float, default=175.0)
    parser.add_argument("-o", "--output-dir", type=Path, required=True)
    return parser.parse_args()


def load_sessions(specifications: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for specification in specifications:
        if "=" not in specification:
            raise ValueError(f"Sessione non valida: {specification}")
        name, raw_path = specification.split("=", 1)
        if not name.strip() or not raw_path.strip():
            raise ValueError(f"Sessione non valida: {specification}")
        frame = analysis.load_measurements([Path(raw_path.strip())])
        frame["sessione"] = name.strip()
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def main() -> int:
    args = parse_args()
    if args.slope == 0:
        raise ValueError("La pendenza non può essere zero.")
    if args.min_mm >= args.max_mm:
        raise ValueError("Il limite minimo deve essere inferiore al massimo.")

    frame = load_sessions(args.session)
    frame = frame[
        frame["distanza_reale_mm"].between(args.min_mm, args.max_mm)
    ].copy()
    if frame.empty:
        raise ValueError("Nessun dato nel range richiesto.")

    frame["errore_grezzo_mm"] = frame["media_mm"] - frame["distanza_reale_mm"]
    frame["distanza_corretta_mm"] = (
        frame["media_mm"] - args.intercept
    ) / args.slope
    frame["errore_corretto_mm"] = (
        frame["distanza_corretta_mm"] - frame["distanza_reale_mm"]
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.style.use("seaborn-v0_8-whitegrid")

    fig, ax = plt.subplots(figsize=(10, 6))
    markers = ["o", "s", "^"]
    for index, (session_name, group) in enumerate(frame.groupby("sessione")):
        ax.scatter(
            group["distanza_reale_mm"],
            group["errore_grezzo_mm"],
            marker=markers[index % len(markers)],
            s=50,
            alpha=0.75,
            label=f"{session_name} ({len(group)} serie)",
        )
    ax.axhline(0, color="black", linestyle="--", linewidth=1)
    ax.set(
        title="Confronto dell'errore grezzo tra sessioni",
        xlabel="Distanza reale [mm]",
        ylabel="Errore misurata - reale [mm]",
        xlim=(args.min_mm - 5, args.max_mm + 5),
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(args.output_dir / "04_confronto_sessioni.png", dpi=180)
    plt.close(fig)

    raw_mae = float(frame["errore_grezzo_mm"].abs().mean())
    corrected_mae = float(frame["errore_corretto_mm"].abs().mean())
    corrected_rmse = float(np.sqrt(np.mean(frame["errore_corretto_mm"] ** 2)))

    fig, (ax_scatter, ax_box) = plt.subplots(
        1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [2.2, 1]}
    )
    ax_scatter.scatter(
        frame["distanza_reale_mm"],
        frame["errore_grezzo_mm"],
        alpha=0.45,
        color="tab:red",
        label=f"Grezzo (MAE {raw_mae:.2f} mm)",
    )
    ax_scatter.scatter(
        frame["distanza_reale_mm"],
        frame["errore_corretto_mm"],
        alpha=0.65,
        color="tab:green",
        label=f"Corretto (MAE {corrected_mae:.2f} mm)",
    )
    ax_scatter.axhline(0, color="black", linestyle="--", linewidth=1)
    ax_scatter.set(
        title="Errore prima e dopo la calibrazione",
        xlabel="Distanza reale [mm]",
        ylabel="Errore [mm]",
        xlim=(args.min_mm - 5, args.max_mm + 5),
    )
    ax_scatter.legend()

    ax_box.boxplot(
        [frame["errore_grezzo_mm"].abs(), frame["errore_corretto_mm"].abs()],
        tick_labels=["Grezzo", "Corretto"],
        showmeans=True,
    )
    ax_box.set(
        title=f"Errore assoluto\nRMSE corretto {corrected_rmse:.2f} mm",
        ylabel="Errore assoluto [mm]",
    )
    fig.suptitle(
        f"Calibrazione finale nel range {args.min_mm:.0f}–{args.max_mm:.0f} mm",
        fontsize=14,
    )
    fig.tight_layout()
    fig.savefig(args.output_dir / "05_prima_dopo_calibrazione.png", dpi=180)
    plt.close(fig)

    print(f"Serie rappresentate: {len(frame)}")
    print(f"MAE grezzo: {raw_mae:.4f} mm")
    print(f"MAE corretto: {corrected_mae:.4f} mm")
    print(f"RMSE corretto: {corrected_rmse:.4f} mm")
    print(f"Grafici salvati in: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as error:
        print(f"ERRORE: {error}", file=sys.stderr)
        raise SystemExit(2)
