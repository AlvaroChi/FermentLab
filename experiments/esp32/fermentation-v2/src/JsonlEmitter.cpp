#include "JsonlEmitter.h"

#include <ArduinoJson.h>

namespace {

const char* stateName(SensorState state) {
  switch (state) {
    case SensorState::Ok:
      return "ok";
    case SensorState::Missing:
      return "missing";
    case SensorState::Error:
      return "error";
    case SensorState::Stale:
      return "stale";
  }
  return "error";
}

bool isUsable(const SensorStatus& status) {
  return status.state == SensorState::Ok || status.state == SensorState::Stale;
}

SensorStatus effectiveStatus(const SensorStatus& status, bool valuesAreFinite) {
  if (isUsable(status) && !valuesAreFinite) {
    return {SensorState::Error, "CONTRACT_VALUE_MISSING", 0};
  }
  return status;
}

void addNumberOrNull(JsonObject object, const char* key, float value,
                     const SensorStatus& status) {
  if (isUsable(status) && isfinite(value)) {
    object[key] = value;
  } else {
    object[key] = nullptr;
  }
}

void addSensor(JsonObject sensors, const char* name, const SensorStatus& status) {
  JsonObject sensor = sensors[name].to<JsonObject>();
  sensor["state"] = stateName(status.state);
  sensor["error_code"] = status.errorCode;
  sensor["detail"] = nullptr;
  if (status.state == SensorState::Stale) {
    sensor["age_ms"] = status.ageMs;
  }
}

}  // namespace

void JsonlEmitter::emitSample(const VesselSample& sample, Print& output) const {
  const SensorStatus dough =
      effectiveStatus(sample.dough, isfinite(sample.temperatureDoughC));
  const SensorStatus ambient = effectiveStatus(
      sample.ambient, isfinite(sample.temperatureAmbientC) &&
                          isfinite(sample.humidityPct));
  const SensorStatus tof = effectiveStatus(
      sample.tof, isfinite(sample.distanceMm) &&
                      isfinite(sample.distanceCalibratedMm) &&
                      isfinite(sample.doughHeightMm) &&
                      isfinite(sample.doughGrowthMm));

  JsonDocument json;
  JsonObject document = json.to<JsonObject>();
  document["schema_version"] = "fermentlab.v2";
  document["event_type"] = "sample";
  document["event_id"] =
      String(sessionId_) + ":sample:" + String(sample.sequence) + ":" + sample.vesselId;
  document["device_id"] = deviceId_;
  document["session_id"] = sessionId_;
  document["vessel_id"] = sample.vesselId;
  document["timestamp_utc_ms"] = nullptr;
  document["time_quality"] = "invalid";
  document["elapsed_ms"] = sample.elapsedMs;
  document["sequence"] = sample.sequence;
  document["vessel_sequence"] = sample.vesselSequence;

  addNumberOrNull(document, "temperature_dough_c", sample.temperatureDoughC,
                  dough);
  addNumberOrNull(document, "temperature_ambient_c",
                  sample.temperatureAmbientC, ambient);
  addNumberOrNull(document, "humidity_pct", sample.humidityPct, ambient);
  addNumberOrNull(document, "distance_mm", sample.distanceMm, tof);
  addNumberOrNull(document, "distance_calibrated_mm",
                  sample.distanceCalibratedMm, tof);
  addNumberOrNull(document, "dough_height_mm", sample.doughHeightMm, tof);
  addNumberOrNull(document, "dough_growth_mm", sample.doughGrowthMm, tof);
  addNumberOrNull(document, "volume_ml", sample.volumeMl, tof);

  JsonObject sensors = document["sensors"].to<JsonObject>();
  addSensor(sensors, "dough", dough);
  addSensor(sensors, "ambient", ambient);
  addSensor(sensors, "tof", tof);

  serializeJson(json, output);
  output.println();
}
