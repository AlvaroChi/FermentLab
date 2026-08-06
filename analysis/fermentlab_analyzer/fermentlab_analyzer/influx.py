"""Read-only access to FermentLab measurements stored in InfluxDB 2.x."""

from __future__ import annotations

from collections.abc import Iterable
import warnings

import pandas as pd
from influxdb_client import InfluxDBClient
from influxdb_client.client.warnings import MissingPivotFunction

from .config import InfluxSettings


MEASUREMENT_FIELDS = (
    "sequence",
    "elapsed_ms",
    "temperature_dough_c",
    "temperature_ambient_c",
    "humidity_pct",
    "distance_mm",
    "dough_height_mm",
    "volume_ml",
)


def _flux_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _frames(result: pd.DataFrame | list[pd.DataFrame]) -> Iterable[pd.DataFrame]:
    if isinstance(result, list):
        return (frame for frame in result if not frame.empty)
    if result.empty:
        return ()
    return (result,)


class InfluxRepository:
    """Query sessions without modifying InfluxDB."""

    def __init__(self, settings: InfluxSettings) -> None:
        settings.validate()
        self.settings = settings

    def _query(self, flux: str) -> pd.DataFrame:
        with InfluxDBClient(
            url=self.settings.url,
            token=self.settings.token,
            org=self.settings.org,
            timeout=15_000,
        ) as client:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", MissingPivotFunction)
                result = client.query_api().query_data_frame(flux)

        frames = list(_frames(result))
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def list_sessions(self, lookback_days: int = 365) -> pd.DataFrame:
        bucket = _flux_string(self.settings.bucket)
        measurement = _flux_string(self.settings.measurement)
        flux = f'''
from(bucket: "{bucket}")
  |> range(start: -{int(lookback_days)}d)
  |> filter(fn: (r) => r._measurement == "{measurement}")
  |> filter(fn: (r) => exists r.session_id)
  |> filter(fn: (r) => r._field == "elapsed_ms")
  |> group(columns: ["session_id"])
  |> last()
  |> keep(columns: ["session_id", "_time"])
  |> sort(columns: ["_time"], desc: true)
'''.strip()
        frame = self._query(flux)
        if frame.empty:
            return pd.DataFrame(columns=["session_id", "last_seen"])

        sessions = frame.rename(columns={"_time": "last_seen"})[
            ["session_id", "last_seen"]
        ].copy()
        sessions["last_seen"] = pd.to_datetime(sessions["last_seen"], utc=True)
        return sessions.drop_duplicates("session_id").sort_values(
            "last_seen", ascending=False
        )

    def load_session(
        self, session_id: str, lookback_days: int = 365
    ) -> pd.DataFrame:
        bucket = _flux_string(self.settings.bucket)
        measurement = _flux_string(self.settings.measurement)
        session = _flux_string(session_id)
        field_filter = " or ".join(
            f'r._field == "{_flux_string(field)}"' for field in MEASUREMENT_FIELDS
        )
        flux = f'''
from(bucket: "{bucket}")
  |> range(start: -{int(lookback_days)}d)
  |> filter(fn: (r) => r._measurement == "{measurement}")
  |> filter(fn: (r) => r.session_id == "{session}")
  |> filter(fn: (r) => {field_filter})
  |> keep(columns: ["_time", "_field", "_value"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
'''.strip()
        frame = self._query(flux)
        if frame.empty:
            return frame

        removable = [column for column in ("result", "table") if column in frame]
        frame = frame.drop(columns=removable)
        frame["_time"] = pd.to_datetime(frame["_time"], utc=True)
        return frame.sort_values("_time").drop_duplicates("_time", keep="last")
