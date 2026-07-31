#include "PersistentQueue.h"

#include <cstring>

#include "Config.h"

namespace {

bool parseSegmentId(const char* rawName, uint32_t& id) {
  const char* name = std::strrchr(rawName, '/');
  name = name == nullptr ? rawName : name + 1;
  unsigned long parsed = 0;
  char trailing = '\0';
  if (std::sscanf(name, "queue-%08lu.lp%c", &parsed, &trailing) != 1) {
    return false;
  }
  id = static_cast<uint32_t>(parsed);
  return true;
}

}  // namespace

bool PersistentQueue::begin(fs::FS& filesystem) {
  filesystem_ = &filesystem;
  if (!filesystem_->exists(Config::TELEMETRY_QUEUE_DIRECTORY) &&
      !filesystem_->mkdir(Config::TELEMETRY_QUEUE_DIRECTORY)) {
    return false;
  }

  // A power loss can leave only the final line incomplete. Keep every fully
  // terminated record and truncate only the damaged tail.
  File directory = filesystem_->open(Config::TELEMETRY_QUEUE_DIRECTORY);
  if (!directory || !directory.isDirectory()) {
    return false;
  }
  for (File entry = directory.openNextFile(); entry;
       entry = directory.openNextFile()) {
    uint32_t ignored = 0;
    if (!entry.isDirectory() && parseSegmentId(entry.name(), ignored)) {
      const char* rawName = entry.name();
      const char* baseName = std::strrchr(rawName, '/');
      baseName = baseName == nullptr ? rawName : baseName + 1;
      const String path =
          String(Config::TELEMETRY_QUEUE_DIRECTORY) + "/" + baseName;
      entry.close();
      if (!repairSegment(path)) {
        directory.close();
        return false;
      }
    }
  }
  directory.close();

  uint32_t minimumId = 0;
  uint32_t maximumId = 0;
  size_t count = 0;
  size_t bytes = 0;
  if (!scan(&minimumId, &maximumId, &count, &bytes)) {
    return false;
  }
  currentSegmentId_ = count == 0 ? 0 : maximumId;
  if (count > 0) {
    const String currentPath = segmentPath(currentSegmentId_);
    File current = filesystem_->open(currentPath, FILE_READ);
    if (!current) {
      return false;
    }
    const size_t size = current.size();
    current.close();
    if (validSegmentBytes(currentPath) < size) {
      // Never append after a partial record: doing so would make two damaged
      // records. The valid prefix can still be uploaded from the old segment.
      ++currentSegmentId_;
    }
  }
  return true;
}

bool PersistentQueue::enqueue(const String& lineProtocol) {
  if (filesystem_ == nullptr || lineProtocol.length() == 0 ||
      lineProtocol.indexOf('\n') >= 0 || lineProtocol.indexOf('\r') >= 0) {
    return false;
  }

  String path = segmentPath(currentSegmentId_);
  File segment = filesystem_->open(path, FILE_APPEND);
  if (!segment) {
    return false;
  }
  const size_t existingBytes = segment.size();
  if (existingBytes > 0 &&
      existingBytes + lineProtocol.length() + 1 >
          Config::TELEMETRY_SEGMENT_MAX_BYTES) {
    segment.close();
    path = segmentPath(++currentSegmentId_);
    segment = filesystem_->open(path, FILE_APPEND);
    if (!segment) {
      return false;
    }
  }
  const size_t written = segment.print(lineProtocol);
  const size_t newlineWritten = segment.write('\n');
  segment.flush();
  segment.close();
  const bool complete =
      written == lineProtocol.length() && newlineWritten == 1;
  if (!complete) {
    ++currentSegmentId_;
  }
  return complete;
}

bool PersistentQueue::peekOldest(String& path, size_t& bytes) const {
  uint32_t minimumId = 0;
  uint32_t maximumId = 0;
  size_t count = 0;
  size_t ignoredBytes = 0;
  if (!scan(&minimumId, &maximumId, &count, &ignoredBytes) || count == 0) {
    return false;
  }
  path = segmentPath(minimumId);
  File file = filesystem_->open(path, FILE_READ);
  if (!file) {
    return false;
  }
  file.close();
  bytes = validSegmentBytes(path);
  return bytes > 0;
}

File PersistentQueue::openForRead(const char* path) const {
  return filesystem_ == nullptr ? File() : filesystem_->open(path, FILE_READ);
}

bool PersistentQueue::remove(const char* path) {
  if (filesystem_ == nullptr || path == nullptr ||
      !String(path).startsWith(Config::TELEMETRY_QUEUE_DIRECTORY)) {
    return false;
  }
  const String currentPath = segmentPath(currentSegmentId_);
  if (!filesystem_->remove(path)) {
    return false;
  }
  if (currentPath == path) {
    ++currentSegmentId_;
  }
  return true;
}

size_t PersistentQueue::segmentCount() const {
  uint32_t minimumId = 0;
  uint32_t maximumId = 0;
  size_t count = 0;
  size_t bytes = 0;
  return scan(&minimumId, &maximumId, &count, &bytes) ? count : 0;
}

size_t PersistentQueue::pendingBytes() const {
  uint32_t minimumId = 0;
  uint32_t maximumId = 0;
  size_t count = 0;
  size_t bytes = 0;
  return scan(&minimumId, &maximumId, &count, &bytes) ? bytes : 0;
}

bool PersistentQueue::scan(uint32_t* minimumId, uint32_t* maximumId,
                           size_t* count, size_t* bytes) const {
  if (filesystem_ == nullptr) {
    return false;
  }
  File directory = filesystem_->open(Config::TELEMETRY_QUEUE_DIRECTORY);
  if (!directory || !directory.isDirectory()) {
    return false;
  }
  *count = 0;
  *bytes = 0;
  for (File entry = directory.openNextFile(); entry;
       entry = directory.openNextFile()) {
    uint32_t id = 0;
    if (!entry.isDirectory() && parseSegmentId(entry.name(), id)) {
      if (*count == 0 || id < *minimumId) {
        *minimumId = id;
      }
      if (*count == 0 || id > *maximumId) {
        *maximumId = id;
      }
      ++*count;
      *bytes += entry.size();
    }
    entry.close();
  }
  directory.close();
  return true;
}

bool PersistentQueue::repairSegment(const String& path) {
  File file = filesystem_->open(path, FILE_READ);
  if (!file) {
    return false;
  }
  const size_t originalSize = file.size();
  file.close();
  if (originalSize == 0 || validSegmentBytes(path) == 0) {
    // There is no complete record to recover.
    return filesystem_->remove(path);
  }
  return true;
}

size_t PersistentQueue::validSegmentBytes(const String& path) const {
  File file = filesystem_->open(path, FILE_READ);
  if (!file) {
    return 0;
  }
  size_t validSize = 0;
  size_t position = 0;
  while (file.available()) {
    if (file.read() == '\n') {
      validSize = position + 1;
    }
    ++position;
  }
  file.close();
  return validSize;
}

String PersistentQueue::segmentPath(uint32_t id) const {
  char path[64] = {};
  std::snprintf(path, sizeof(path), "%s/queue-%08lu.lp",
                Config::TELEMETRY_QUEUE_DIRECTORY,
                static_cast<unsigned long>(id));
  return String(path);
}
