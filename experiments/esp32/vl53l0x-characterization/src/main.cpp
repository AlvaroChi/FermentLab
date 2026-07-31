#include <Arduino.h>
#include <VL53L0X.h>
#include <Wire.h>

#include <cctype>
#include <cmath>
#include <cstdlib>
#include <new>

#include "Config.h"
#include "Statistics.h"

namespace {

VL53L0X sensor;
bool sensorReady = false;

size_t sampleCount = Config::DEFAULT_SAMPLE_COUNT;
uint32_t sampleDelayMs = Config::DEFAULT_SAMPLE_DELAY_MS;
uint32_t timingBudgetMs = Config::DEFAULT_TIMING_BUDGET_MS;

constexpr size_t COMMAND_BUFFER_SIZE = 64;
char commandBuffer[COMMAND_BUFFER_SIZE] = {};
size_t commandLength = 0;

constexpr char CSV_HEADER[] =
    "distanza_reale_mm,n_totali,n_valide,n_non_valide,media_mm,mediana_mm,"
    "std_mm,min_mm,p05_mm,p25_mm,p75_mm,p95_mm,max_mm,errore_media_mm,"
    "errore_mediana_mm";

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

struct InvalidCounters {
  size_t timeout = 0;
  size_t i2c = 0;
  size_t deviceStatus = 0;
  size_t outOfRange = 0;

  void add(InvalidReason reason) {
    switch (reason) {
      case InvalidReason::Timeout:
        ++timeout;
        break;
      case InvalidReason::I2cError:
        ++i2c;
        break;
      case InvalidReason::DeviceStatus:
        ++deviceStatus;
        break;
      case InvalidReason::OutOfRange:
        ++outOfRange;
        break;
      case InvalidReason::None:
        break;
    }
  }
};

bool i2cDevicePresent(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}

bool initializeSensor() {
  Serial.println(F("\nInizializzazione VL53L0X..."));
  if (!i2cDevicePresent(Config::SENSOR_I2C_ADDRESS)) {
    Serial.println(F("ERRORE: nessuna risposta I2C all'indirizzo 0x29."));
    Serial.println(F("Controllare VCC, GND, SDA e SCL; usare 'retry' per riprovare."));
    return false;
  }

  sensor.setTimeout(Config::SENSOR_TIMEOUT_MS);
  if (!sensor.init(true)) {
    Serial.println(F("ERRORE: il sensore risponde, ma l'inizializzazione e' fallita."));
    return false;
  }

  if (!sensor.setSignalRateLimit(Config::SIGNAL_RATE_LIMIT_MCPS)) {
    Serial.println(F("ERRORE: impossibile impostare il limite di segnale."));
    return false;
  }
  if (!sensor.setMeasurementTimingBudget(timingBudgetMs * 1000UL)) {
    Serial.println(F("ERRORE: timing budget non accettato dal sensore."));
    return false;
  }

  sensor.startContinuous();
  Serial.printf("Sensore pronto: indirizzo=0x%02X, timing budget=%lu ms\n",
                sensor.getAddress(), static_cast<unsigned long>(timingBudgetMs));
  return true;
}

uint32_t measurementTimeoutMs() {
  const uint32_t derived = timingBudgetMs + Config::TIMEOUT_MARGIN_MS;
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

  // L'interrupt va liberato anche quando il risultato non e' valido.
  sensor.writeReg(VL53L0X::SYSTEM_INTERRUPT_CLEAR, 0x01);
  if (!rangeReadOk || sensor.last_status != 0) {
    measurement.invalidReason = InvalidReason::I2cError;
  } else if (measurement.deviceStatus !=
             Config::DEVICE_STATUS_RANGE_COMPLETE) {
    measurement.invalidReason = InvalidReason::DeviceStatus;
  } else if (measurement.millimeters < Config::MIN_VALID_RANGE_MM ||
             measurement.millimeters > Config::MAX_VALID_RANGE_MM ||
             measurement.millimeters >= 8190) {
    measurement.invalidReason = InvalidReason::OutOfRange;
  }

  return measurement;
}

const char* invalidReasonText(InvalidReason reason) {
  switch (reason) {
    case InvalidReason::Timeout:
      return "timeout";
    case InvalidReason::I2cError:
      return "errore I2C";
    case InvalidReason::DeviceStatus:
      return "stato sensore non valido";
    case InvalidReason::OutOfRange:
      return "fuori intervallo";
    case InvalidReason::None:
      return "nessuno";
  }
  return "sconosciuto";
}

void printSingleReading() {
  if (!sensorReady) {
    Serial.println(F("ERRORE: sensore non pronto. Usare 'retry'."));
    return;
  }

  const Measurement measurement = readMeasurement();
  if (measurement.valid()) {
    Serial.printf("Distanza: %u mm\n", measurement.millimeters);
  } else {
    Serial.printf("Lettura non valida: %s (stato=%u)\n",
                  invalidReasonText(measurement.invalidReason),
                  measurement.deviceStatus);
  }
}

void printCsvHeader() {
  Serial.println(CSV_HEADER);
}

void printHelp() {
  Serial.println(F("\nComandi disponibili (premere Invio):"));
  Serial.println(F("  50          acquisisce una serie alla distanza reale di 50 mm"));
  Serial.println(F("  read        esegue una singola lettura"));
  Serial.println(F("  n=200       imposta le acquisizioni per serie (10..10000)"));
  Serial.println(F("  delay=20    pausa aggiuntiva tra letture, in ms"));
  Serial.println(F("  budget=50   timing budget VL53L0X, in ms (20..1000)"));
  Serial.println(F("  status      mostra sensore e configurazione corrente"));
  Serial.println(F("  header      ristampa l'intestazione CSV"));
  Serial.println(F("  retry       ritenta l'inizializzazione del sensore"));
  Serial.println(F("  help        mostra questo elenco"));
  Serial.println(F("\nDurante una serie inviare 'x' per interromperla."));
}

void printStatus() {
  Serial.println(F("\nConfigurazione corrente:"));
  Serial.printf("  sensore: %s\n", sensorReady ? "pronto" : "NON pronto");
  Serial.printf("  campioni per serie: %u\n",
                static_cast<unsigned>(sampleCount));
  Serial.printf("  delay aggiuntivo: %lu ms\n",
                static_cast<unsigned long>(sampleDelayMs));
  Serial.printf("  timing budget: %lu ms\n",
                static_cast<unsigned long>(timingBudgetMs));
  Serial.printf("  I2C: SDA=%u, SCL=%u, clock=%lu Hz, address=0x%02X\n",
                Config::SDA_PIN, Config::SCL_PIN,
                static_cast<unsigned long>(Config::I2C_FREQUENCY_HZ),
                Config::SENSOR_I2C_ADDRESS);
}

void printCsvNumber(double value) {
  if (isnan(value)) {
    Serial.print(F("nan"));
  } else {
    Serial.print(value, 3);
  }
}

void printCsvRow(double realDistance, size_t total, size_t valid,
                 const StatisticsResult& stats) {
  Serial.print(realDistance, 3);
  Serial.print(',');
  Serial.print(total);
  Serial.print(',');
  Serial.print(valid);
  Serial.print(',');
  Serial.print(total - valid);

  const double values[] = {
      stats.mean,
      stats.median,
      stats.standardDeviation,
      stats.minimum,
      stats.p05,
      stats.p25,
      stats.p75,
      stats.p95,
      stats.maximum,
      stats.available ? stats.mean - realDistance : NAN,
      stats.available ? stats.median - realDistance : NAN,
  };
  for (double value : values) {
    Serial.print(',');
    printCsvNumber(value);
  }
  Serial.println();
}

bool abortRequested() {
  bool requested = false;
  while (Serial.available() > 0) {
    const char incoming = static_cast<char>(Serial.read());
    if (incoming == 'x' || incoming == 'X' || incoming == 27) {
      requested = true;
    }
  }
  return requested;
}

void runTest(double realDistance) {
  if (!sensorReady) {
    Serial.println(F("ERRORE: sensore non pronto. Correggere i collegamenti e usare 'retry'."));
    return;
  }

  uint16_t* validReadings = new (std::nothrow) uint16_t[sampleCount];
  if (validReadings == nullptr) {
    Serial.println(F("ERRORE: memoria insufficiente; ridurre n."));
    return;
  }

  Serial.printf(
      "\nTEST: distanza reale=%.3f mm, acquisizioni=%u, delay=%lu ms, "
      "budget=%lu ms\n",
      realDistance, static_cast<unsigned>(sampleCount),
      static_cast<unsigned long>(sampleDelayMs),
      static_cast<unsigned long>(timingBudgetMs));
  Serial.printf("Warm-up: %u letture non conteggiate...\n",
                static_cast<unsigned>(Config::WARMUP_READINGS));

  for (size_t i = 0; i < Config::WARMUP_READINGS; ++i) {
    if (abortRequested()) {
      Serial.println(F("Serie annullata durante il warm-up."));
      delete[] validReadings;
      return;
    }
    (void)readMeasurement();
    if (sampleDelayMs > 0) {
      delay(sampleDelayMs);
    }
  }

  size_t acquiredCount = 0;
  size_t validCount = 0;
  size_t nextProgressPercent = 10;
  InvalidCounters invalid;
  bool aborted = false;
  const uint32_t acquisitionStartedAt = millis();

  for (size_t i = 0; i < sampleCount; ++i) {
    if (abortRequested()) {
      aborted = true;
      break;
    }

    const Measurement measurement = readMeasurement();
    ++acquiredCount;
    if (measurement.valid()) {
      validReadings[validCount++] = measurement.millimeters;
    } else {
      invalid.add(measurement.invalidReason);
    }

    const size_t progressPercent = 100 * acquiredCount / sampleCount;
    if (progressPercent >= nextProgressPercent) {
      Serial.printf("Progresso: %u%% (%u/%u)\n",
                    static_cast<unsigned>(progressPercent),
                    static_cast<unsigned>(acquiredCount),
                    static_cast<unsigned>(sampleCount));
      nextProgressPercent += 10;
    }

    if (sampleDelayMs > 0 && i + 1 < sampleCount) {
      delay(sampleDelayMs);
    }
  }

  const uint32_t elapsedMs = millis() - acquisitionStartedAt;
  const StatisticsResult stats =
      computeStatistics(validReadings, validCount);

  Serial.println(F("\n--- RIEPILOGO ---"));
  Serial.printf("Stato serie:          %s\n",
                aborted ? "INTERROTTA" : "completata");
  Serial.printf("Distanza reale:       %.3f mm\n", realDistance);
  Serial.printf("Letture acquisite:    %u\n",
                static_cast<unsigned>(acquiredCount));
  Serial.printf("Letture valide:       %u",
                static_cast<unsigned>(validCount));
  if (acquiredCount > 0) {
    Serial.printf(" (%.2f%%)",
                  100.0 * static_cast<double>(validCount) /
                      static_cast<double>(acquiredCount));
  }
  Serial.println();
  Serial.printf("Letture non valide:   %u\n",
                static_cast<unsigned>(acquiredCount - validCount));
  Serial.printf("  timeout=%u, I2C=%u, stato sensore=%u, fuori range=%u\n",
                static_cast<unsigned>(invalid.timeout),
                static_cast<unsigned>(invalid.i2c),
                static_cast<unsigned>(invalid.deviceStatus),
                static_cast<unsigned>(invalid.outOfRange));
  Serial.printf("Tempo acquisizione:   %.2f s\n", elapsedMs / 1000.0);

  if (stats.available) {
    Serial.printf("Media:                %.3f mm (errore %+.3f mm)\n",
                  stats.mean, stats.mean - realDistance);
    Serial.printf("Mediana:              %.3f mm (errore %+.3f mm)\n",
                  stats.median, stats.median - realDistance);
    Serial.printf("Deviazione standard:  %.3f mm\n",
                  stats.standardDeviation);
    Serial.printf("Min / Max:            %.3f / %.3f mm\n",
                  stats.minimum, stats.maximum);
    Serial.printf("P05 / P25:            %.3f / %.3f mm\n",
                  stats.p05, stats.p25);
    Serial.printf("P75 / P95:            %.3f / %.3f mm\n",
                  stats.p75, stats.p95);
  } else {
    Serial.println(F("Nessuna lettura valida: statistiche non disponibili."));
  }

  if (acquiredCount > 0) {
    Serial.println(F("\nCSV:"));
    printCsvHeader();
    printCsvRow(realDistance, acquiredCount, validCount, stats);
  }
  Serial.println(F("\nPronto per una nuova distanza reale (oppure 'help')."));

  delete[] validReadings;
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

bool parseDistance(String text, double& value) {
  text.replace(',', '.');
  char* end = nullptr;
  const double parsed = strtod(text.c_str(), &end);
  while (end != nullptr && isspace(static_cast<unsigned char>(*end))) {
    ++end;
  }
  if (end == text.c_str() || (end != nullptr && *end != '\0') ||
      !isfinite(parsed) || parsed <= 0.0 ||
      parsed > Config::MAX_REAL_DISTANCE_MM) {
    return false;
  }
  value = parsed;
  return true;
}

void setTimingBudget(uint32_t requestedMs) {
  if (requestedMs < Config::MIN_TIMING_BUDGET_MS ||
      requestedMs > Config::MAX_TIMING_BUDGET_MS) {
    Serial.printf("ERRORE: budget deve essere tra %lu e %lu ms.\n",
                  static_cast<unsigned long>(Config::MIN_TIMING_BUDGET_MS),
                  static_cast<unsigned long>(Config::MAX_TIMING_BUDGET_MS));
    return;
  }

  if (!sensorReady) {
    timingBudgetMs = requestedMs;
    Serial.printf(
        "Timing budget memorizzato: %lu ms; verra' applicato con 'retry'.\n",
        static_cast<unsigned long>(timingBudgetMs));
    return;
  }

  sensor.stopContinuous();
  if (sensor.setMeasurementTimingBudget(requestedMs * 1000UL)) {
    timingBudgetMs = requestedMs;
    Serial.printf("Timing budget impostato a %lu ms.\n",
                  static_cast<unsigned long>(timingBudgetMs));
  } else {
    Serial.println(F("ERRORE: timing budget rifiutato; resta il valore precedente."));
  }
  sensor.startContinuous();
}

void processCommand(const char* rawCommand) {
  String command(rawCommand);
  command.trim();
  command.toLowerCase();
  if (command.length() == 0) {
    return;
  }

  if (command == "help" || command == "?") {
    printHelp();
    return;
  }
  if (command == "read") {
    printSingleReading();
    return;
  }
  if (command == "header") {
    printCsvHeader();
    return;
  }
  if (command == "status") {
    printStatus();
    return;
  }
  if (command == "retry") {
    if (sensorReady) {
      Serial.println(F("Il sensore e' gia' pronto."));
    } else {
      sensorReady = initializeSensor();
    }
    return;
  }

  uint32_t unsignedValue = 0;
  if (command.startsWith("n=")) {
    if (!parseUnsigned(command.substring(2), unsignedValue) ||
        unsignedValue < Config::MIN_SAMPLE_COUNT ||
        unsignedValue > Config::MAX_SAMPLE_COUNT) {
      Serial.printf("ERRORE: n deve essere tra %u e %u.\n",
                    static_cast<unsigned>(Config::MIN_SAMPLE_COUNT),
                    static_cast<unsigned>(Config::MAX_SAMPLE_COUNT));
      return;
    }
    sampleCount = unsignedValue;
    Serial.printf("Numero di acquisizioni impostato a %u.\n",
                  static_cast<unsigned>(sampleCount));
    return;
  }
  if (command.startsWith("delay=")) {
    if (!parseUnsigned(command.substring(6), unsignedValue) ||
        unsignedValue > Config::MAX_SAMPLE_DELAY_MS) {
      Serial.printf("ERRORE: delay deve essere tra 0 e %lu ms.\n",
                    static_cast<unsigned long>(
                        Config::MAX_SAMPLE_DELAY_MS));
      return;
    }
    sampleDelayMs = unsignedValue;
    Serial.printf("Delay aggiuntivo impostato a %lu ms.\n",
                  static_cast<unsigned long>(sampleDelayMs));
    return;
  }
  if (command.startsWith("budget=")) {
    if (!parseUnsigned(command.substring(7), unsignedValue)) {
      Serial.println(F("ERRORE: usare per esempio budget=50 oppure budget=200."));
      return;
    }
    setTimingBudget(unsignedValue);
    return;
  }

  double realDistance = 0.0;
  if (parseDistance(command, realDistance)) {
    runTest(realDistance);
    return;
  }

  Serial.println(F("Comando non riconosciuto. Digitare 'help'."));
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
      Serial.println(F("ERRORE: comando troppo lungo; buffer svuotato."));
    }
  }
}

}  // namespace

void setup() {
  Serial.begin(Config::SERIAL_BAUD);
  delay(500);

  Serial.println(F("\n=== Taratura ESP32 + VL53L0X ==="));
  Wire.begin(Config::SDA_PIN, Config::SCL_PIN);
  Wire.setClock(Config::I2C_FREQUENCY_HZ);
  delay(100);

  sensorReady = initializeSensor();
  printStatus();
  printHelp();
  Serial.println(F("\nInserire la distanza reale in millimetri:"));
}

void loop() {
  pollSerial();
  delay(2);
}
