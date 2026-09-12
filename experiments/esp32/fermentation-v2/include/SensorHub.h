#pragma once

#include <Arduino.h>

enum class SensorState : uint8_t { Ok, Missing, Error, Stale };

struct ScalarReading {
  SensorState state = SensorState::Missing;
  const char* errorCode = nullptr;
  float value = NAN;
  uint64_t ageMs = 0;
};

struct VesselSample {
  const char* vesselId = "";
  uint64_t sequence = 0;
  uint64_t vesselSequence = 0;
  uint64_t elapsedMs = 0;
  ScalarReading doughTemperatureC;
  ScalarReading ambientTemperatureC;
  ScalarReading humidityPct;
  ScalarReading distanceMm;
  ScalarReading distanceCalibratedMm;
  ScalarReading doughHeightMm;
  ScalarReading doughGrowthMm;
  ScalarReading volumeMl;
};

class SensorHub {
 public:
  virtual ~SensorHub() = default;
  virtual bool begin() = 0;
  virtual VesselSample readVessel(const char* vesselId, uint64_t sequence,
                                  uint64_t elapsedMs) = 0;
};
