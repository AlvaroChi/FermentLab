#!/usr/bin/env python3
"""Acquisisce una sessione FermentLab JSONL e la chiude al secondo click."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import serial


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "records" / "fermentations"
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def available_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Troppi file omonimi per {path.name}")


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        port = serial.Serial(args.port, args.baud, timeout=0.2)
    except serial.SerialException as error:
        print(f"ERRORE: impossibile aprire {args.port}: {error}", file=sys.stderr)
        return 2

    partial_path: Path | None = None
    output_file = None
    final_path: Path | None = None
    print(
        f"{args.port} collegata. Premi GPIO27 per iniziare; "
        "premilo ancora per chiudere."
    )

    try:
        while True:
            raw_line = port.readline()
            if not raw_line:
                continue
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                print(f"[seriale] {line}")
                continue

            print(json.dumps(payload, ensure_ascii=False, indent=2))
            event_type = payload.get("type")

            if event_type == "session_start":
                if output_file is not None:
                    output_file.close()
                    output_file = None
                session_id = str(payload.get("session_id", "sessione"))
                safe_session_id = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id)
                partial_path = available_path(
                    output_dir / f".{safe_session_id}.partial.jsonl"
                )
                output_file = partial_path.open("x", encoding="utf-8", newline="\n")
                print(f"REGISTRAZIONE ATTIVA: {partial_path}")

            if output_file is not None:
                output_file.write(
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                    + "\n"
                )
                output_file.flush()
                os.fsync(output_file.fileno())

            if event_type == "session_end" and output_file is not None:
                suggested = str(payload.get("suggested_filename", "sessione.jsonl"))
                if not SAFE_FILENAME.fullmatch(suggested):
                    raise ValueError(f"Nome file non valido ricevuto: {suggested}")
                output_file.close()
                output_file = None
                final_path = available_path(output_dir / suggested)
                if partial_path is None:
                    raise RuntimeError("File parziale non disponibile")
                partial_path.replace(final_path)
                print(f"SESSIONE SALVATA: {final_path}")
                return 0
    except KeyboardInterrupt:
        print("\nAcquisizione interrotta.")
        return 130
    except (OSError, RuntimeError, ValueError, serial.SerialException) as error:
        print(f"ERRORE: {error}", file=sys.stderr)
        return 3
    finally:
        if output_file is not None:
            output_file.flush()
            os.fsync(output_file.fileno())
            output_file.close()
        port.close()
        if final_path is None and partial_path is not None:
            print(f"SESSIONE INCOMPLETA CONSERVATA: {partial_path}")


if __name__ == "__main__":
    raise SystemExit(main())
