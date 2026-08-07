#include <Arduino.h>
#include <DallasTemperature.h>
#include <LittleFS.h>
#include <OneWire.h>
#include <Preferences.h>
#include <VL53L0X.h>
#include <WiFi.h>
#include <Wire.h>
#include <esp_system.h>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <time.h>

#include "Config.h"
#include "InfluxUploader.h"
#include "PersistentQueue.h"
#include "SessionConfigStore.h"
#include "TelemetryRecord.h"
#include "WebInterface.h"
#include "secrets.h"

#if defined(WIFI_SSID_2) != defined(WIFI_PASSWORD_2)
#error "WIFI_SSID_2 and WIFI_PASSWORD_2 must be defined together"
#endif
#if defined(WIFI_SSID_3) != defined(WIFI_PASSWORD_3)
#error "WIFI_SSID_3 and WIFI_PASSWORD_3 must be defined together"
#endif
#if defined(WIFI_SSID_4) != defined(WIFI_PASSWORD_4)
#error "WIFI_SSID_4 and WIFI_PASSWORD_4 must be defined together"
#endif
#if defined(WIFI_SSID_5) != defined(WIFI_PASSWORD_5)
#error "WIFI_SSID_5 and WIFI_PASSWORD_5 must be defined together"
#endif

namespace {

struct WifiCredential {
  const char* ssid;
  const char* password;
};

const WifiCredential WIFI_CREDENTIALS[] = {
    {WIFI_SSID, WIFI_PASSWORD},
#if defined(WIFI_SSID_2)
    {WIFI_SSID_2, WIFI_PASSWORD_2},
#endif
#if defined(WIFI_SSID_3)
    {WIFI_SSID_3, WIFI_PASSWORD_3},
#endif
#if defined(WIFI_SSID_4)
    {WIFI_SSID_4, WIFI_PASSWORD_4},
#endif
#if defined(WIFI_SSID_5)
    {WIFI_SSID_5, WIFI_PASSWORD_5},
#endif
};
constexpr size_t WIFI_CREDENTIAL_COUNT =
    sizeof(WIFI_CREDENTIALS) / sizeof(WIFI_CREDENTIALS[0]);

void appendInfluxEscapedTag(String& output, const char* value) {
  while (*value != '\0') {
    if (*value == ' ' || *value == ',' || *value == '=' || *value == '\\') {
      output += '\\';
    }
    output += *value++;
  }
}

void appendInfluxIntegerField(String& output, const char* key, uint32_t value,
                              bool& hasField) {
  output += hasField ? ',' : ' ';
  output += key;
  output += '=';
  output += String(value);
  output += 'i';
  hasField = true;
}

void appendInfluxFloatField(String& output, const char* key, float value,
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

void appendInfluxStringField(String& output, const char* key,
                             const String& value, bool& hasField) {
  output += hasField ? ',' : ' ';
  output += key;
  output += '=';
  output += '"';
  for (size_t index = 0; index < value.length(); ++index) {
    const char current = value[index];
    if (current == '\\' || current == '"') {
      output += '\\';
    }
    if (current == '\n' || current == '\r') {
      output += ' ';
      continue;
    }
    output += current;
  }
  output += '"';
  hasField = true;
}

VL53L0X distanceSensor;
OneWire doughOneWire(Config::DS18B20_PIN);
DallasTemperature doughSensor(&doughOneWire);
DeviceAddress doughSensorAddress = {};
bool distanceSensorReady = false;
bool ambientSensorReady = false;
bool doughSensorReady = false;
bool doughConversionPending = false;
uint32_t doughConversionStartedMs = 0;
float lastDoughTemperatureC = NAN;
uint8_t ambientSensorAddress = Config::SHT3X_DEFAULT_I2C_ADDRESS;

bool sessionActive = false;
bool baselineAvailable = false;
float baselineDistanceMm = NAN;
uint32_t sessionStartMs = 0;
uint32_t lastReadingMs = 0;
uint32_t sessionReadingIntervalSeconds =
    Config::DEFAULT_READING_INTERVAL_S;
uint32_t sequenceNumber = 0;
time_t lastMeasurementTimestamp = 0;

char deviceId[32] = {};
char sessionId[64] = {};
char sessionStartDate[9] = {};
char sessionStartTime[7] = {};
char activeFilePath[128] = {};
File sessionFile;
bool storageReady = false;
bool telemetryQueueReady = false;
PersistentQueue telemetryQueue;
InfluxUploader influxUploader;
bool influxFailureActive = false;
WebInterface webInterface;
SessionConfigStore sessionConfigStore;
bool recipeConfigReady = false;

bool wifiAttemptInProgress = false;
bool wifiWasConnected = false;
bool ntpConfigured = false;
bool ntpReadyReported = false;
bool wifiCredentialsWarningEmitted = false;
uint32_t wifiAttemptStartedMs = 0;
uint32_t nextWifiAttemptMs = 0;
uint32_t wifiRetryDelayMs = Config::WIFI_RETRY_INITIAL_MS;
size_t wifiCredentialIndex = 0;
uint32_t lastSensorRetryMs = 0;
uint8_t i2cDeviceCount = 0;
uint8_t i2cScanErrors = 0;
int i2cSdaLevel = HIGH;
int i2cSclLevel = HIGH;
bool i2cBusValid = false;
bool i2cDistancePresent = false;
bool i2cAmbientPresent = false;
char i2cAddressSummary[192] = "non ancora scansionato";
bool statusLedAvailable = false;
bool statusLedOn = false;
uint8_t statusLedRed = 0;
uint8_t statusLedGreen = 0;
uint8_t statusLedBlue = 0;
esp_reset_reason_t bootResetReason = ESP_RST_UNKNOWN;
bool panicSafeMode = false;
bool panicQueueSkipReported = false;
bool panicSessionFileSkipReported = false;
bool panicMeasurementSkipReported = false;
bool sessionFileEnabled = true;
uint32_t nextSessionFlushMs = 0;
RTC_DATA_ATTR uint32_t crashBreadcrumb = 0;
RTC_DATA_ATTR uint32_t lastPanicBreadcrumb = 0;
uint32_t bootCrashBreadcrumb = 0;

constexpr uint32_t BREADCRUMB_IDLE = 100;
constexpr uint32_t BREADCRUMB_START_BEGIN = 200;
constexpr uint32_t BREADCRUMB_START_FILE_OPEN = 210;
constexpr uint32_t BREADCRUMB_START_ACTIVE = 220;
constexpr uint32_t BREADCRUMB_MEASURE_BEGIN = 300;
constexpr uint32_t BREADCRUMB_MEASURE_SENSORS = 310;
constexpr uint32_t BREADCRUMB_MEASURE_SERIAL = 320;
constexpr uint32_t BREADCRUMB_MEASURE_FILE = 330;
constexpr uint32_t BREADCRUMB_MEASURE_QUEUE = 340;
constexpr uint32_t BREADCRUMB_MEASURE_DONE = 399;

enum class StatusLedPattern : uint8_t {
  Off,
  Solid,
  FastBlink,
  SlowBlink,
  DoubleBlink,
  Heartbeat,
};

struct StatusLedState {
  StatusLedPattern pattern;
  uint8_t red;
  uint8_t green;
  uint8_t blue;
};

enum class DistanceInvalidReason : uint8_t {
  None,
  Timeout,
  I2cError,
  DeviceStatus,
  OutOfRange,
};

struct DistanceMeasurement {
  uint16_t millimeters = 0;
  DistanceInvalidReason invalidReason = DistanceInvalidReason::None;

  bool valid() const {
    return invalidReason == DistanceInvalidReason::None;
  }
};

struct FilteredDistance {
  uint16_t values[Config::FILTER_SAMPLE_COUNT] = {};
  size_t validCount = 0;
  size_t attempts = 0;
  uint16_t minimum = 0;
  uint16_t median = 0;
  uint16_t maximum = 0;
  float mean = NAN;

  bool available() const {
    return validCount >= Config::MIN_VALID_SAMPLES;
  }
};

enum class AmbientStatus : uint8_t {
  Ok,
  SensorNotReady,
  CommandError,
  ReadError,
  CrcError,
};

struct AmbientReading {
  float temperatureC = NAN;
  float humidityPercent = NAN;
  AmbientStatus status = AmbientStatus::SensorNotReady;
};

enum class DoughStatus : uint8_t {
  Ok,
  SensorNotReady,
  ConversionPending,
  ReadError,
};

struct DoughReading {
  float temperatureC = NAN;
  DoughStatus status = DoughStatus::SensorNotReady;
};

const char* resetReasonText(esp_reset_reason_t reason) {
  switch (reason) {
    case ESP_RST_POWERON:
      return "POWERON";
    case ESP_RST_EXT:
      return "EXTERNAL";
    case ESP_RST_SW:
      return "SOFTWARE";
    case ESP_RST_PANIC:
      return "PANIC";
    case ESP_RST_INT_WDT:
      return "INT_WDT";
    case ESP_RST_TASK_WDT:
      return "TASK_WDT";
    case ESP_RST_WDT:
      return "WDT";
    case ESP_RST_DEEPSLEEP:
      return "DEEPSLEEP";
    case ESP_RST_BROWNOUT:
      return "BROWNOUT";
    case ESP_RST_SDIO:
      return "SDIO";
    default:
      return "UNKNOWN";
  }
}

void setCrashBreadcrumb(uint32_t code) {
  crashBreadcrumb = code;
}

const char* crashBreadcrumbText(uint32_t code) {
  switch (code) {
    case BREADCRUMB_IDLE:
      return "IDLE";
    case BREADCRUMB_START_BEGIN:
      return "START_BEGIN";
    case BREADCRUMB_START_FILE_OPEN:
      return "START_FILE_OPEN";
    case BREADCRUMB_START_ACTIVE:
      return "START_ACTIVE";
    case BREADCRUMB_MEASURE_BEGIN:
      return "MEASURE_BEGIN";
    case BREADCRUMB_MEASURE_SENSORS:
      return "MEASURE_SENSORS";
    case BREADCRUMB_MEASURE_SERIAL:
      return "MEASURE_SERIAL";
    case BREADCRUMB_MEASURE_FILE:
      return "MEASURE_FILE";
    case BREADCRUMB_MEASURE_QUEUE:
      return "MEASURE_QUEUE";
    case BREADCRUMB_MEASURE_DONE:
      return "MEASURE_DONE";
    default:
      return "UNKNOWN";
  }
}

void printJsonFloat(Print& output, float value, uint8_t decimals = 3) {
  if (isnan(value) || isinf(value)) {
    output.print(F("null"));
  } else {
    output.print(value, decimals);
  }
}

void printJsonString(Print& output, const String& value) {
  output.print('"');
  for (size_t index = 0; index < value.length(); ++index) {
    const char c = value[index];
    if (c == '\\' || c == '"') {
      output.print('\\');
      output.print(c);
    } else if (c == '\n') {
      output.print(F("\\n"));
    } else if (c == '\r') {
      output.print(F("\\r"));
    } else if (c == '\t') {
      output.print(F("\\t"));
    } else {
      output.print(c);
    }
  }
  output.print('"');
}

void emitEvent(const char* type, const char* code) {
  Serial.print(F("{\"schema\":\"fermentlab.event.v1\",\"type\":\""));
  Serial.print(type);
  Serial.print(F("\",\"device_id\":\""));
  Serial.print(deviceId);
  Serial.print(F("\",\"code\":\""));
  Serial.print(code);
  Serial.println(F("\"}"));
}

void writeStatusLedRaw(bool on, uint8_t red = 0, uint8_t green = 0,
                       uint8_t blue = 0) {
  if (!statusLedAvailable) {
    return;
  }
  if (Config::STATUS_LED_IS_NEOPIXEL) {
    if (on) {
      neopixelWrite(Config::STATUS_LED_PIN, red, green, blue);
    } else {
      neopixelWrite(Config::STATUS_LED_PIN, 0, 0, 0);
    }
    return;
  }
  const uint8_t level =
      on == Config::STATUS_LED_ACTIVE_HIGH ? HIGH : LOW;
  digitalWrite(Config::STATUS_LED_PIN, level);
}

void setStatusLed(bool on, uint8_t red, uint8_t green, uint8_t blue) {
  if (!statusLedAvailable ||
      (statusLedOn == on && (!on || (statusLedRed == red &&
                                    statusLedGreen == green &&
                                    statusLedBlue == blue)))) {
    return;
  }
  statusLedOn = on;
  statusLedRed = on ? red : 0;
  statusLedGreen = on ? green : 0;
  statusLedBlue = on ? blue : 0;
  if (on) {
    writeStatusLedRaw(true, red, green, blue);
  } else {
    writeStatusLedRaw(false);
  }
}

void initializeStatusLed() {
  if (Config::STATUS_LED_PIN < 0) {
    statusLedAvailable = false;
    return;
  }
  if (!Config::STATUS_LED_IS_NEOPIXEL) {
    pinMode(Config::STATUS_LED_PIN, OUTPUT);
  }
  statusLedAvailable = true;
  writeStatusLedRaw(false);
}

bool patternLevel(StatusLedPattern pattern, uint32_t nowMs) {
  const uint32_t phaseMs = nowMs % 2000UL;
  switch (pattern) {
    case StatusLedPattern::Off:
      return false;
    case StatusLedPattern::Solid:
      return true;
    case StatusLedPattern::FastBlink:
      return (phaseMs % 200UL) < 100UL;
    case StatusLedPattern::SlowBlink:
      return phaseMs < 700UL;
    case StatusLedPattern::DoubleBlink:
      return phaseMs < 120UL || (phaseMs >= 260UL && phaseMs < 380UL);
    case StatusLedPattern::Heartbeat:
      return phaseMs < 70UL;
  }
  return false;
}

StatusLedState currentStatusLedState() {
  const bool errorActive =
      !storageReady || !telemetryQueueReady ||
      WiFi.status() != WL_CONNECTED || !webInterface.running() ||
      !distanceSensorReady || !ambientSensorReady || !doughSensorReady ||
      isnan(lastDoughTemperatureC) || !recipeConfigReady ||
      !ntpReadyReported || influxFailureActive;
  if (errorActive) {
    return {StatusLedPattern::FastBlink, 24, 0, 0};
  }
  if (sessionActive) {
    return {StatusLedPattern::SlowBlink, 24, 7, 0};
  }
  return {StatusLedPattern::Heartbeat, 0, 10, 24};
}

void updateStatusLed() {
  if (!statusLedAvailable) {
    return;
  }
  const StatusLedState state = currentStatusLedState();
  setStatusLed(patternLevel(state.pattern, millis()), state.red, state.green,
               state.blue);
}

void showOneShotReadingLed() {
  // Keep the LED green for the duration of the synchronous test acquisition.
  setStatusLed(true, 0, 24, 0);
}

bool mountLittleFsSafely() {
  Preferences preferences;
  const bool preferencesReady = preferences.begin("fermentlab", false);
  const bool previouslyInitialized =
      preferencesReady && preferences.getBool("fs-ready", false);

  bool mounted = LittleFS.begin(false);
  if (!mounted && preferencesReady && !previouslyInitialized) {
    // A factory-new ESP32 has an erased, unformatted data partition. Format
    // only once, before a successful filesystem has ever been recorded in
    // NVS. A later mount failure is treated as recoverable corruption and is
    // never formatted automatically.
    emitEvent("status", "LITTLEFS_FIRST_BOOT_FORMAT");
    mounted = LittleFS.format() && LittleFS.begin(false);
  }
  if (mounted && preferencesReady) {
    preferences.putBool("fs-ready", true);
  }
  if (preferencesReady) preferences.end();
  return mounted;
}

void scanI2cBus() {
  i2cDeviceCount = 0;
  i2cScanErrors = 0;
  i2cBusValid = false;
  i2cDistancePresent = false;
  i2cAmbientPresent = false;
  i2cAddressSummary[0] = '\0';
  i2cSdaLevel = digitalRead(Config::SDA_PIN);
  i2cSclLevel = digitalRead(Config::SCL_PIN);

  // A low idle line indicates a short, missing pull-up or a peripheral holding
  // the bus. Avoid 126 pointless transactions in that condition.
  if (i2cSdaLevel == HIGH && i2cSclLevel == HIGH) {
    for (uint8_t address = 1; address < 127; ++address) {
      Wire.beginTransmission(address);
      const uint8_t result = Wire.endTransmission();
      if (result == 0) {
        ++i2cDeviceCount;
        if (address == Config::VL53L0X_I2C_ADDRESS) {
          i2cDistancePresent = true;
        }
        if (address == Config::SHT3X_DEFAULT_I2C_ADDRESS ||
            address == Config::SHT3X_ALTERNATE_I2C_ADDRESS) {
          i2cAmbientPresent = true;
        }
        const size_t used = strlen(i2cAddressSummary);
        if (used + 8 < sizeof(i2cAddressSummary)) {
          snprintf(i2cAddressSummary + used,
                   sizeof(i2cAddressSummary) - used, "%s0x%02X",
                   used == 0 ? "" : ", ", address);
        }
      } else if (result != 2) {
        ++i2cScanErrors;
      }
      if ((address & 0x0F) == 0) yield();
    }
  }
  i2cSdaLevel = digitalRead(Config::SDA_PIN);
  i2cSclLevel = digitalRead(Config::SCL_PIN);
  i2cBusValid = i2cSdaLevel == HIGH && i2cSclLevel == HIGH &&
                i2cScanErrors == 0 && i2cDeviceCount <= 16;
  if (!i2cBusValid) {
    i2cDeviceCount = 0;
    i2cDistancePresent = false;
    i2cAmbientPresent = false;
    snprintf(i2cAddressSummary, sizeof(i2cAddressSummary),
             "bus bloccato o risposta anomala");
  } else if (i2cAddressSummary[0] == '\0') {
    snprintf(i2cAddressSummary, sizeof(i2cAddressSummary), "nessuno");
  }

  Serial.print(F("{\"schema\":\"fermentlab.event.v1\",\"type\":\"i2c_scan\",\"device_id\":\""));
  Serial.print(deviceId);
  Serial.print(F("\",\"frequency_hz\":"));
  Serial.print(Config::I2C_FREQUENCY_HZ);
  Serial.print(F(",\"sda_gpio\":"));
  Serial.print(Config::SDA_PIN);
  Serial.print(F(",\"sda_level\":"));
  Serial.print(i2cSdaLevel);
  Serial.print(F(",\"scl_gpio\":"));
  Serial.print(Config::SCL_PIN);
  Serial.print(F(",\"scl_level\":"));
  Serial.print(i2cSclLevel);
  Serial.print(F(",\"device_count\":"));
  Serial.print(i2cDeviceCount);
  Serial.print(F(",\"bus_valid\":"));
  Serial.print(i2cBusValid ? F("true") : F("false"));
  Serial.print(F(",\"scan_errors\":"));
  Serial.print(i2cScanErrors);
  Serial.print(F(",\"addresses\":\""));
  Serial.print(i2cAddressSummary);
  Serial.println(F("\"}"));
}

bool i2cDevicePresent(uint8_t address) {
  if (!i2cBusValid) return false;
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}

bool initializeDistanceSensor() {
  if (!i2cDevicePresent(Config::VL53L0X_I2C_ADDRESS)) {
    emitEvent("error", "VL53L0X_NOT_FOUND");
    return false;
  }

  distanceSensor.setTimeout(Config::SENSOR_TIMEOUT_MS);
  if (!distanceSensor.init(true) ||
      !distanceSensor.setSignalRateLimit(Config::SIGNAL_RATE_LIMIT_MCPS) ||
      !distanceSensor.setMeasurementTimingBudget(
          Config::TIMING_BUDGET_MS * 1000UL)) {
    emitEvent("error", "VL53L0X_INIT_FAILED");
    return false;
  }
  distanceSensor.startContinuous();
  emitEvent("status", "VL53L0X_READY");
  return true;
}

uint32_t measurementTimeoutMs() {
  const uint32_t derived =
      Config::TIMING_BUDGET_MS + Config::TIMEOUT_MARGIN_MS;
  return std::max(derived, static_cast<uint32_t>(Config::SENSOR_TIMEOUT_MS));
}

DistanceMeasurement readDistanceMeasurement() {
  DistanceMeasurement measurement;
  const uint32_t startedAt = millis();

  while (true) {
    const uint8_t interruptStatus =
        distanceSensor.readReg(VL53L0X::RESULT_INTERRUPT_STATUS);
    if (distanceSensor.last_status != 0) {
      measurement.invalidReason = DistanceInvalidReason::I2cError;
      return measurement;
    }
    if ((interruptStatus & 0x07) != 0) {
      break;
    }
    if (millis() - startedAt >= measurementTimeoutMs()) {
      measurement.invalidReason = DistanceInvalidReason::Timeout;
      return measurement;
    }
    delay(1);
  }

  const uint8_t rawRangeStatus =
      distanceSensor.readReg(VL53L0X::RESULT_RANGE_STATUS);
  if (distanceSensor.last_status != 0) {
    measurement.invalidReason = DistanceInvalidReason::I2cError;
    return measurement;
  }
  const uint8_t deviceStatus = (rawRangeStatus & 0x78) >> 3;

  measurement.millimeters =
      distanceSensor.readReg16Bit(VL53L0X::RESULT_RANGE_STATUS + 10);
  const bool rangeReadOk = distanceSensor.last_status == 0;
  distanceSensor.writeReg(VL53L0X::SYSTEM_INTERRUPT_CLEAR, 0x01);

  if (!rangeReadOk || distanceSensor.last_status != 0) {
    measurement.invalidReason = DistanceInvalidReason::I2cError;
  } else if (deviceStatus != Config::DEVICE_STATUS_RANGE_COMPLETE) {
    measurement.invalidReason = DistanceInvalidReason::DeviceStatus;
  } else if (measurement.millimeters < Config::MIN_SENSOR_RANGE_MM ||
             measurement.millimeters > Config::MAX_SENSOR_RANGE_MM ||
             measurement.millimeters >= 8190) {
    measurement.invalidReason = DistanceInvalidReason::OutOfRange;
  }
  return measurement;
}

void warmUpDistanceSensor() {
  if (!distanceSensorReady) {
    return;
  }
  for (size_t index = 0; index < Config::WARMUP_READINGS; ++index) {
    (void)readDistanceMeasurement();
    delay(Config::SAMPLE_DELAY_MS);
  }
}

FilteredDistance acquireFilteredDistance() {
  FilteredDistance result;
  if (!distanceSensorReady) {
    return result;
  }

  while (result.validCount < Config::FILTER_SAMPLE_COUNT &&
         result.attempts < Config::MAX_SAMPLE_ATTEMPTS) {
    const DistanceMeasurement measurement = readDistanceMeasurement();
    ++result.attempts;
    if (measurement.valid()) {
      result.values[result.validCount++] = measurement.millimeters;
    }
    if (result.validCount < Config::FILTER_SAMPLE_COUNT) {
      delay(Config::SAMPLE_DELAY_MS);
    }
  }
  if (!result.available()) {
    return result;
  }

  std::sort(result.values, result.values + result.validCount);
  result.minimum = result.values[0];
  result.median = result.values[result.validCount / 2];
  result.maximum = result.values[result.validCount - 1];
  uint32_t sum = 0;
  for (size_t index = 0; index < result.validCount; ++index) {
    sum += result.values[index];
  }
  result.mean =
      static_cast<float>(sum) / static_cast<float>(result.validCount);
  return result;
}

bool sendSht3xCommand(uint16_t command) {
  Wire.beginTransmission(ambientSensorAddress);
  Wire.write(static_cast<uint8_t>(command >> 8));
  Wire.write(static_cast<uint8_t>(command & 0xFF));
  return Wire.endTransmission() == 0;
}

bool initializeAmbientSensor() {
  constexpr uint8_t addresses[] = {
      Config::SHT3X_DEFAULT_I2C_ADDRESS,
      Config::SHT3X_ALTERNATE_I2C_ADDRESS,
  };
  for (const uint8_t address : addresses) {
    if (!i2cDevicePresent(address)) {
      continue;
    }
    ambientSensorAddress = address;
    if (!sendSht3xCommand(0x30A2)) {
      continue;
    }
    delay(2);
    emitEvent("status", "SHT3X_READY");
    return true;
  }
  emitEvent("error", "SHT3X_NOT_FOUND");
  return false;
}

uint8_t sht3xCrc(const uint8_t* data, size_t length) {
  uint8_t crc = 0xFF;
  for (size_t index = 0; index < length; ++index) {
    crc ^= data[index];
    for (uint8_t bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x80) != 0
                ? static_cast<uint8_t>((crc << 1) ^ 0x31)
                : static_cast<uint8_t>(crc << 1);
    }
  }
  return crc;
}

AmbientReading readAmbientMeasurement() {
  AmbientReading reading;
  if (!ambientSensorReady) {
    return reading;
  }
  if (!sendSht3xCommand(0x2400)) {
    reading.status = AmbientStatus::CommandError;
    return reading;
  }
  delay(Config::SHT3X_MEASUREMENT_DELAY_MS);

  constexpr uint8_t byteCount = 6;
  uint8_t data[byteCount] = {};
  const size_t received = Wire.requestFrom(
      ambientSensorAddress, byteCount, static_cast<uint8_t>(true));
  if (received != byteCount) {
    while (Wire.available() > 0) {
      (void)Wire.read();
    }
    reading.status = AmbientStatus::ReadError;
    return reading;
  }
  for (uint8_t index = 0; index < byteCount; ++index) {
    data[index] = static_cast<uint8_t>(Wire.read());
  }
  if (sht3xCrc(data, 2) != data[2] ||
      sht3xCrc(data + 3, 2) != data[5]) {
    reading.status = AmbientStatus::CrcError;
    return reading;
  }

  const uint16_t rawTemperature =
      static_cast<uint16_t>((data[0] << 8) | data[1]);
  const uint16_t rawHumidity =
      static_cast<uint16_t>((data[3] << 8) | data[4]);
  reading.temperatureC =
      -45.0f + 175.0f * static_cast<float>(rawTemperature) / 65535.0f;
  reading.humidityPercent =
      100.0f * static_cast<float>(rawHumidity) / 65535.0f;
  reading.status = AmbientStatus::Ok;
  return reading;
}

const char* ambientStatusText(AmbientStatus status) {
  switch (status) {
    case AmbientStatus::Ok:
      return "OK";
    case AmbientStatus::SensorNotReady:
      return "SHT3X_NOT_READY";
    case AmbientStatus::CommandError:
      return "SHT3X_COMMAND_ERROR";
    case AmbientStatus::ReadError:
      return "SHT3X_READ_ERROR";
    case AmbientStatus::CrcError:
      return "SHT3X_CRC_ERROR";
  }
  return "SHT3X_UNKNOWN_ERROR";
}

void startDoughConversion() {
  if (!doughSensorReady) {
    return;
  }
  doughSensor.requestTemperaturesByAddress(doughSensorAddress);
  doughConversionStartedMs = millis();
  doughConversionPending = true;
}

bool initializeDoughSensor() {
  doughSensor.begin();
  doughSensor.setWaitForConversion(false);
  if (doughSensor.getDeviceCount() == 0 ||
      !doughSensor.getAddress(doughSensorAddress, 0) ||
      !doughSensor.validAddress(doughSensorAddress) ||
      !doughSensor.validFamily(doughSensorAddress)) {
    doughSensorReady = false;
    doughConversionPending = false;
    lastDoughTemperatureC = NAN;
    emitEvent("error", "DS18B20_NOT_FOUND");
    return false;
  }

  doughSensor.setResolution(doughSensorAddress,
                            Config::DS18B20_RESOLUTION_BITS);
  doughSensorReady = true;
  lastDoughTemperatureC = NAN;
  startDoughConversion();
  emitEvent("status", "DS18B20_READY");
  return true;
}

void serviceDoughSensor() {
  if (!doughSensorReady) {
    return;
  }
  if (!doughConversionPending) {
    startDoughConversion();
    return;
  }
  if (millis() - doughConversionStartedMs < Config::DS18B20_CONVERSION_MS) {
    return;
  }

  const float temperatureC = doughSensor.getTempC(doughSensorAddress);
  doughConversionPending = false;
  if (temperatureC == DEVICE_DISCONNECTED_C || isnan(temperatureC) ||
      temperatureC < -55.0f || temperatureC > 125.0f) {
    doughSensorReady = false;
    lastDoughTemperatureC = NAN;
    emitEvent("error", "DS18B20_LOST");
    return;
  }
  lastDoughTemperatureC = temperatureC;
  startDoughConversion();
}

DoughReading currentDoughReading() {
  DoughReading reading;
  if (!doughSensorReady) {
    return reading;
  }
  if (isnan(lastDoughTemperatureC)) {
    reading.status = DoughStatus::ConversionPending;
    return reading;
  }
  reading.temperatureC = lastDoughTemperatureC;
  reading.status = DoughStatus::Ok;
  return reading;
}

const char* doughStatusText(DoughStatus status) {
  switch (status) {
    case DoughStatus::Ok:
      return "OK";
    case DoughStatus::SensorNotReady:
      return "DS18B20_NOT_READY";
    case DoughStatus::ConversionPending:
      return "DS18B20_CONVERSION_PENDING";
    case DoughStatus::ReadError:
      return "DS18B20_READ_ERROR";
  }
  return "DS18B20_UNKNOWN_ERROR";
}

void initializeDeviceId() {
  const uint64_t chipId = ESP.getEfuseMac();
  snprintf(deviceId, sizeof(deviceId), "ESP32-%012llX",
           static_cast<unsigned long long>(chipId & 0xFFFFFFFFFFFFULL));
}

bool wifiCredentialAvailable(size_t index) {
  if (index >= WIFI_CREDENTIAL_COUNT) return false;
  const char* ssid = WIFI_CREDENTIALS[index].ssid;
  return ssid != nullptr && std::strlen(ssid) > 0 &&
         std::strncmp(ssid, "YOUR_", 5) != 0;
}

bool wifiCredentialsAvailable() {
  for (size_t index = 0; index < WIFI_CREDENTIAL_COUNT; ++index) {
    if (wifiCredentialAvailable(index)) return true;
  }
  return false;
}

bool selectNextWifiCredential() {
  const size_t previous = wifiCredentialIndex;
  for (size_t offset = 1; offset <= WIFI_CREDENTIAL_COUNT; ++offset) {
    const size_t candidate =
        (previous + offset) % WIFI_CREDENTIAL_COUNT;
    if (wifiCredentialAvailable(candidate)) {
      wifiCredentialIndex = candidate;
      return candidate <= previous;
    }
  }
  return true;
}

void selectFirstAvailableWifiCredential() {
  if (wifiCredentialAvailable(wifiCredentialIndex)) return;
  for (size_t index = 0; index < WIFI_CREDENTIAL_COUNT; ++index) {
    if (wifiCredentialAvailable(index)) {
      wifiCredentialIndex = index;
      return;
    }
  }
}

void serviceConnectivity() {
  if (!wifiCredentialsAvailable()) {
    webInterface.stop();
    if (!wifiCredentialsWarningEmitted) {
      emitEvent("error", "WIFI_CREDENTIALS_MISSING");
      wifiCredentialsWarningEmitted = true;
    }
    return;
  }

  const uint32_t now = millis();
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifiWasConnected) {
      emitEvent("status", "WIFI_CONNECTED");
      wifiWasConnected = true;
      wifiAttemptInProgress = false;
      wifiRetryDelayMs = Config::WIFI_RETRY_INITIAL_MS;
      ntpConfigured = false;
    }
    if (!webInterface.running()) {
      const bool webReady = webInterface.begin();
      if (webReady) {
        emitEvent("status", "WEB_INTERFACE_READY");
        if (!webInterface.mdnsReady()) {
          emitEvent("error", "MDNS_START_FAILED");
        }
        Serial.print(F("{\"schema\":\"fermentlab.event.v1\",\"type\":\"web_ready\",\"device_id\":\""));
        Serial.print(deviceId);
        Serial.print(F("\",\"url\":\"http://"));
        Serial.print(WiFi.localIP());
        Serial.print(F("\",\"mdns_url\":\"http://"));
        Serial.print(Config::WEB_HOSTNAME);
        Serial.println(F(".local\"}"));
      }
    }
    if (!ntpConfigured) {
      configTzTime(Config::TIMEZONE, Config::NTP_SERVER_1,
                   Config::NTP_SERVER_2);
      emitEvent("status", "NTP_SYNCHRONIZING");
      ntpConfigured = true;
    }
    if (!ntpReadyReported && time(nullptr) >= Config::MIN_VALID_EPOCH) {
      emitEvent("status", "NTP_SYNCHRONIZED");
      ntpReadyReported = true;
    }
    return;
  }

  if (wifiWasConnected) {
    emitEvent("error", "WIFI_DISCONNECTED");
    wifiWasConnected = false;
    wifiAttemptInProgress = false;
    nextWifiAttemptMs = now;
  }
  webInterface.stop();

  if (wifiAttemptInProgress) {
    if (now - wifiAttemptStartedMs < Config::WIFI_TIMEOUT_MS) {
      return;
    }
    emitEvent("error", "WIFI_TIMEOUT");
    WiFi.disconnect();
    wifiAttemptInProgress = false;
    const bool completedCycle = selectNextWifiCredential();
    nextWifiAttemptMs = completedCycle ? now + wifiRetryDelayMs : now;
    if (completedCycle) {
      wifiRetryDelayMs = std::min(wifiRetryDelayMs * 2,
                                  Config::WIFI_RETRY_MAX_MS);
    }
    return;
  }

  if (static_cast<int32_t>(now - nextWifiAttemptMs) < 0) {
    return;
  }
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(Config::WEB_HOSTNAME);
  selectFirstAvailableWifiCredential();
  WiFi.begin(WIFI_CREDENTIALS[wifiCredentialIndex].ssid,
             WIFI_CREDENTIALS[wifiCredentialIndex].password);
  wifiAttemptInProgress = true;
  wifiAttemptStartedMs = now;
  emitEvent("status", "WIFI_CONNECTING");
}

bool formatLocalTime(time_t timestamp, char* iso, size_t isoSize,
                     char* dateCompact = nullptr,
                     size_t dateCompactSize = 0,
                     char* timeCompact = nullptr,
                     size_t timeCompactSize = 0) {
  struct tm localTime = {};
  if (localtime_r(&timestamp, &localTime) == nullptr) {
    return false;
  }

  char dateTime[24] = {};
  char offset[8] = {};
  if (strftime(dateTime, sizeof(dateTime), "%Y-%m-%dT%H:%M:%S",
               &localTime) == 0 ||
      strftime(offset, sizeof(offset), "%z", &localTime) == 0 ||
      std::strlen(offset) != 5) {
    return false;
  }
  snprintf(iso, isoSize, "%s%c%c%c:%c%c", dateTime, offset[0], offset[1],
           offset[2], offset[3], offset[4]);

  if (dateCompact != nullptr && dateCompactSize > 0) {
    strftime(dateCompact, dateCompactSize, "%Y%m%d", &localTime);
  }
  if (timeCompact != nullptr && timeCompactSize > 0) {
    strftime(timeCompact, timeCompactSize, "%H%M%S", &localTime);
  }
  return true;
}

void serviceSensorRecovery() {
  const uint32_t now = millis();
  if (now - lastSensorRetryMs < Config::SENSOR_RETRY_INTERVAL_MS) {
    return;
  }
  lastSensorRetryMs = now;
  scanI2cBus();

  if (distanceSensorReady && !i2cDistancePresent) {
    distanceSensorReady = false;
    emitEvent("error", "VL53L0X_LOST");
  }
  if (ambientSensorReady && !i2cAmbientPresent) {
    ambientSensorReady = false;
    emitEvent("error", "SHT3X_LOST");
  }

  if (!distanceSensorReady && i2cBusValid) {
    distanceSensorReady = initializeDistanceSensor();
    if (distanceSensorReady) {
      warmUpDistanceSensor();
      emitEvent("status", "VL53L0X_RECOVERED");
    }
  }
  if (!ambientSensorReady && i2cBusValid) {
    ambientSensorReady = initializeAmbientSensor();
    if (ambientSensorReady) {
      emitEvent("status", "SHT3X_RECOVERED");
    }
  }
  if (!doughSensorReady && initializeDoughSensor()) {
    emitEvent("status", "DS18B20_RECOVERED");
  }
}

float calibratedExternalDistanceMm(float rawMedianMm) {
  if (!std::isfinite(rawMedianMm) ||
      Config::DISTANCE_CALIBRATION_COUNT < 2 ||
      rawMedianMm < Config::DISTANCE_CALIBRATION[0].rawMedianMm ||
      rawMedianMm > Config::DISTANCE_CALIBRATION[
                        Config::DISTANCE_CALIBRATION_COUNT - 1]
                        .rawMedianMm) {
    return NAN;
  }

  for (size_t index = 1; index < Config::DISTANCE_CALIBRATION_COUNT;
       ++index) {
    const auto& lower = Config::DISTANCE_CALIBRATION[index - 1];
    const auto& upper = Config::DISTANCE_CALIBRATION[index];
    if (rawMedianMm <= upper.rawMedianMm) {
      const float fraction =
          (rawMedianMm - lower.rawMedianMm) /
          (upper.rawMedianMm - lower.rawMedianMm);
      return lower.externalDistanceMm +
             fraction * (upper.externalDistanceMm -
                         lower.externalDistanceMm);
    }
  }
  return NAN;
}

void writeSessionStart(Print& output, time_t timestamp,
                       const char* isoTimestamp) {
  output.print(F("{\"schema\":\"fermentlab.session.v1\",\"type\":\"session_start\",\"device_id\":\""));
  output.print(deviceId);
  output.print(F("\",\"session_id\":\""));
  output.print(sessionId);
  output.print(F("\",\"timestamp\":\""));
  output.print(isoTimestamp);
  output.print(F("\",\"epoch_s\":"));
  output.print(static_cast<unsigned long>(timestamp));
  output.print(F(",\"timezone\":\"Europe/Rome\",\"interval_s\":"));
  output.print(sessionReadingIntervalSeconds);
  output.print(F(",\"recipe_name\":"));
  printJsonString(output, sessionConfigStore.draftName());
  output.print(F(",\"recipe_flours\":"));
  printJsonString(output, sessionConfigStore.draftFlourSummary());
  output.print(F(",\"recipe_hydration_pct\":"));
  printJsonFloat(output, sessionConfigStore.draftHydrationPercent(), 1);
  output.println(F("}"));
}

String buildSessionStartLineProtocol(time_t timestamp, const char* isoTimestamp) {
  const String draftName = sessionConfigStore.draftName();
  const String draftFlours = sessionConfigStore.draftFlourSummary();
  const float hydration = sessionConfigStore.draftHydrationPercent();

  String line;
  line.reserve(320);
  line += F("session_start,device_id=");
  appendInfluxEscapedTag(line, deviceId);
  line += F(",session_id=");
  appendInfluxEscapedTag(line, sessionId);

  bool hasField = false;
  appendInfluxStringField(line, "schema", String("fermentlab.session.v1"),
                         hasField);
  appendInfluxStringField(line, "type", String("session_start"), hasField);
  appendInfluxStringField(line, "timestamp", String(isoTimestamp), hasField);
  appendInfluxIntegerField(line, "epoch_s", static_cast<uint32_t>(timestamp),
                           hasField);
  appendInfluxStringField(line, "timezone", String("Europe/Rome"), hasField);
  appendInfluxIntegerField(line, "interval_s", sessionReadingIntervalSeconds,
                           hasField);
  appendInfluxStringField(line, "name", draftName, hasField);
  appendInfluxStringField(line, "flours_summary", draftFlours, hasField);
  appendInfluxFloatField(line, "hydration_pct", hydration, hasField);
  return line;
}

void emitSessionStartToInflux(time_t timestamp, const char* isoTimestamp) {
  if (!telemetryQueueReady) {
    emitEvent("error", "SESSION_START_QUEUE_NOT_READY");
    return;
  }
  if (!telemetryQueue.enqueue(buildSessionStartLineProtocol(timestamp,
                                                           isoTimestamp))) {
    emitEvent("error", "SESSION_START_QUEUE_WRITE_FAILED");
  }
}

void emitSessionStart(time_t timestamp, const char* isoTimestamp) {
  writeSessionStart(Serial, timestamp, isoTimestamp);
  // Keep START metadata out of filesystem-backed writes. The session_start
  // queue write can trigger immediate resets on some boards right after START.
  (void)timestamp;
  (void)isoTimestamp;
}

void emitMeasurement() {
  setCrashBreadcrumb(BREADCRUMB_MEASURE_BEGIN);
  const time_t timestamp = time(nullptr);
  char isoTimestamp[40] = {};
  if (timestamp < Config::MIN_VALID_EPOCH ||
      !formatLocalTime(timestamp, isoTimestamp, sizeof(isoTimestamp))) {
    emitEvent("error", "INVALID_TIMESTAMP");
    return;
  }

  const DoughReading dough = currentDoughReading();
  const AmbientReading ambient = readAmbientMeasurement();
  const FilteredDistance distance = acquireFilteredDistance();
  setCrashBreadcrumb(BREADCRUMB_MEASURE_SENSORS);

  float correctedDistanceMm = NAN;
  float growthMm = NAN;
  float doughHeightMm = NAN;
  float volumeMl = NAN;
  const char* distanceStatus = "INSUFFICIENT_READINGS";
  if (!distanceSensorReady) {
    distanceStatus = "VL53L0X_NOT_READY";
  } else if (distance.available()) {
    correctedDistanceMm =
        calibratedExternalDistanceMm(static_cast<float>(distance.median));
    if (!std::isfinite(correctedDistanceMm) ||
        correctedDistanceMm < Config::CALIBRATED_MIN_MM ||
        correctedDistanceMm > Config::CALIBRATED_MAX_MM) {
      correctedDistanceMm = NAN;
      distanceStatus = "OUTSIDE_CALIBRATED_RANGE";
    } else {
      if (!baselineAvailable) {
        baselineDistanceMm = correctedDistanceMm;
        baselineAvailable = true;
        distanceStatus = "BASELINE_INITIALIZED";
      } else {
        distanceStatus = "OK";
      }
      growthMm = baselineDistanceMm - correctedDistanceMm;
      if (Config::SENSOR_TO_CONTAINER_BOTTOM_MM > 0.0f) {
        doughHeightMm =
            Config::SENSOR_TO_CONTAINER_BOTTOM_MM - correctedDistanceMm;
      }
      if (!isnan(doughHeightMm) && doughHeightMm >= 0.0f &&
          Config::CONTAINER_CROSS_SECTION_CM2 > 0.0f) {
        volumeMl =
            Config::CONTAINER_CROSS_SECTION_CM2 * doughHeightMm / 10.0f;
      }
    }
  }

  const uint32_t currentSequence = sequenceNumber++;
  const uint32_t elapsedMs = millis() - sessionStartMs;
  const auto writeMeasurement = [&](Print& output) {
    output.print(F("{\"schema\":\"fermentlab.measurement.v1\",\"type\":\"measurement\",\"device_id\":\""));
    output.print(deviceId);
    output.print(F("\",\"session_id\":\""));
    output.print(sessionId);
    output.print(F("\",\"sequence\":"));
    output.print(currentSequence);
    output.print(F(",\"timestamp\":\""));
    output.print(isoTimestamp);
    output.print(F("\",\"epoch_s\":"));
    output.print(static_cast<unsigned long>(timestamp));
    output.print(F(",\"elapsed_ms\":"));
    output.print(elapsedMs);
    output.print(F(",\"ambient_temperature_c\":"));
    printJsonFloat(output, ambient.temperatureC);
    output.print(F(",\"dough_temperature_c\":"));
    printJsonFloat(output, dough.temperatureC);
    output.print(F(",\"dough_status\":\""));
    output.print(doughStatusText(dough.status));
    output.print(F("\""));
    output.print(F(",\"ambient_humidity_pct\":"));
    printJsonFloat(output, ambient.humidityPercent);
    output.print(F(",\"ambient_status\":\""));
    output.print(ambientStatusText(ambient.status));
    output.print(F("\",\"distance_samples_valid\":"));
    output.print(distance.validCount);
    output.print(F(",\"distance_attempts\":"));
    output.print(distance.attempts);
    output.print(F(",\"distance_raw_min_mm\":"));
    if (distance.available()) output.print(distance.minimum); else output.print(F("null"));
    output.print(F(",\"distance_raw_mean_mm\":"));
    printJsonFloat(output, distance.mean);
    output.print(F(",\"distance_raw_median_mm\":"));
    if (distance.available()) output.print(distance.median); else output.print(F("null"));
    output.print(F(",\"distance_raw_max_mm\":"));
    if (distance.available()) output.print(distance.maximum); else output.print(F("null"));
    output.print(F(",\"distance_corrected_mm\":"));
    printJsonFloat(output, correctedDistanceMm);
    output.print(F(",\"growth_mm\":"));
    printJsonFloat(output, growthMm);
    output.print(F(",\"dough_height_mm\":"));
    printJsonFloat(output, doughHeightMm);
    output.print(F(",\"volume_ml\":"));
    printJsonFloat(output, volumeMl);
    output.print(F(",\"distance_status\":\""));
    output.print(distanceStatus);
    output.println(F("\"}"));
  };

  writeMeasurement(Serial);
  setCrashBreadcrumb(BREADCRUMB_MEASURE_SERIAL);
  if (sessionFileEnabled && sessionFile) {
    writeMeasurement(sessionFile);
    setCrashBreadcrumb(BREADCRUMB_MEASURE_FILE);

    if (!panicSafeMode && millis() >= nextSessionFlushMs) {
      sessionFile.flush();
      nextSessionFlushMs = millis() + 5000UL;
    }
  }

  TelemetryRecord record;
  record.deviceId = deviceId;
  record.sessionId = sessionId;
  record.sequence = currentSequence;
  record.timestamp = timestamp;
  record.elapsedMs = elapsedMs;
  record.doughTemperatureC = dough.temperatureC;
  record.ambientTemperatureC = ambient.temperatureC;
  record.humidityPercent = ambient.humidityPercent;
  record.distanceMm = correctedDistanceMm;
  record.doughHeightMm = doughHeightMm;
  record.volumeMl = volumeMl;
  setCrashBreadcrumb(BREADCRUMB_MEASURE_QUEUE);
  if (panicSafeMode) {
    if (!panicQueueSkipReported) {
      emitEvent("warning", "PANIC_SAFE_MODE_QUEUE_DISABLED");
      panicQueueSkipReported = true;
    }
  } else if (!telemetryQueueReady ||
             !telemetryQueue.enqueue(toInfluxLineProtocol(record))) {
    emitEvent("error", "TELEMETRY_QUEUE_WRITE_FAILED");
  }
  lastMeasurementTimestamp = timestamp;
  setCrashBreadcrumb(BREADCRUMB_MEASURE_DONE);
}

void dumpSavedFile(const char* path, const char* filename) {
  File savedFile = LittleFS.open(path, FILE_READ);
  if (!savedFile) {
    emitEvent("error", "FILE_DUMP_OPEN_FAILED");
    return;
  }
  Serial.print(F("{\"schema\":\"fermentlab.event.v1\",\"type\":\"file_dump_start\",\"device_id\":\""));
  Serial.print(deviceId);
  Serial.print(F("\",\"filename\":\""));
  Serial.print(filename);
  Serial.println(F("\"}"));
  while (savedFile.available()) {
    String line = savedFile.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      Serial.println(line);
    }
  }
  savedFile.close();
  Serial.print(F("{\"schema\":\"fermentlab.event.v1\",\"type\":\"file_dump_end\",\"device_id\":\""));
  Serial.print(deviceId);
  Serial.print(F("\",\"filename\":\""));
  Serial.print(filename);
  Serial.println(F("\"}"));
}

void startSession() {
  setCrashBreadcrumb(BREADCRUMB_START_BEGIN);
  if (sessionActive) {
    return;
  }
  if (!storageReady) {
    emitEvent("error", "SESSION_REJECTED_STORAGE_NOT_READY");
    return;
  }
  if (!distanceSensorReady || !ambientSensorReady) {
    emitEvent("error", "SESSION_REJECTED_SENSOR_NOT_READY");
    return;
  }

  if (panicSafeMode) {
    const time_t startTimestamp = time(nullptr);
    if (startTimestamp < Config::MIN_VALID_EPOCH ||
        startTimestamp < 0) {
      emitEvent("error", "SESSION_REJECTED_TIME_UNAVAILABLE");
      return;
    }
    const unsigned long epochValue = static_cast<unsigned long>(startTimestamp);
    snprintf(sessionStartDate, sizeof(sessionStartDate), "%08lu",
         epochValue % 100000000UL);
    snprintf(sessionStartTime, sizeof(sessionStartTime), "%06lu",
         epochValue % 1000000UL);
    snprintf(sessionId, sizeof(sessionId), "panic-%08lu-%s",
         epochValue % 100000000UL, deviceId);
    sessionReadingIntervalSeconds = Config::DEFAULT_READING_INTERVAL_S;
    sequenceNumber = 0;
    nextSessionFlushMs = millis() + 5000UL;
    sessionStartMs = millis();
    sessionActive = true;
    setCrashBreadcrumb(BREADCRUMB_START_ACTIVE);
    emitEvent("warning", "PANIC_SAFE_MODE_MINIMAL_START");
    lastReadingMs = millis();
    sessionFileEnabled = false;
    activeFilePath[0] = '\0';
    if (!panicSessionFileSkipReported) {
      emitEvent("warning", "PANIC_SAFE_MODE_SESSION_FILE_DISABLED");
      panicSessionFileSkipReported = true;
    }
    baselineAvailable = false;
    baselineDistanceMm = NAN;
    return;
  }

  String recipeError;
  if (!recipeConfigReady || !sessionConfigStore.draftValid(&recipeError)) {
    emitEvent("error", "SESSION_REJECTED_RECIPE_NOT_READY");
    return;
  }
  if (time(nullptr) < Config::MIN_VALID_EPOCH) {
    emitEvent("error", "SESSION_REJECTED_TIME_UNAVAILABLE");
    return;
  }

  const time_t startTimestamp = time(nullptr);
  char isoTimestamp[40] = {};
  if (!formatLocalTime(startTimestamp, isoTimestamp, sizeof(isoTimestamp),
                       sessionStartDate, sizeof(sessionStartDate),
                       sessionStartTime, sizeof(sessionStartTime))) {
    emitEvent("error", "SESSION_REJECTED_TIME_FORMAT");
    return;
  }

  snprintf(sessionId, sizeof(sessionId), "%s-%s-%s", sessionStartDate,
           sessionStartTime, deviceId);
  if (panicSafeMode) {
    sessionFileEnabled = false;
    activeFilePath[0] = '\0';
    if (!panicSessionFileSkipReported) {
      emitEvent("warning", "PANIC_SAFE_MODE_SESSION_FILE_DISABLED");
      panicSessionFileSkipReported = true;
    }
  } else {
    sessionFileEnabled = true;
    snprintf(activeFilePath, sizeof(activeFilePath), "/%s.partial.jsonl",
             sessionId);
    setCrashBreadcrumb(BREADCRUMB_START_FILE_OPEN);
    sessionFile = LittleFS.open(activeFilePath, FILE_WRITE);
    if (!sessionFile) {
      emitEvent("error", "SESSION_FILE_OPEN_FAILED");
      return;
    }
  }
  baselineAvailable = false;
  baselineDistanceMm = NAN;
  sessionReadingIntervalSeconds =
      sessionConfigStore.draftReadingIntervalSeconds();
  sequenceNumber = 0;
  nextSessionFlushMs = millis() + 5000UL;
  sessionStartMs = millis();
  sessionActive = true;
  setCrashBreadcrumb(BREADCRUMB_START_ACTIVE);
  emitSessionStart(startTimestamp, isoTimestamp);
  // Start with a clean interval window. Triggering a measurement immediately
  // after START was causing a panic on some boards during filesystem writes.
  lastReadingMs = millis();
}

void stopSession() {
  if (!sessionActive) {
    return;
  }
  const time_t endTimestamp = time(nullptr);
  char isoTimestamp[40] = {};
  char endTime[7] = {};
  if (!formatLocalTime(endTimestamp, isoTimestamp, sizeof(isoTimestamp),
                       nullptr, 0, endTime, sizeof(endTime))) {
    emitEvent("error", "SESSION_END_TIME_FORMAT_ERROR");
    return;
  }

  sessionActive = false;
  char filename[128] = {};
  char finalPath[132] = {};
  snprintf(filename, sizeof(filename), "%s_%s_%s_%s.jsonl",
           sessionStartDate, sessionStartTime, endTime, deviceId);
  snprintf(finalPath, sizeof(finalPath), "/%s", filename);

  const auto writeSessionEnd = [&](Print& output) {
    output.print(F("{\"schema\":\"fermentlab.session.v1\",\"type\":\"session_end\",\"device_id\":\""));
    output.print(deviceId);
    output.print(F("\",\"session_id\":\""));
    output.print(sessionId);
    output.print(F("\",\"timestamp\":\""));
    output.print(isoTimestamp);
    output.print(F("\",\"epoch_s\":"));
    output.print(static_cast<unsigned long>(endTimestamp));
    output.print(F(",\"measurements\":"));
    output.print(sequenceNumber);
    output.print(F(",\"suggested_filename\":\""));
    output.print(filename);
    output.println(F("\"}"));
  };
  writeSessionEnd(Serial);
  size_t savedBytes = 0;
  if (sessionFileEnabled && sessionFile) {
    writeSessionEnd(sessionFile);
    sessionFile.flush();
    savedBytes = sessionFile.size();
    sessionFile.close();
    Serial.flush();

    if (!LittleFS.rename(activeFilePath, finalPath)) {
      emitEvent("error", "SESSION_FILE_RENAME_FAILED");
    } else {
      Serial.print(F("{\"schema\":\"fermentlab.event.v1\",\"type\":\"file_saved\",\"device_id\":\""));
      Serial.print(deviceId);
      Serial.print(F("\",\"filename\":\""));
      Serial.print(filename);
      Serial.print(F("\",\"bytes\":"));
      Serial.print(savedBytes);
      Serial.println(F("}"));
      dumpSavedFile(finalPath, filename);
    }
  } else {
    emitEvent("warning", "PANIC_SAFE_MODE_SESSION_FILE_SKIPPED");
  }
}

void toggleSession() {
  if (sessionActive) {
    stopSession();
  } else {
    startSession();
  }
}

String jsonFloatValue(float value, uint8_t decimals = 3) {
  return isnan(value) || isinf(value) ? String("null")
                                      : String(value,
                                               static_cast<unsigned int>(decimals));
}

void appendJsonString(String& output, const String& value) {
  output += '"';
  for (size_t index = 0; index < value.length(); ++index) {
    const char c = value[index];
    if (c == '"' || c == '\\') output += '\\';
    if (c == '\n' || c == '\r') {
      output += ' ';
    } else {
      output += c;
    }
  }
  output += '"';
}

String webStatusJson() {
  const time_t timestamp = time(nullptr);
  char isoTimestamp[40] = {};
  const bool timeValid =
      timestamp >= Config::MIN_VALID_EPOCH &&
      formatLocalTime(timestamp, isoTimestamp, sizeof(isoTimestamp));

  if (panicSafeMode) {
    String json;
    json.reserve(448);
    json += F("{\"device_id\":\"");
    json += deviceId;
    json += F("\",\"board_profile\":\"");
    json += Config::BOARD_PROFILE;
    json += F("\",\"reset_reason\":\"");
    json += resetReasonText(bootResetReason);
    json += F("\",\"panic_safe_mode\":true");
    json += F(",\"measurement_enabled\":false");
    json += F(",\"session_file_enabled\":");
    json += sessionFileEnabled ? F("true") : F("false");
    json += F(",\"session_active\":");
    json += sessionActive ? F("true") : F("false");
    json += F(",\"session_id\":");
    if (sessionActive) {
      appendJsonString(json, String(sessionId));
    } else {
      json += F("null");
    }
    json += F(",\"time_valid\":");
    json += timeValid ? F("true") : F("false");
    json += F(",\"timestamp\":");
    if (timeValid) {
      appendJsonString(json, String(isoTimestamp));
    } else {
      json += F("null");
    }
    json += F(",\"storage_ready\":");
    json += storageReady ? F("true") : F("false");
    json += F(",\"telemetry_queue_ready\":");
    json += telemetryQueueReady ? F("true") : F("false");
    json += F(",\"distance_sensor_ready\":");
    json += distanceSensorReady ? F("true") : F("false");
    json += F(",\"ambient_sensor_ready\":");
    json += ambientSensorReady ? F("true") : F("false");
    json += F(",\"dough_sensor_ready\":");
    json += doughSensorReady ? F("true") : F("false");
    json += F(",\"ip\":\"");
    json += WiFi.localIP().toString();
    json += F("\",\"uptime_s\":");
    json += String(millis() / 1000UL);
    json += F(",\"free_heap_bytes\":");
    json += String(ESP.getFreeHeap());
    json += F("}");
    return json;
  }

  char lastMeasurementIso[40] = {};
  const bool lastMeasurementAvailable =
      lastMeasurementTimestamp >= Config::MIN_VALID_EPOCH &&
      formatLocalTime(lastMeasurementTimestamp, lastMeasurementIso,
                      sizeof(lastMeasurementIso));
  uint32_t nextReadingSeconds = 0;
  const uint32_t displayedReadingIntervalSeconds =
      sessionActive ? sessionReadingIntervalSeconds
                    : sessionConfigStore.draftReadingIntervalSeconds();
  const uint32_t sessionReadingIntervalMs =
      sessionReadingIntervalSeconds * 1000UL;
  if (sessionActive) {
    const uint32_t elapsedSinceReading = millis() - lastReadingMs;
    const uint32_t remainingMs =
        elapsedSinceReading >= sessionReadingIntervalMs
            ? 0
            : sessionReadingIntervalMs - elapsedSinceReading;
    nextReadingSeconds = (remainingMs + 999UL) / 1000UL;
  }

  String json;
  json.reserve(1152);
  json += F("{\"device_id\":\"");
  json += deviceId;
  json += F("\",\"board_profile\":\"");
  json += Config::BOARD_PROFILE;
  json += F("\",\"reset_reason\":\"");
  json += resetReasonText(bootResetReason);
  json += F("\",\"panic_safe_mode\":");
  json += panicSafeMode ? F("true") : F("false");
  json += F(",\"measurement_enabled\":");
  json += panicSafeMode ? F("false") : F("true");
  json += F(",\"crash_breadcrumb\":");
  json += String(crashBreadcrumb);
  json += F(",\"crash_breadcrumb_text\":\"");
  json += crashBreadcrumbText(crashBreadcrumb);
  json += F("\",\"boot_crash_breadcrumb\":");
  json += String(bootCrashBreadcrumb);
  json += F(",\"boot_crash_breadcrumb_text\":\"");
  json += crashBreadcrumbText(bootCrashBreadcrumb);
  json += F("\",\"last_panic_breadcrumb\":");
  json += String(lastPanicBreadcrumb);
  json += F(",\"last_panic_breadcrumb_text\":\"");
  json += crashBreadcrumbText(lastPanicBreadcrumb);
  json += F("\",\"free_heap_bytes\":");
  json += String(ESP.getFreeHeap());
  json += F(",\"session_active\":");
  json += sessionActive ? F("true") : F("false");
  json += F(",\"session_id\":");
  if (sessionActive) {
    json += '"';
    json += sessionId;
    json += '"';
  } else {
    json += F("null");
  }
  json += F(",\"timestamp\":");
  if (timeValid) {
    json += '"';
    json += isoTimestamp;
    json += '"';
  } else {
    json += F("null");
  }
  json += F(",\"time_valid\":");
  json += timeValid ? F("true") : F("false");
  json += F(",\"storage_ready\":");
  json += storageReady ? F("true") : F("false");
  json += F(",\"telemetry_queue_ready\":");
  json += telemetryQueueReady ? F("true") : F("false");
  json += F(",\"session_file_enabled\":");
  json += sessionFileEnabled ? F("true") : F("false");
  json += F(",\"distance_sensor_ready\":");
  json += distanceSensorReady ? F("true") : F("false");
  json += F(",\"ambient_sensor_ready\":");
  json += ambientSensorReady ? F("true") : F("false");
  const DoughReading dough = currentDoughReading();
  json += F(",\"dough_sensor_ready\":");
  json += doughSensorReady ? F("true") : F("false");
  json += F(",\"dough_sensor_gpio\":");
  json += String(Config::DS18B20_PIN);
  json += F(",\"dough_temperature_c\":");
  json += jsonFloatValue(dough.temperatureC);
  json += F(",\"dough_status\":\"");
  json += doughStatusText(dough.status);
  json += '"';
  json += F(",\"i2c_frequency_hz\":");
  json += String(Config::I2C_FREQUENCY_HZ);
  json += F(",\"i2c_sda_level\":");
  json += String(i2cSdaLevel);
  json += F(",\"i2c_scl_level\":");
  json += String(i2cSclLevel);
  json += F(",\"i2c_device_count\":");
  json += String(i2cDeviceCount);
  json += F(",\"i2c_bus_valid\":");
  json += i2cBusValid ? F("true") : F("false");
  json += F(",\"i2c_scan_errors\":");
  json += String(i2cScanErrors);
  json += F(",\"i2c_addresses\":\"");
  json += i2cAddressSummary;
  json += '"';
  json += F(",\"recipe_config_ready\":");
  json += recipeConfigReady ? F("true") : F("false");
  json += F(",\"start_blocker\":");
  if (sessionActive) {
    json += F("null");
  } else if (!storageReady) {
    json += F("\"Memoria LittleFS non disponibile.\"");
  } else if (!distanceSensorReady) {
    json += F("\"Sensore VL53L0X non disponibile; nuovo tentativo automatico entro 15 secondi.\"");
  } else if (!ambientSensorReady) {
    json += F("\"Sensore SHT3x non disponibile; nuovo tentativo automatico entro 15 secondi.\"");
  } else if (!doughSensorReady) {
    json += F("\"Sensore DS18B20 su GPIO27 non disponibile; nuovo tentativo automatico entro 15 secondi.\"");
  } else if (isnan(lastDoughTemperatureC)) {
    json += F("\"Prima lettura DS18B20 ancora in corso.\"");
  } else if (!recipeConfigReady) {
    json += F("\"Configurazione impasto non disponibile in LittleFS.\"");
  } else {
    String recipeError;
    if (!sessionConfigStore.draftValid(&recipeError)) {
      appendJsonString(json, String("Prossimo impasto non valido: ") + recipeError);
    } else if (!timeValid) {
      json += F("\"Orologio non sincronizzato; attendere NTP.\"");
    } else {
      json += F("null");
    }
  }
  json += F(",\"ip\":\"");
  json += WiFi.localIP().toString();
  json += F("\",\"rssi_dbm\":");
  json += String(WiFi.RSSI());
  json += F(",\"uptime_s\":");
  json += String(millis() / 1000UL);
  json += F(",\"reading_interval_s\":");
  json += String(displayedReadingIntervalSeconds);
  json += F(",\"session_measurements\":");
  json += String(sequenceNumber);
  json += F(",\"next_reading_in_s\":");
  json += sessionActive ? String(nextReadingSeconds) : String("null");
  json += F(",\"last_measurement_at\":");
  if (lastMeasurementAvailable) {
    json += '"';
    json += lastMeasurementIso;
    json += '"';
  } else {
    json += F("null");
  }
  json += F(",\"queue_records\":");
  json += String(telemetryQueueReady ? telemetryQueue.pendingRecords() : 0);
  json += F(",\"queue_segments\":");
  json += String(telemetryQueueReady ? telemetryQueue.segmentCount() : 0);
  json += F(",\"queue_bytes\":");
  json += String(telemetryQueueReady ? telemetryQueue.pendingBytes() : 0);
  json += F(",\"draft_name\":");
  if (recipeConfigReady) {
    appendJsonString(json, sessionConfigStore.draftName());
  } else {
    json += F("null");
  }
  json += F(",\"draft_flours\":");
  if (recipeConfigReady) {
    appendJsonString(json, sessionConfigStore.draftFlourSummary());
  } else {
    json += F("null");
  }
  json += F(",\"draft_hydration_pct\":");
  json += recipeConfigReady
              ? jsonFloatValue(sessionConfigStore.draftHydrationPercent(), 1)
              : String("null");
  json += '}';
  return json;
}

String webTestJson() {
  showOneShotReadingLed();
  const time_t timestamp = time(nullptr);
  char isoTimestamp[40] = {};
  const bool timeValid =
      timestamp >= Config::MIN_VALID_EPOCH &&
      formatLocalTime(timestamp, isoTimestamp, sizeof(isoTimestamp));
  const DoughReading dough = currentDoughReading();
  const AmbientReading ambient = readAmbientMeasurement();
  const FilteredDistance distance = acquireFilteredDistance();

  float correctedDistanceMm = NAN;
  float doughHeightMm = NAN;
  const char* distanceStatus = "INSUFFICIENT_READINGS";
  if (!distanceSensorReady) {
    distanceStatus = "VL53L0X_NOT_READY";
  } else if (distance.available()) {
    correctedDistanceMm =
        calibratedExternalDistanceMm(static_cast<float>(distance.median));
    if (!std::isfinite(correctedDistanceMm) ||
        correctedDistanceMm < Config::CALIBRATED_MIN_MM ||
        correctedDistanceMm > Config::CALIBRATED_MAX_MM) {
      correctedDistanceMm = NAN;
      distanceStatus = "OUTSIDE_CALIBRATED_RANGE";
    } else {
      distanceStatus = "OK";
      doughHeightMm =
          Config::SENSOR_TO_CONTAINER_BOTTOM_MM - correctedDistanceMm;
    }
  }

  String json;
  json.reserve(416);
  json += F("{\"timestamp\":");
  if (timeValid) {
    json += '"';
    json += isoTimestamp;
    json += '"';
  } else {
    json += F("null");
  }
  json += F(",\"dough_temperature_c\":");
  json += jsonFloatValue(dough.temperatureC);
  json += F(",\"dough_status\":\"");
  json += doughStatusText(dough.status);
  json += '"';
  json += F(",\"ambient_temperature_c\":");
  json += jsonFloatValue(ambient.temperatureC);
  json += F(",\"humidity_pct\":");
  json += jsonFloatValue(ambient.humidityPercent);
  json += F(",\"ambient_status\":\"");
  json += ambientStatusText(ambient.status);
  json += F("\",\"distance_raw_median_mm\":");
  json += distance.available() ? String(distance.median) : String("null");
  json += F(",\"distance_corrected_mm\":");
  json += jsonFloatValue(correctedDistanceMm);
  json += F(",\"dough_height_mm\":");
  json += jsonFloatValue(doughHeightMm);
  json += F(",\"distance_status\":\"");
  json += distanceStatus;
  json += F("\"}");
  updateStatusLed();
  return json;
}

String toggleSessionFromWeb() {
  toggleSession();
  String json;
  json.reserve(64);
  json += F("{\"ok\":true,\"queued\":false,\"session_active\":");
  json += sessionActive ? F("true") : F("false");
  json += F("}");
  return json;
}

String configurationLockedJson() {
  return F("{\"ok\":false,\"message\":\"Configurazione bloccata durante una sessione attiva.\"}");
}

String saveFloursFromWeb(const String& body) {
  return sessionActive ? configurationLockedJson()
                       : sessionConfigStore.saveFlours(body);
}

String savePresetsFromWeb(const String& body) {
  return sessionActive ? configurationLockedJson()
                       : sessionConfigStore.savePresets(body);
}

String saveDraftFromWeb(const String& body) {
  return sessionActive ? configurationLockedJson()
                       : sessionConfigStore.saveDraft(body);
}

String importConfigFromWeb(const String& body) {
  return sessionActive ? configurationLockedJson()
                       : sessionConfigStore.importBackup(body);
}

}  // namespace

void setup() {
  Serial.begin(Config::SERIAL_BAUD);
  delay(Config::STARTUP_UPLOAD_GRACE_MS);

  bootResetReason = esp_reset_reason();
  bootCrashBreadcrumb = crashBreadcrumb;
  panicSafeMode = bootResetReason == ESP_RST_PANIC;
  panicQueueSkipReported = false;
  panicSessionFileSkipReported = false;
  panicMeasurementSkipReported = false;
  sessionFileEnabled = !panicSafeMode;
  if (panicSafeMode && bootCrashBreadcrumb != BREADCRUMB_IDLE) {
    lastPanicBreadcrumb = bootCrashBreadcrumb;
  }
  setCrashBreadcrumb(BREADCRUMB_IDLE);
  if (panicSafeMode) {
    emitEvent("warning", "PANIC_SAFE_MODE_ENABLED");
  }

  initializeStatusLed();

  initializeDeviceId();
  storageReady = mountLittleFsSafely();
  emitEvent(storageReady ? "status" : "error",
            storageReady ? "LITTLEFS_READY" : "LITTLEFS_MOUNT_FAILED");
  if (storageReady) {
    recipeConfigReady = sessionConfigStore.begin(LittleFS);
    emitEvent(recipeConfigReady ? "status" : "error",
              recipeConfigReady ? "RECIPE_CONFIG_READY"
                                : "RECIPE_CONFIG_FAILED");
    telemetryQueueReady = telemetryQueue.begin(LittleFS);
    if (telemetryQueueReady) {
      influxUploader.begin(telemetryQueue);
    }
    emitEvent(telemetryQueueReady ? "status" : "error",
              telemetryQueueReady ? "TELEMETRY_QUEUE_READY"
                                  : "TELEMETRY_QUEUE_FAILED");
  }
  setenv("TZ", Config::TIMEZONE, 1);
  tzset();

  Wire.begin(Config::SDA_PIN, Config::SCL_PIN);
  Wire.setClock(Config::I2C_FREQUENCY_HZ);
  Wire.setTimeOut(Config::I2C_TRANSACTION_TIMEOUT_MS);
  delay(100);
  scanI2cBus();

  distanceSensorReady = initializeDistanceSensor();
  warmUpDistanceSensor();
  ambientSensorReady = initializeAmbientSensor();
  doughSensorReady = initializeDoughSensor();
  lastSensorRetryMs = millis();

  webInterface.configure(webStatusJson, webTestJson, toggleSessionFromWeb);
  webInterface.configureRecipes(
      []() { return sessionConfigStore.floursJson(); }, saveFloursFromWeb,
      []() { return sessionConfigStore.presetsJson(); }, savePresetsFromWeb,
      []() { return sessionConfigStore.draftJson(); }, saveDraftFromWeb,
      []() { return sessionConfigStore.backupJson(); }, importConfigFromWeb);

  Serial.print(F("{\"schema\":\"fermentlab.event.v1\",\"type\":\"ready\",\"device_id\":\""));
  Serial.print(deviceId);
  Serial.print(F("\",\"board_profile\":\""));
  Serial.print(Config::BOARD_PROFILE);
  Serial.print(F("\",\"sda_gpio\":"));
  Serial.print(Config::SDA_PIN);
  Serial.print(F(",\"scl_gpio\":"));
  Serial.print(Config::SCL_PIN);
  Serial.print(F(",\"ds18b20_gpio\":"));
  Serial.print(Config::DS18B20_PIN);
  Serial.print(F(",\"interval_s\":"));
  Serial.print(Config::DEFAULT_READING_INTERVAL_S);
  Serial.println(F("}"));
}

void loop() {
  serviceConnectivity();
  serviceSensorRecovery();
  serviceDoughSensor();
  webInterface.tick();

  if (sessionActive &&
      millis() - lastReadingMs >= sessionReadingIntervalSeconds * 1000UL) {
    if (panicSafeMode) {
      if (!panicMeasurementSkipReported) {
        emitEvent("warning", "PANIC_SAFE_MODE_MEASUREMENT_DISABLED");
        panicMeasurementSkipReported = true;
      }
      lastReadingMs = millis();
    } else {
      emitMeasurement();
      lastReadingMs = millis();
    }
  }

  if (telemetryQueueReady) {
    const InfluxUploadEvent uploadEvent = influxUploader.tick();
    if (uploadEvent == InfluxUploadEvent::Sent) {
      influxFailureActive = false;
      emitEvent("status", "INFLUX_BATCH_SENT");
    } else if (uploadEvent == InfluxUploadEvent::Failed) {
      influxFailureActive = true;
      emitEvent("error", "INFLUX_SEND_FAILED");
    } else if (uploadEvent == InfluxUploadEvent::ConfigurationMissing) {
      influxFailureActive = true;
      emitEvent("error", "INFLUX_CONFIGURATION_MISSING");
    }
  }
  updateStatusLed();
  delay(2);
}
