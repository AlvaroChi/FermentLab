#pragma once

#include <Arduino.h>

enum class SensorState : uint8_t { Ok, Missing, Error, Stale };

struct SensorStatus {
  SensorStatus() = default;
  SensorStatus(SensorState stateValue, const char* errorCodeValue,
               uint64_t ageMsValue)
      : state(stateValue), errorCode(errorCodeValue), ageMs(ageMsValue) {}

  SensorState state = SensorState::Missing;
  const char* errorCode = nullptr;
  uint64_t ageMs = 0;
};

struct VesselSample {
  const char* vesselId = "";
  uint64_t sequence = 0;
  uint64_t vesselSequence = 0;
  uint64_t elapsedMs = 0;
  SensorStatus dough;
  SensorStatus ambient;
  SensorStatus tof;
  float temperatureDoughC = NAN;
  float temperatureAmbientC = NAN;
  float humidityPct = NAN;
  float distanceMm = NAN;
  float distanceCalibratedMm = NAN;
  float doughHeightMm = NAN;
  float doughGrowthMm = NAN;
  float volumeMl = NAN;
};

class SensorHub {
 public:
  virtual ~SensorHub() = default;
  virtual bool begin() = 0;
  virtual VesselSample readVessel(const char* vesselId, uint64_t sequence,
                                  uint64_t elapsedMs) = 0;
};
