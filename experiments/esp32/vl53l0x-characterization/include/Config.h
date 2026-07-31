#pragma once

#include <Arduino.h>

namespace Config {

// Pin I2C predefiniti per un ESP32 DevKit/WROOM classico.
constexpr uint8_t SDA_PIN = 21;
constexpr uint8_t SCL_PIN = 22;
constexpr uint32_t I2C_FREQUENCY_HZ = 400000;

constexpr uint32_t SERIAL_BAUD = 115200;

// Modificare questo valore per scegliere ogni quanti secondi leggere il sensore.
constexpr uint32_t READ_INTERVAL_SECONDS = 2;
constexpr uint32_t READ_INTERVAL_MS = READ_INTERVAL_SECONDS * 1000UL;

constexpr uint16_t SENSOR_TIMEOUT_MS = 500;
constexpr uint32_t MEASUREMENT_TIMING_BUDGET_MS = 50;

}  // namespace Config
