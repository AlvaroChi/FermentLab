"""Access to FermentLab measurements stored in InfluxDB 2.x."""

from __future__ import annotations

from collections.abc import Iterable
import json
import warnings

import pandas as pd
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.warnings import MissingPivotFunction
from influxdb_client.client.write_api import SYNCHRONOUS

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

RESERVED_INFLUX_COLUMNS = {
    "result",
    "table",
    "_start",
    "_stop",
    "_time",
    "_value",
    "_field",
    "_measurement",
}

TEST_SESSION_HINTS = (
    "test",
    "debug",
    "tmp",
    "temp",
    "proof",
    "prove",
    "trial",
    "demo",
    "fake",
)

FAILED_SESSION_HINTS = (
    "fail",
    "failed",
    "error",
    "abort",
    "broken",
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


def _normalize_field_value(value: object) -> object:
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, TypeError):
            pass
    return value


def _session_window(records: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    if records.empty or "_time" not in records:
        raise ValueError("Sessione non trovata o priva di timestamp.")

    start = pd.to_datetime(records["_time"].min(), utc=True)
    stop = pd.to_datetime(records["_time"].max(), utc=True)
    if pd.isna(start) or pd.isna(stop):
        raise ValueError("Sessione non trovata o priva di timestamp validi.")
    if start == stop:
        stop = stop + pd.Timedelta(milliseconds=1)
    else:
        stop = stop + pd.Timedelta(milliseconds=1)
    return start, stop


def summarize_session_records(records: pd.DataFrame) -> dict[str, object]:
    if records.empty:
        return {}

    start, stop = _session_window(records)
    last_seen = stop - pd.Timedelta(milliseconds=1)

    measurements = []
    if "_measurement" in records:
        measurements = sorted(
            str(value)
            for value in records["_measurement"].dropna().astype(str).unique().tolist()
        )

    fields = []
    if "_field" in records:
        fields = sorted(
            str(value)
            for value in records["_field"].dropna().astype(str).unique().tolist()
        )

    session_id = ""
    if "session_id" in records and records["session_id"].notna().any():
        session_id = str(records["session_id"].dropna().iloc[0])

    duration = last_seen - start
    return {
        "session_id": session_id,
        "first_seen": start,
        "last_seen": last_seen,
        "duration_hours": duration.total_seconds() / 3600.0,
        "record_count": int(len(records.index)),
        "sample_count": int(records["_time"].nunique()),
        "measurement_count": len(measurements),
        "measurements": measurements,
        "field_count": len(fields),
        "fields": fields,
    }


def build_merged_points(records: pd.DataFrame, target_session_id: str) -> list[Point]:
    if records.empty:
        return []

    points: list[Point] = []
    for row in records.to_dict("records"):
        measurement = str(row.get("_measurement") or "")
        field_name = str(row.get("_field") or "")
        field_value = row.get("_value")
        timestamp = row.get("_time")
        if not measurement or not field_name or not _is_present(field_value) or timestamp is None:
            continue

        point = Point(measurement).time(pd.Timestamp(timestamp).to_pydatetime(), WritePrecision.NS)
        for key, value in row.items():
            if key in RESERVED_INFLUX_COLUMNS or key == "session_id":
                continue
            if _is_present(value):
                point.tag(str(key), str(value))
        point.tag("session_id", target_session_id)
        point.field(field_name, _normalize_field_value(field_value))
        points.append(point)
    return points


def _normalize_record_value(value: object) -> object:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    value = _normalize_field_value(value)
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def build_record_keys(records: pd.DataFrame) -> set[tuple[object, ...]]:
    if records.empty:
        return set()

    tag_columns = sorted(
        column
        for column in records.columns
        if column not in RESERVED_INFLUX_COLUMNS and column != "session_id"
    )
    keys: set[tuple[object, ...]] = set()
    for row in records.to_dict("records"):
        key = [
            _normalize_record_value(row.get("_time")),
            row.get("_measurement"),
            row.get("_field"),
        ]
        for column in tag_columns:
            key.append(column)
            key.append(_normalize_record_value(row.get(column)))
        keys.add(tuple(key))
    return keys


def preview_merge_records(
    source_records: pd.DataFrame, target_records: pd.DataFrame
) -> dict[str, object]:
    source_summary = summarize_session_records(source_records)
    target_summary = summarize_session_records(target_records)
    source_keys = build_record_keys(source_records)
    target_keys = build_record_keys(target_records)
    overlap_keys = source_keys & target_keys

    source_times = set()
    target_times = set()
    if not source_records.empty and "_time" in source_records:
        source_times = {
            pd.Timestamp(value).isoformat()
            for value in source_records["_time"].dropna().tolist()
        }
    if not target_records.empty and "_time" in target_records:
        target_times = {
            pd.Timestamp(value).isoformat()
            for value in target_records["_time"].dropna().tolist()
        }

    return {
        "source_summary": source_summary,
        "target_summary": target_summary,
        "source_record_count": int(source_summary.get("record_count", 0)),
        "target_record_count": int(target_summary.get("record_count", 0)),
        "overlap_point_count": int(len(overlap_keys)),
        "overlap_timestamp_count": int(len(source_times & target_times)),
        "new_point_count": int(len(source_keys - target_keys)),
        "would_create_target": not bool(target_summary),
    }


def classify_session_summary(summary: dict[str, object]) -> dict[str, object]:
    session_id = str(summary.get("session_id") or "")
    session_name = session_id.lower()
    tags: list[str] = []

    if any(hint in session_name for hint in TEST_SESSION_HINTS):
        tags.append("test")
    if any(hint in session_name for hint in FAILED_SESSION_HINTS):
        tags.append("failed")

    record_count = int(summary.get("record_count") or 0)
    duration_hours = float(summary.get("duration_hours") or 0.0)
    sample_count = int(summary.get("sample_count") or 0)
    field_count = int(summary.get("field_count") or 0)

    reasons: list[str] = []
    if record_count < 20:
        reasons.append("pochi record")
    if sample_count < 5:
        reasons.append("pochi campioni")
    if duration_hours < 0.25:
        reasons.append("durata breve")
    if field_count <= 1:
        reasons.append("pochi campi")
    if "failed" in tags:
        reasons.append("session_id suggerisce failure")
    if "test" in tags:
        reasons.append("session_id suggerisce test")

    is_suspicious = bool(reasons)
    kind = "normal"
    if "failed" in tags:
        kind = "failed"
    elif "test" in tags:
        kind = "test"
    elif is_suspicious:
        kind = "suspicious"

    return {
        "kind": kind,
        "is_test": "test" in tags,
        "is_failed": "failed" in tags,
        "is_suspicious": is_suspicious,
        "reasons": reasons,
    }


class InfluxRepository:
    """Query and manage FermentLab sessions in InfluxDB."""

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

    def _client(self) -> InfluxDBClient:
        return InfluxDBClient(
            url=self.settings.url,
            token=self.settings.token,
            org=self.settings.org,
            timeout=15_000,
        )

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

    def load_session_records(
        self, session_id: str, lookback_days: int = 365
    ) -> pd.DataFrame:
        bucket = _flux_string(self.settings.bucket)
        session = _flux_string(session_id)
        flux = f'''
from(bucket: "{bucket}")
  |> range(start: -{int(lookback_days)}d)
  |> filter(fn: (r) => exists r.session_id)
  |> filter(fn: (r) => r.session_id == "{session}")
  |> sort(columns: ["_time"])
'''.strip()
        frame = self._query(flux)
        if frame.empty:
            return frame

        removable = [column for column in ("result", "table", "_start", "_stop") if column in frame]
        frame = frame.drop(columns=removable)
        if "_time" in frame:
            frame["_time"] = pd.to_datetime(frame["_time"], utc=True)
        return frame.sort_values(["_time", "_measurement", "_field"], na_position="last")

    def load_session_admin_info(
        self, session_id: str, lookback_days: int = 365
    ) -> dict[str, object]:
        records = self.load_session_records(session_id, lookback_days)
        if records.empty:
            return {}

        summary = summarize_session_records(records)
        metadata = self.load_session_metadata(session_id, lookback_days)
        for key in ("_time", "device_id", "schema", "type", "recipe"):
            if key in metadata and _is_present(metadata[key]):
                summary[key] = metadata[key]
        summary.update(classify_session_summary(summary))
        return summary

    def preview_merge_sessions(
        self,
        source_session_id: str,
        target_session_id: str,
        lookback_days: int = 3650,
    ) -> dict[str, object]:
        if source_session_id == target_session_id:
            raise ValueError("Sorgente e destinazione devono essere diverse.")

        source_records = self.load_session_records(source_session_id, lookback_days)
        if source_records.empty:
            raise ValueError(f"Sessione sorgente '{source_session_id}' non trovata.")

        target_records = self.load_session_records(target_session_id, lookback_days)
        preview = preview_merge_records(source_records, target_records)
        preview["source_session_id"] = source_session_id
        preview["target_session_id"] = target_session_id
        return preview

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

    def delete_session(self, session_id: str, lookback_days: int = 3650) -> dict[str, object]:
        records = self.load_session_records(session_id, lookback_days)
        if records.empty:
            raise ValueError(f"Sessione '{session_id}' non trovata.")

        summary = summarize_session_records(records)
        start, stop = _session_window(records)
        predicate = f'session_id="{_flux_string(session_id)}"'

        with self._client() as client:
            client.delete_api().delete(
                start=start.to_pydatetime(),
                stop=stop.to_pydatetime(),
                predicate=predicate,
                bucket=self.settings.bucket,
                org=self.settings.org,
            )

        return summary

    def merge_sessions(
        self,
        source_session_id: str,
        target_session_id: str,
        lookback_days: int = 3650,
        delete_source: bool = False,
    ) -> dict[str, object]:
        if source_session_id == target_session_id:
            raise ValueError("Sorgente e destinazione devono essere diverse.")

        records = self.load_session_records(source_session_id, lookback_days)
        if records.empty:
            raise ValueError(f"Sessione sorgente '{source_session_id}' non trovata.")

        points = build_merged_points(records, target_session_id)
        if not points:
            raise ValueError("La sessione sorgente non contiene punti scrivibili.")

        merged_summary = summarize_session_records(records)
        target_before = self.load_session_admin_info(target_session_id, lookback_days)

        with self._client() as client:
            client.write_api(write_options=SYNCHRONOUS).write(
                bucket=self.settings.bucket,
                org=self.settings.org,
                record=points,
            )

        if delete_source:
            self.delete_session(source_session_id, lookback_days)

        target_after = self.load_session_admin_info(target_session_id, lookback_days)
        return {
            "source_session_id": source_session_id,
            "target_session_id": target_session_id,
            "copied_records": int(merged_summary.get("record_count", 0)),
            "target_before_records": int(target_before.get("record_count", 0)) if target_before else 0,
            "target_after_records": int(target_after.get("record_count", 0)) if target_after else 0,
            "source_deleted": delete_source,
        }
