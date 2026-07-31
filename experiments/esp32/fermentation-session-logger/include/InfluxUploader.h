#pragma once

#include <Arduino.h>

#include "PersistentQueue.h"

enum class InfluxUploadEvent : uint8_t {
  None,
  Sent,
  Failed,
  ConfigurationMissing,
};

class InfluxUploader {
 public:
  void begin(PersistentQueue& queue);
  InfluxUploadEvent tick();
  int lastHttpCode() const { return lastHttpCode_; }
  size_t lastUploadedBytes() const { return lastUploadedBytes_; }

 private:
  bool configurationAvailable() const;
  String writeEndpoint() const;
  void scheduleFailure(uint32_t now);

  PersistentQueue* queue_ = nullptr;
  uint32_t nextAttemptMs_ = 0;
  uint32_t retryDelayMs_ = 0;
  int lastHttpCode_ = 0;
  size_t lastUploadedBytes_ = 0;
  bool configurationWarningEmitted_ = false;
};
