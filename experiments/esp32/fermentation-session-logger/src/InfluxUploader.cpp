#include "InfluxUploader.h"

#include <HTTPClient.h>
#include <WiFi.h>

#include <algorithm>
#include <cstring>

#include "Config.h"
#include "secrets.h"

namespace {

#ifndef INFLUX_HOME_WIFI_SSID
#define INFLUX_HOME_WIFI_SSID WIFI_SSID
#endif

struct InfluxProfileConfig {
  const char* name;
  const char* url;
  const char* token;
  const char* org;
  const char* bucket;
};

const InfluxProfileConfig NAS_PROFILE = {
    "NAS", INFLUX_NAS_URL, INFLUX_NAS_TOKEN, INFLUX_NAS_ORG,
    INFLUX_NAS_BUCKET};

const InfluxProfileConfig PC_PROFILE = {
    "PC", INFLUX_PC_URL, INFLUX_PC_TOKEN, INFLUX_PC_ORG, INFLUX_PC_BUCKET};

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

bool tokenPlaceholder(const char* token) {
  return isPlaceholder(token, "YOUR_INFLUXDB_TOKEN") ||
         isPlaceholder(token, "YOUR_NAS_INFLUX_TOKEN") ||
         isPlaceholder(token, "YOUR_PC_INFLUX_TOKEN");
}

bool profileConfigured(const InfluxProfileConfig& profile) {
  return !isPlaceholder(profile.url, "http://192.168.x.x:8086") &&
         !tokenPlaceholder(profile.token) && profile.org != nullptr &&
         profile.bucket != nullptr && profile.org[0] != '\0' &&
         profile.bucket[0] != '\0';
}

bool connectedToHomeSsid() {
  const String currentSsid = WiFi.SSID();
  return currentSsid.length() > 0 &&
         std::strcmp(currentSsid.c_str(), INFLUX_HOME_WIFI_SSID) == 0;
}

String buildWriteEndpoint(const InfluxProfileConfig& profile) {
  String endpoint(profile.url);
  while (endpoint.endsWith("/")) {
    endpoint.remove(endpoint.length() - 1);
  }
  endpoint += "/api/v2/write?org=";
  endpoint += urlEncode(profile.org);
  endpoint += "&bucket=";
  endpoint += urlEncode(profile.bucket);
  endpoint += "&precision=s";
  return endpoint;
}

int postToProfile(File& segment, size_t bytes,
                  const InfluxProfileConfig& profile) {
  if (!segment.seek(0)) {
    return 0;
  }

  WiFiClient client;
  HTTPClient http;
  http.setConnectTimeout(Config::INFLUX_HTTP_TIMEOUT_MS);
  http.setTimeout(Config::INFLUX_HTTP_TIMEOUT_MS);
  if (!http.begin(client, buildWriteEndpoint(profile))) {
    return 0;
  }
  http.addHeader("Authorization", String("Token ") + profile.token);
  http.addHeader("Content-Type", "text/plain; charset=utf-8");
  http.addHeader("Accept", "application/json");
  const int httpCode = http.sendRequest("POST", &segment, bytes);
  http.end();
  return httpCode;
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

  const InfluxProfileConfig& selectedProfile =
      connectedToHomeSsid() ? NAS_PROFILE : PC_PROFILE;
  lastHttpCode_ = profileConfigured(selectedProfile)
                      ? postToProfile(segment, bytes, selectedProfile)
                      : 0;
  const bool uploadSucceeded =
      lastHttpCode_ >= 200 && lastHttpCode_ < 300;

  segment.close();

  if (uploadSucceeded && queue_->remove(path.c_str())) {
    lastUploadedBytes_ = bytes;
    retryDelayMs_ = Config::INFLUX_RETRY_INITIAL_MS;
    nextAttemptMs_ = now + Config::INFLUX_SUCCESS_PAUSE_MS;
    return InfluxUploadEvent::Sent;
  }

  scheduleFailure(now);
  return InfluxUploadEvent::Failed;
}

bool InfluxUploader::configurationAvailable() const {
  return profileConfigured(NAS_PROFILE) || profileConfigured(PC_PROFILE);
}

void InfluxUploader::scheduleFailure(uint32_t now) {
  nextAttemptMs_ = now + retryDelayMs_;
  retryDelayMs_ = std::min(retryDelayMs_ * 2,
                           Config::INFLUX_RETRY_MAX_MS);
}
