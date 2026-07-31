#!/usr/bin/env python3
"""Monitor seriale interattivo con salvataggio immediato e verificabile."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import serial


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Registra una sessione VL53L0X e inoltra i comandi all'ESP32."
    )
    parser.add_argument("--port", default="COM3", help="Porta seriale (default: COM3).")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate.")
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("logs"),
        help="Cartella dei log (default: ./logs).",
    )
    parser.add_argument(
        "--prefix",
        default="serial",
        help="Prefisso del nome file (default: serial).",
    )
    parser.add_argument(
        "--command",
        action="append",
        default=[],
        help="Comando da inviare automaticamente; ripetibile.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        help="Secondi di acquisizione non interattiva dopo i comandi.",
    )
    return parser.parse_args()


class SessionLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._file = path.open("ab", buffering=0)
        self._lock = threading.Lock()

    def write(self, data: bytes) -> None:
        with self._lock:
            self._file.write(data)
            os.fsync(self._file.fileno())

    def close(self) -> None:
        with self._lock:
            self._file.close()


def send_command(port: serial.Serial, log: SessionLog, command: str) -> None:
    encoded = (command + "\n").encode("utf-8")
    log.write(f"\n# COMANDO: {command}\n".encode("utf-8"))
    port.write(encoded)
    port.flush()
    print(f"> {command}")


def main() -> int:
    args = parse_args()
    if not args.prefix or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for character in args.prefix
    ):
        print("ERRORE: prefisso non valido.", file=sys.stderr)
        return 2
    log_dir = args.log_dir.resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = log_dir / f"{args.prefix}-{timestamp}.log"

    session_log = SessionLog(log_path)
    session_log.write(
        (
            f"# Sessione VL53L0X iniziata {datetime.now().isoformat(timespec='seconds')}\n"
            f"# Porta={args.port}, baud={args.baud}\n"
        ).encode("utf-8")
    )
    print(f"LOG ATTIVO: {log_path}")
    print(f"File creato: {log_path.stat().st_size} byte")

    try:
        port = serial.Serial(args.port, args.baud, timeout=0.1)
    except serial.SerialException as error:
        session_log.write(f"# ERRORE APERTURA PORTA: {error}\n".encode("utf-8"))
        session_log.close()
        print(f"ERRORE: impossibile aprire {args.port}: {error}", file=sys.stderr)
        return 2

    stop_event = threading.Event()
    received_bytes = 0
    received_lock = threading.Lock()

    def serial_reader() -> None:
        nonlocal received_bytes
        while not stop_event.is_set():
            try:
                data = port.read(max(port.in_waiting, 1))
            except serial.SerialException as error:
                print(f"\nERRORE LETTURA SERIALE: {error}", file=sys.stderr)
                stop_event.set()
                return
            if not data:
                continue
            session_log.write(data)
            with received_lock:
                received_bytes += len(data)
            sys.stdout.write(data.decode("utf-8", errors="replace"))
            sys.stdout.flush()

    reader = threading.Thread(target=serial_reader, daemon=True)
    reader.start()

    try:
        time.sleep(1.0)
        for command in args.command:
            send_command(port, session_log, command)

        if args.duration is not None:
            deadline = time.monotonic() + max(args.duration, 0.0)
            while time.monotonic() < deadline and not stop_event.is_set():
                time.sleep(0.1)
        else:
            print("Scrivi una distanza o un comando. Scrivi 'fine' per salvare e uscire.")
            while not stop_event.is_set():
                try:
                    command = input()
                except EOFError:
                    break
                if command.strip().lower() in {"fine", "exit", "quit"}:
                    break
                if command.strip():
                    send_command(port, session_log, command.strip())
    except KeyboardInterrupt:
        print("\nInterruzione richiesta.")
    finally:
        stop_event.set()
        reader.join(timeout=1.0)
        port.close()
        session_log.write(
            f"\n# Sessione terminata {datetime.now().isoformat(timespec='seconds')}\n".encode(
                "utf-8"
            )
        )
        session_log.close()

    with received_lock:
        captured = received_bytes
    print(f"DATI SALVATI: {log_path}")
    print(f"Byte ricevuti dall'ESP32: {captured}")
    print(f"Dimensione finale: {log_path.stat().st_size} byte")
    if captured == 0:
        print("ERRORE: nessun dato ricevuto dall'ESP32.", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
