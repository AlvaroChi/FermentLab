#pragma once

#include <Arduino.h>
#include <FS.h>

class PersistentQueue {
 public:
  bool begin(fs::FS& filesystem);
  bool enqueue(const String& lineProtocol);
  bool peekOldest(String& path, size_t& bytes) const;
  File openForRead(const char* path) const;
  bool remove(const char* path);
  size_t segmentCount() const;
  size_t pendingBytes() const;

 private:
  bool scan(uint32_t* minimumId, uint32_t* maximumId, size_t* count,
            size_t* bytes) const;
  bool repairSegment(const String& path);
  size_t validSegmentBytes(const String& path) const;
  String segmentPath(uint32_t id) const;

  fs::FS* filesystem_ = nullptr;
  uint32_t currentSegmentId_ = 0;
};
