#pragma once

#include <Arduino.h>

namespace Config {

constexpr uint8_t SDA_PIN = 21;
constexpr uint8_t SCL_PIN = 22;
constexpr uint8_t BUTTON_PIN = 4;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 50;
constexpr uint32_t I2C_FREQUENCY_HZ = 400000;
constexpr uint8_t SENSOR_I2C_ADDRESS = 0x29;
constexpr uint32_t SERIAL_BAUD = 115200;

constexpr uint16_t SENSOR_TIMEOUT_MS = 500;
constexpr uint32_t TIMEOUT_MARGIN_MS = 250;
constexpr uint32_t TIMING_BUDGET_MS = 50;
constexpr uint32_t SAMPLE_DELAY_MS = 20;
constexpr float SIGNAL_RATE_LIMIT_MCPS = 0.25f;

constexpr size_t WARMUP_READINGS = 5;
constexpr size_t FILTER_SAMPLE_COUNT = 7;
constexpr size_t MIN_VALID_SAMPLES = 5;
constexpr size_t MAX_SAMPLE_ATTEMPTS = 14;

constexpr uint16_t MIN_SENSOR_RANGE_MM = 5;
constexpr uint16_t MAX_SENSOR_RANGE_MM = 2000;
constexpr uint8_t DEVICE_STATUS_RANGE_COMPLETE = 11;

// Fit finale validato su 65 serie indipendenti nel range reale 50..175 mm.
// distanza_corretta = (misurata - intercetta) / pendenza
constexpr float CALIBRATION_SLOPE = 0.99605958f;
constexpr float CALIBRATION_INTERCEPT_MM = 6.13040452f;
constexpr float CALIBRATED_MIN_MM = 50.0f;
constexpr float CALIBRATED_MAX_MM = 175.0f;

constexpr uint32_t DEFAULT_READING_INTERVAL_SECONDS = 30;
constexpr uint32_t MIN_READING_INTERVAL_SECONDS = 1;
constexpr uint32_t MAX_READING_INTERVAL_SECONDS = 3600;

}  // namespace Config
