#include "InfluxUploader.h"

#include <HTTPClient.h>
#include <WiFi.h>

#include <algorithm>
#include <cstring>

#include "Config.h"
#include "secrets.h"

namespace {

String urlEncode(const char* value) {
  static constexpr char hex[] = "0123456789ABCDEF";
  String encoded;
  while (*value != '\0') {
    const uint8_t character = static_cast<uint8_t>(*value++);
    const bool unreserved =
        (character >= 'a' && character <= 'z') ||
        (character >= 'A' && character <= 'Z') ||
        (character >= '0' && character <= '9') || character == '-' ||
        character == '_' || character == '.' || character == '~';
    if (unreserved) {
      encoded += static_cast<char>(character);
    } else {
      encoded += '%';
      encoded += hex[character >> 4];
      encoded += hex[character & 0x0F];
    }
  }
  return encoded;
}

bool isPlaceholder(const char* value, const char* placeholder) {
  return value == nullptr || value[0] == '\0' ||
         std::strcmp(value, placeholder) == 0;
}

}  // namespace

void InfluxUploader::begin(PersistentQueue& queue) {
  queue_ = &queue;
  retryDelayMs_ = Config::INFLUX_RETRY_INITIAL_MS;
}

InfluxUploadEvent InfluxUploader::tick() {
  if (queue_ == nullptr) {
    return InfluxUploadEvent::None;
  }
  if (!configurationAvailable()) {
    if (!configurationWarningEmitted_) {
      configurationWarningEmitted_ = true;
      return InfluxUploadEvent::ConfigurationMissing;
    }
    return InfluxUploadEvent::None;
  }
  if (WiFi.status() != WL_CONNECTED) {
    return InfluxUploadEvent::None;
  }

  const uint32_t now = millis();
  if (static_cast<int32_t>(now - nextAttemptMs_) < 0) {
    return InfluxUploadEvent::None;
  }

  String path;
  size_t bytes = 0;
  if (!queue_->peekOldest(path, bytes)) {
    return InfluxUploadEvent::None;
  }
  File segment = queue_->openForRead(path.c_str());
  if (!segment) {
    scheduleFailure(now);
    lastHttpCode_ = 0;
    return InfluxUploadEvent::Failed;
  }

  WiFiClient client;
  HTTPClient http;
  http.setConnectTimeout(Config::INFLUX_HTTP_TIMEOUT_MS);
  http.setTimeout(Config::INFLUX_HTTP_TIMEOUT_MS);
  if (!http.begin(client, writeEndpoint())) {
    segment.close();
    scheduleFailure(now);
    lastHttpCode_ = 0;
    return InfluxUploadEvent::Failed;
  }
  http.addHeader("Authorization", String("Token ") + INFLUX_TOKEN);
  http.addHeader("Content-Type", "text/plain; charset=utf-8");
  http.addHeader("Accept", "application/json");
  lastHttpCode_ = http.sendRequest("POST", &segment, bytes);
  segment.close();
  http.end();

  if (lastHttpCode_ >= 200 && lastHttpCode_ < 300 &&
      queue_->remove(path.c_str())) {
    lastUploadedBytes_ = bytes;
    retryDelayMs_ = Config::INFLUX_RETRY_INITIAL_MS;
    nextAttemptMs_ = now + Config::INFLUX_SUCCESS_PAUSE_MS;
    return InfluxUploadEvent::Sent;
  }

  scheduleFailure(now);
  return InfluxUploadEvent::Failed;
}

bool InfluxUploader::configurationAvailable() const {
    return !isPlaceholder(INFLUX_URL, "http://192.168.x.x:8086") &&
      !isPlaceholder(INFLUX_TOKEN, "YOUR_INFLUXDB_TOKEN") &&
  !isPlaceholder(INFLUX_TOKEN, "YOUR_NAS_INFLUX_TOKEN") &&
  !isPlaceholder(INFLUX_TOKEN, "YOUR_PC_INFLUX_TOKEN") &&
      INFLUX_ORG[0] != '\0' && INFLUX_BUCKET[0] != '\0';
}

String InfluxUploader::writeEndpoint() const {
  String endpoint(INFLUX_URL);
  while (endpoint.endsWith("/")) {
    endpoint.remove(endpoint.length() - 1);
  }
  endpoint += "/api/v2/write?org=";
  endpoint += urlEncode(INFLUX_ORG);
  endpoint += "&bucket=";
  endpoint += urlEncode(INFLUX_BUCKET);
  endpoint += "&precision=s";
  return endpoint;
}

void InfluxUploader::scheduleFailure(uint32_t now) {
  nextAttemptMs_ = now + retryDelayMs_;
  retryDelayMs_ = std::min(retryDelayMs_ * 2,
                           Config::INFLUX_RETRY_MAX_MS);
}
