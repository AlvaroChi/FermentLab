"""Configuration values for read-only InfluxDB access."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class InfluxSettings:
    """Connection settings supplied by the environment or the local UI."""

    url: str = "http://localhost:8086"
    org: str = "FermentLab"
    bucket: str = "fermentlab"
    token: str = ""
    measurement: str = "fermentation_measurement"

    @classmethod
    def from_environment(cls) -> "InfluxSettings":
        return cls(
            url=os.getenv("FERMENTLAB_INFLUX_URL", cls.url).rstrip("/"),
            org=os.getenv("FERMENTLAB_INFLUX_ORG", cls.org),
            bucket=os.getenv("FERMENTLAB_INFLUX_BUCKET", cls.bucket),
            token=os.getenv("FERMENTLAB_INFLUX_TOKEN", ""),
            measurement=os.getenv(
                "FERMENTLAB_INFLUX_MEASUREMENT", cls.measurement
            ),
        )

    def validate(self) -> None:
        missing = [
            name
            for name, value in (
                ("URL", self.url),
                ("organizzazione", self.org),
                ("bucket", self.bucket),
                ("token", self.token),
                ("measurement", self.measurement),
            )
            if not value.strip()
        ]
        if missing:
            raise ValueError("Configurazione Influx incompleta: " + ", ".join(missing))
