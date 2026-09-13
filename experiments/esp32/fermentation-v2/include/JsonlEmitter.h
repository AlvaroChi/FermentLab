#pragma once

#include <Arduino.h>

#include "SensorHub.h"

class JsonlEmitter {
 public:
  JsonlEmitter(const char* deviceId, const char* sessionId)
      : deviceId_(deviceId), sessionId_(sessionId) {}

  void emitSample(const VesselSample& sample, Print& output) const;

 private:
  const char* deviceId_;
  const char* sessionId_;
};
