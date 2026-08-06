"""Read-only access to FermentLab measurements stored in InfluxDB 2.x."""

from __future__ import annotations

from collections.abc import Iterable
import json
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

SESSION_START_FIELDS = (
    "recipe",
    "recipe_json",
    "recipe_snapshot",
    "payload",
    "data",
    "json",
    "schema",
    "type",
    "device_id",
    "name",
    "preset_id",
    "total_flour_g",
    "hydration_pct",
    "salt_pct",
    "yeast_type",
    "yeast_pct",
    "autolyse",
    "autolyse_min",
    "initial_dough_mass_g",
    "notes",
)

RECIPE_FIELDS = (
    "name",
    "preset_id",
    "total_flour_g",
    "hydration_pct",
    "salt_pct",
    "yeast_type",
    "yeast_pct",
    "autolyse",
    "autolyse_min",
    "initial_dough_mass_g",
    "notes",
)


def _flux_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _frames(result: pd.DataFrame | list[pd.DataFrame]) -> Iterable[pd.DataFrame]:
    if isinstance(result, list):
        return (frame for frame in result if not frame.empty)
    if result.empty:
        return ()
    return (result,)


def _is_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    try:
        return not pd.isna(value)
    except (TypeError, ValueError):
        return True


def _maybe_parse_json(value: object) -> object:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "[{":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _flatten_recipe_snapshot(recipe: object) -> dict[str, object]:
    parsed = _maybe_parse_json(recipe)
    if not isinstance(parsed, dict):
        return {}

    flattened: dict[str, object] = {}
    for field in RECIPE_FIELDS:
        value = parsed.get(field)
        if _is_present(value):
            flattened[field] = value

    flours = parsed.get("flours")
    if isinstance(flours, list):
        summary: list[str] = []
        flour_count = 0
        for component in flours:
            if not isinstance(component, dict):
                continue
            flour_count += 1
            label = str(
                component.get("flour_id")
                or component.get("name")
                or component.get("id")
                or "misc"
            )
            pct = component.get("pct")
            grams = component.get("grams")
            piece = label
            if _is_present(pct):
                piece += f" {float(pct):.1f}%"
            if _is_present(grams):
                piece += f" ({float(grams):.0f} g)"
            summary.append(piece)
        if flour_count:
            flattened["flour_count"] = flour_count
        if summary:
            flattened["flours_summary"] = ", ".join(summary)

    return flattened


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

    def load_session_metadata(
        self, session_id: str, lookback_days: int = 365
    ) -> dict[str, object]:
        bucket = _flux_string(self.settings.bucket)
        measurement = _flux_string(self.settings.measurement)
        session = _flux_string(session_id)
        field_filter = " or ".join(
            f'r._field == "{_flux_string(field)}"' for field in SESSION_START_FIELDS
        )
        flux = f'''
from(bucket: "{bucket}")
  |> range(start: -{int(lookback_days)}d)
  |> filter(fn: (r) => r.session_id == "{session}")
  |> filter(fn: (r) =>
       r._measurement == "{measurement}" or
       r._measurement == "session_start"
  )
  |> filter(fn: (r) => {field_filter} or r._measurement == "session_start")
  |> keep(columns: ["_time", "_measurement", "_field", "_value", "session_id", "device_id", "schema", "type"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
'''.strip()

        frame = self._query(flux)
        if frame.empty:
            return {}

        removable = [column for column in ("result", "table") if column in frame]
        frame = frame.drop(columns=removable)
        if "_time" in frame:
            frame["_time"] = pd.to_datetime(frame["_time"], utc=True)
            frame = frame.sort_values("_time").drop_duplicates("_time", keep="last")

        row = frame.iloc[-1].to_dict()
        metadata: dict[str, object] = {
            key: row[key]
            for key in ("_time", "session_id", "device_id", "schema", "type")
            if key in row and _is_present(row[key])
        }

        recipe = _flatten_recipe_snapshot(
            row.get("recipe")
            or row.get("recipe_snapshot")
            or row.get("recipe_json")
            or row.get("payload")
            or row.get("data")
            or row.get("json")
        )
        if not recipe:
            scalar_recipe = {
                key: row.get(key)
                for key in RECIPE_FIELDS
                if _is_present(row.get(key))
            }
            if scalar_recipe:
                recipe = scalar_recipe
        if recipe:
            metadata["recipe"] = recipe
        return metadata
