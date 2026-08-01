#include "TelemetryRecord.h"

namespace {

void appendEscapedTag(String& output, const char* value) {
  while (*value != '\0') {
    if (*value == ' ' || *value == ',' || *value == '=' || *value == '\\') {
      output += '\\';
    }
    output += *value++;
  }
}

void appendFloatField(String& output, const char* key, float value,
                      bool& hasField) {
  if (isnan(value) || isinf(value)) {
    return;
  }
  output += hasField ? ',' : ' ';
  output += key;
  output += '=';
  output += String(value, 3);
  hasField = true;
}

void appendIntegerField(String& output, const char* key, uint32_t value,
                        bool& hasField) {
  output += hasField ? ',' : ' ';
  output += key;
  output += '=';
  output += String(value);
  output += 'i';
  hasField = true;
}

}  // namespace

String toInfluxLineProtocol(const TelemetryRecord& record) {
  String line;
  line.reserve(384);
  line += "fermentation_measurement,device_id=";
  appendEscapedTag(line, record.deviceId);
  line += ",session_id=";
  appendEscapedTag(line, record.sessionId);

  bool hasField = false;
  appendIntegerField(line, "sequence", record.sequence, hasField);
  appendIntegerField(line, "elapsed_ms", record.elapsedMs, hasField);
  appendFloatField(line, "temperature_dough_c", record.doughTemperatureC,
                   hasField);
  appendFloatField(line, "temperature_ambient_c",
                   record.ambientTemperatureC, hasField);
  appendFloatField(line, "humidity_pct", record.humidityPercent, hasField);
  appendFloatField(line, "distance_mm", record.distanceMm, hasField);
  appendFloatField(line, "dough_height_mm", record.doughHeightMm, hasField);
  appendFloatField(line, "volume_ml", record.volumeMl, hasField);
  line += ' ';
  line += String(static_cast<unsigned long>(record.timestamp));
  return line;
}
