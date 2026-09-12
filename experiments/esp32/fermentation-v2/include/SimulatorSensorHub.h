#pragma once

#include "SensorHub.h"

class SimulatorSensorHub final : public SensorHub {
 public:
  bool begin() override { return true; }
  VesselSample readVessel(const char* vesselId, uint64_t sequence,
                          uint64_t elapsedMs) override;
};
