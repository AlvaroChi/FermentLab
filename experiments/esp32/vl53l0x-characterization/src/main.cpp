#include <Arduino.h>
#include <VL53L0X.h>
#include <Wire.h>

#include "Config.h"

namespace {

VL53L0X sensor;
bool sensorReady = false;
uint32_t lastReadingMs = 0;

bool initializeSensor() {
  Serial.println(F("Inizializzazione VL53L0X..."));

  sensor.setTimeout(Config::SENSOR_TIMEOUT_MS);
  if (!sensor.init()) {
    Serial.println(F("ERRORE: VL53L0X non trovato."));
    Serial.println(F("Controllare alimentazione, GND, SDA e SCL."));
    return false;
  }

  if (!sensor.setMeasurementTimingBudget(
          Config::MEASUREMENT_TIMING_BUDGET_MS * 1000UL)) {
    Serial.println(F("ERRORE: timing budget non accettato."));
    return false;
  }

  Serial.println(F("Sensore pronto."));
  return true;
}

void printDistance() {
  const uint16_t distanceMm = sensor.readRangeSingleMillimeters();

  if (sensor.timeoutOccurred()) {
    Serial.println(F("ERRORE: timeout durante la lettura."));
    return;
  }

  Serial.print(F("Distanza: "));
  Serial.print(distanceMm);
  Serial.println(F(" mm"));
}

}  // namespace

void setup() {
  Serial.begin(Config::SERIAL_BAUD);
  delay(500);

  Serial.println(F("\n=== Test hardware ESP32 + VL53L0X ==="));
  Wire.begin(Config::SDA_PIN, Config::SCL_PIN);
  Wire.setClock(Config::I2C_FREQUENCY_HZ);

  sensorReady = initializeSensor();

  Serial.print(F("Intervallo letture: "));
  Serial.print(Config::READ_INTERVAL_SECONDS);
  Serial.println(F(" s"));

  // Consente di effettuare la prima lettura immediatamente.
  lastReadingMs = millis() - Config::READ_INTERVAL_MS;
}

void loop() {
  if (!sensorReady) {
    delay(100);
    return;
  }

  const uint32_t now = millis();
  if (now - lastReadingMs >= Config::READ_INTERVAL_MS) {
    lastReadingMs = now;
    printDistance();
  }
}
