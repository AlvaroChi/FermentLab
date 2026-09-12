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

void addNumberOrNull(JsonObject object, const char* key, float value) {
  if (isfinite(value)) {
    object[key] = value;
  } else {
    object[key] = nullptr;
  }
}

void addSensor(JsonObject sensors, const char* name, const ScalarReading& reading) {
  JsonObject sensor = sensors[name].to<JsonObject>();
  sensor["state"] = stateName(reading.state);
  sensor["error_code"] = reading.errorCode;
  sensor["detail"] = nullptr;
  if (reading.state == SensorState::Stale) {
    sensor["age_ms"] = reading.ageMs;
  }
}

}  // namespace

void JsonlEmitter::emitSample(const VesselSample& sample, Print& output) const {
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

  addNumberOrNull(document, "temperature_dough_c", sample.doughTemperatureC.value);
  addNumberOrNull(document, "temperature_ambient_c", sample.ambientTemperatureC.value);
  addNumberOrNull(document, "humidity_pct", sample.humidityPct.value);
  addNumberOrNull(document, "distance_mm", sample.distanceMm.value);
  addNumberOrNull(document, "distance_calibrated_mm", sample.distanceCalibratedMm.value);
  addNumberOrNull(document, "dough_height_mm", sample.doughHeightMm.value);
  addNumberOrNull(document, "dough_growth_mm", sample.doughGrowthMm.value);
  document["volume_ml"] = nullptr;

  JsonObject sensors = document["sensors"].to<JsonObject>();
  addSensor(sensors, "dough", sample.doughTemperatureC);
  addSensor(sensors, "ambient", sample.ambientTemperatureC);
  addSensor(sensors, "tof", sample.distanceMm);

  serializeJson(json, output);
  output.println();
}
