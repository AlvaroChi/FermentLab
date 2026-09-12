#include "SimulatorSensorHub.h"

#include <cstring>

namespace {

ScalarReading ok(float value) {
  return {SensorState::Ok, nullptr, value, 0};
}

ScalarReading failed(const char* code) {
  return {SensorState::Error, code, NAN, 0};
}

float vesselOffset(const char* vesselId) {
  if (strcmp(vesselId, "vessel-2") == 0) return 0.6f;
  if (strcmp(vesselId, "vessel-3") == 0) return -0.4f;
  return 0.0f;
}

}  // namespace

VesselSample SimulatorSensorHub::readVessel(const char* vesselId,
                                            uint64_t sequence,
                                            uint64_t elapsedMs) {
  const float offset = vesselOffset(vesselId);
  const float growth = static_cast<float>(sequence) * 0.7f + offset;
  VesselSample sample;
  sample.vesselId = vesselId;
  sample.sequence = sequence;
  sample.vesselSequence = sequence;
  sample.elapsedMs = elapsedMs;
  sample.doughTemperatureC = ok(24.8f + offset + sequence * 0.05f);
  if (sequence % 5 == 1 && strcmp(vesselId, "vessel-2") == 0) {
    sample.doughTemperatureC = failed("SIMULATED_DS18B20_TIMEOUT");
  }
  sample.ambientTemperatureC = ok(23.1f + sequence * 0.02f);
  sample.humidityPct = ok(62.0f - sequence * 0.1f);
  sample.distanceMm = ok(118.0f - growth);
  sample.distanceCalibratedMm = ok(117.4f - growth);
  sample.doughHeightMm = ok(24.0f + growth);
  sample.doughGrowthMm = ok(growth);
  sample.volumeMl = {SensorState::Missing, nullptr, NAN, 0};
  return sample;
}
