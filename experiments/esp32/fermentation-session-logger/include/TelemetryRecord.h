#pragma once

#include <Arduino.h>

struct TelemetryRecord {
  const char* deviceId = "";
  const char* sessionId = "";
  uint32_t sequence = 0;
  time_t timestamp = 0;
  uint32_t elapsedMs = 0;
  float doughTemperatureC = NAN;
  float ambientTemperatureC = NAN;
  float humidityPercent = NAN;
  float distanceMm = NAN;
  float doughHeightMm = NAN;
  float volumeMl = NAN;
};

String toInfluxLineProtocol(const TelemetryRecord& record);
