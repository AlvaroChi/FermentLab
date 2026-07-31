#include <Arduino.h>
#include <VL53L0X.h>
#include <Wire.h>

#include <algorithm>
#include <cctype>
#include <cstdlib>

#include "Config.h"

namespace {

VL53L0X sensor;
bool sensorReady = false;
bool acquisitionRunning = false;

int buttonRawState = HIGH;
int buttonStableState = HIGH;
uint32_t buttonLastChangeMs = 0;

uint32_t readingIntervalSeconds =
    Config::DEFAULT_READING_INTERVAL_SECONDS;
uint32_t lastReadingMs = 0;

bool baselineAvailable = false;
float baselineDistanceMm = NAN;
bool latestDistanceAvailable = false;
float latestCorrectedDistanceMm = NAN;

constexpr size_t COMMAND_BUFFER_SIZE = 64;
char commandBuffer[COMMAND_BUFFER_SIZE] = {};
size_t commandLength = 0;

constexpr char CSV_HEADER[] =
    "tempo_ms,n_valide,n_tentativi,raw_min_mm,raw_media_mm,"
    "raw_mediana_mm,raw_max_mm,distanza_corretta_mm,crescita_mm,stato";

enum class InvalidReason : uint8_t {
  None,
  Timeout,
  I2cError,
  DeviceStatus,
  OutOfRange,
};

struct Measurement {
  uint16_t millimeters = 0;
  uint8_t deviceStatus = 0;
  InvalidReason invalidReason = InvalidReason::None;

  bool valid() const { return invalidReason == InvalidReason::None; }
};

struct FilteredReading {
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

bool i2cDevicePresent(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}

bool initializeSensor() {
  Serial.println(F("# Inizializzazione VL53L0X..."));
  if (!i2cDevicePresent(Config::SENSOR_I2C_ADDRESS)) {
    Serial.println(F("# ERRORE: nessuna risposta I2C all'indirizzo 0x29."));
    return false;
  }

  sensor.setTimeout(Config::SENSOR_TIMEOUT_MS);
  if (!sensor.init(true)) {
    Serial.println(F("# ERRORE: inizializzazione VL53L0X fallita."));
    return false;
  }
  if (!sensor.setSignalRateLimit(Config::SIGNAL_RATE_LIMIT_MCPS)) {
    Serial.println(F("# ERRORE: limite di segnale non accettato."));
    return false;
  }
  if (!sensor.setMeasurementTimingBudget(
          Config::TIMING_BUDGET_MS * 1000UL)) {
    Serial.println(F("# ERRORE: timing budget non accettato."));
    return false;
  }

  sensor.startContinuous();
  Serial.println(F("# Sensore pronto."));
  return true;
}

uint32_t measurementTimeoutMs() {
  const uint32_t derived =
      Config::TIMING_BUDGET_MS + Config::TIMEOUT_MARGIN_MS;
  return derived > Config::SENSOR_TIMEOUT_MS ? derived
                                             : Config::SENSOR_TIMEOUT_MS;
}

Measurement readMeasurement() {
  Measurement measurement;
  const uint32_t startedAt = millis();

  while (true) {
    const uint8_t interruptStatus =
        sensor.readReg(VL53L0X::RESULT_INTERRUPT_STATUS);
    if (sensor.last_status != 0) {
      measurement.invalidReason = InvalidReason::I2cError;
      return measurement;
    }
    if ((interruptStatus & 0x07) != 0) {
      break;
    }
    if (millis() - startedAt >= measurementTimeoutMs()) {
      measurement.invalidReason = InvalidReason::Timeout;
      return measurement;
    }
    delay(1);
  }

  const uint8_t rawRangeStatus =
      sensor.readReg(VL53L0X::RESULT_RANGE_STATUS);
  if (sensor.last_status != 0) {
    measurement.invalidReason = InvalidReason::I2cError;
    return measurement;
  }
  measurement.deviceStatus = (rawRangeStatus & 0x78) >> 3;

  measurement.millimeters =
      sensor.readReg16Bit(VL53L0X::RESULT_RANGE_STATUS + 10);
  const bool rangeReadOk = sensor.last_status == 0;
  sensor.writeReg(VL53L0X::SYSTEM_INTERRUPT_CLEAR, 0x01);

  if (!rangeReadOk || sensor.last_status != 0) {
    measurement.invalidReason = InvalidReason::I2cError;
  } else if (measurement.deviceStatus !=
             Config::DEVICE_STATUS_RANGE_COMPLETE) {
    measurement.invalidReason = InvalidReason::DeviceStatus;
  } else if (measurement.millimeters < Config::MIN_SENSOR_RANGE_MM ||
             measurement.millimeters > Config::MAX_SENSOR_RANGE_MM ||
             measurement.millimeters >= 8190) {
    measurement.invalidReason = InvalidReason::OutOfRange;
  }
  return measurement;
}

void warmUpSensor() {
  if (!sensorReady) {
    return;
  }
  for (size_t i = 0; i < Config::WARMUP_READINGS; ++i) {
    (void)readMeasurement();
    delay(Config::SAMPLE_DELAY_MS);
  }
}

FilteredReading acquireFilteredReading() {
  FilteredReading result;
  while (result.validCount < Config::FILTER_SAMPLE_COUNT &&
         result.attempts < Config::MAX_SAMPLE_ATTEMPTS) {
    const Measurement measurement = readMeasurement();
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
  result.maximum = result.values[result.validCount - 1];
  result.median = result.values[result.validCount / 2];

  uint32_t sum = 0;
  for (size_t i = 0; i < result.validCount; ++i) {
    sum += result.values[i];
  }
  result.mean =
      static_cast<float>(sum) / static_cast<float>(result.validCount);
  return result;
}

float calibrateDistance(float measuredMm) {
  return (measuredMm - Config::CALIBRATION_INTERCEPT_MM) /
         Config::CALIBRATION_SLOPE;
}

void printCsvFloat(float value) {
  if (isnan(value)) {
    Serial.print(F("nan"));
  } else {
    Serial.print(value, 3);
  }
}

void printUnavailableRow(const char* state) {
  Serial.print(millis());
  Serial.print(F(",0,0,nan,nan,nan,nan,nan,nan,"));
  Serial.println(state);
}

void performReading() {
  if (!sensorReady) {
    printUnavailableRow("SENSORE_NON_PRONTO");
    return;
  }

  const FilteredReading reading = acquireFilteredReading();
  if (!reading.available()) {
    Serial.print(millis());
    Serial.print(',');
    Serial.print(reading.validCount);
    Serial.print(',');
    Serial.print(reading.attempts);
    Serial.println(F(",nan,nan,nan,nan,nan,nan,LETTURE_INSUFFICIENTI"));
    return;
  }

  // La mediana elimina eventuali letture isolate prima della calibrazione.
  const float correctedMm = calibrateDistance(reading.median);
  const bool insideCalibratedRange =
      correctedMm >= Config::CALIBRATED_MIN_MM &&
      correctedMm <= Config::CALIBRATED_MAX_MM;

  const char* state = "OK";
  float growthMm = NAN;
  if (!insideCalibratedRange) {
    latestDistanceAvailable = false;
    state = "FUORI_RANGE_CALIBRATO";
  } else {
    latestCorrectedDistanceMm = correctedMm;
    latestDistanceAvailable = true;
    if (!baselineAvailable) {
      baselineDistanceMm = correctedMm;
      baselineAvailable = true;
      state = "OK_BASELINE_INIZIALE";
    }
    growthMm = baselineDistanceMm - correctedMm;
  }

  Serial.print(millis());
  Serial.print(',');
  Serial.print(reading.validCount);
  Serial.print(',');
  Serial.print(reading.attempts);
  Serial.print(',');
  Serial.print(reading.minimum);
  Serial.print(',');
  printCsvFloat(reading.mean);
  Serial.print(',');
  Serial.print(reading.median);
  Serial.print(',');
  Serial.print(reading.maximum);
  Serial.print(',');
  printCsvFloat(insideCalibratedRange ? correctedMm : NAN);
  Serial.print(',');
  printCsvFloat(growthMm);
  Serial.print(',');
  Serial.println(state);
}

void printHelp() {
  Serial.println(F("# Comandi: start, stop, read, baseline, clear, interval=30, status, header, retry, help"));
}

void printStatus() {
  Serial.printf("# Acquisizione=%s, pulsante=GPIO%u (attivo LOW)\n",
                acquisitionRunning ? "ATTIVA" : "IN_ATTESA",
                Config::BUTTON_PIN);
  Serial.printf("# Sensore=%s, intervallo=%lu s, range calibrato=%.0f..%.0f mm\n",
                sensorReady ? "pronto" : "NON pronto",
                static_cast<unsigned long>(readingIntervalSeconds),
                Config::CALIBRATED_MIN_MM, Config::CALIBRATED_MAX_MM);
  if (baselineAvailable) {
    Serial.printf("# Baseline=%.3f mm\n", baselineDistanceMm);
  } else {
    Serial.println(F("# Baseline non disponibile."));
  }
}

void clearBaseline() {
  baselineAvailable = false;
  baselineDistanceMm = NAN;
  latestDistanceAvailable = false;
  latestCorrectedDistanceMm = NAN;
}

void startAcquisition(const char* source) {
  if (acquisitionRunning) {
    Serial.println(F("# Acquisizione gia' attiva."));
    return;
  }

  clearBaseline();
  acquisitionRunning = true;
  Serial.printf("# EVENTO: START (%s)\n", source);
  Serial.println(CSV_HEADER);
  performReading();
  lastReadingMs = millis();
}

void stopAcquisition(const char* source) {
  if (!acquisitionRunning) {
    Serial.println(F("# Acquisizione gia' ferma."));
    return;
  }

  acquisitionRunning = false;
  Serial.printf("# EVENTO: STOP (%s)\n", source);
}

void toggleAcquisitionFromButton() {
  if (acquisitionRunning) {
    stopAcquisition("PULSANTE_GPIO4");
  } else {
    startAcquisition("PULSANTE_GPIO4");
  }
}

void pollButton() {
  const int currentRawState = digitalRead(Config::BUTTON_PIN);
  if (currentRawState != buttonRawState) {
    buttonRawState = currentRawState;
    buttonLastChangeMs = millis();
  }

  if (buttonRawState != buttonStableState &&
      millis() - buttonLastChangeMs >= Config::BUTTON_DEBOUNCE_MS) {
    buttonStableState = buttonRawState;
    if (buttonStableState == LOW) {
      toggleAcquisitionFromButton();
    }
  }
}

bool parseUnsigned(const String& text, uint32_t& value) {
  if (text.length() == 0) {
    return false;
  }
  char* end = nullptr;
  const unsigned long parsed = strtoul(text.c_str(), &end, 10);
  while (end != nullptr && isspace(static_cast<unsigned char>(*end))) {
    ++end;
  }
  if (end == text.c_str() || (end != nullptr && *end != '\0')) {
    return false;
  }
  value = static_cast<uint32_t>(parsed);
  return true;
}

void processCommand(const char* rawCommand) {
  String command(rawCommand);
  command.trim();
  command.toLowerCase();
  if (command.length() == 0) {
    return;
  }

  if (command == "start") {
    startAcquisition("SERIALE");
  } else if (command == "stop") {
    stopAcquisition("SERIALE");
  } else if (command == "read") {
    performReading();
    lastReadingMs = millis();
  } else if (command == "baseline") {
    if (latestDistanceAvailable) {
      baselineDistanceMm = latestCorrectedDistanceMm;
      baselineAvailable = true;
      Serial.printf("# Nuova baseline=%.3f mm\n", baselineDistanceMm);
    } else {
      Serial.println(F("# ERRORE: nessuna distanza valida per la baseline."));
    }
  } else if (command == "clear") {
    clearBaseline();
    Serial.println(F("# Baseline cancellata; la prossima lettura valida sara' lo zero."));
  } else if (command == "status") {
    printStatus();
  } else if (command == "header") {
    Serial.println(CSV_HEADER);
  } else if (command == "retry") {
    if (!sensorReady) {
      sensorReady = initializeSensor();
      warmUpSensor();
    } else {
      Serial.println(F("# Il sensore e' gia' pronto."));
    }
  } else if (command == "help" || command == "?") {
    printHelp();
  } else if (command.startsWith("interval=")) {
    uint32_t requested = 0;
    if (!parseUnsigned(command.substring(9), requested) ||
        requested < Config::MIN_READING_INTERVAL_SECONDS ||
        requested > Config::MAX_READING_INTERVAL_SECONDS) {
      Serial.printf("# ERRORE: interval deve essere tra %lu e %lu secondi.\n",
                    static_cast<unsigned long>(
                        Config::MIN_READING_INTERVAL_SECONDS),
                    static_cast<unsigned long>(
                        Config::MAX_READING_INTERVAL_SECONDS));
    } else {
      readingIntervalSeconds = requested;
      Serial.printf("# Intervallo impostato a %lu secondi.\n",
                    static_cast<unsigned long>(readingIntervalSeconds));
    }
  } else {
    Serial.println(F("# Comando non riconosciuto; usare help."));
  }
}

void pollSerial() {
  while (Serial.available() > 0) {
    const char incoming = static_cast<char>(Serial.read());
    if (incoming == '\r' || incoming == '\n') {
      if (commandLength > 0) {
        commandBuffer[commandLength] = '\0';
        processCommand(commandBuffer);
        commandLength = 0;
      }
      continue;
    }

    if (commandLength < COMMAND_BUFFER_SIZE - 1) {
      commandBuffer[commandLength++] = incoming;
    } else {
      commandLength = 0;
      Serial.println(F("# ERRORE: comando troppo lungo."));
    }
  }
}

}  // namespace

void setup() {
  Serial.begin(Config::SERIAL_BAUD);
  delay(500);

  Serial.println(F("\n# === FermentLab: monitor altezza ==="));
  pinMode(Config::BUTTON_PIN, INPUT_PULLUP);
  buttonRawState = digitalRead(Config::BUTTON_PIN);
  buttonStableState = buttonRawState;
  buttonLastChangeMs = millis();

  Wire.begin(Config::SDA_PIN, Config::SCL_PIN);
  Wire.setClock(Config::I2C_FREQUENCY_HZ);
  delay(100);

  sensorReady = initializeSensor();
  warmUpSensor();
  printStatus();
  printHelp();
  Serial.println(CSV_HEADER);
  Serial.println(F("# IN ATTESA: premere il pulsante su GPIO4 oppure inviare start."));
}

void loop() {
  pollButton();
  pollSerial();

  const uint32_t intervalMs = readingIntervalSeconds * 1000UL;
  if (acquisitionRunning && millis() - lastReadingMs >= intervalMs) {
    performReading();
    lastReadingMs = millis();
  }
  delay(2);
}
