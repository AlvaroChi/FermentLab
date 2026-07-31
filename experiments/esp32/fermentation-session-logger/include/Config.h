#pragma once

#include <Arduino.h>

// Intervallo tra misure espresso in secondi.
#define TIMEINTERVAL 10

namespace Config {

constexpr uint8_t SDA_PIN = 21;
constexpr uint8_t SCL_PIN = 22;
constexpr uint8_t BUTTON_PIN = 4;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 50;
constexpr uint32_t I2C_FREQUENCY_HZ = 400000;
constexpr uint32_t SERIAL_BAUD = 115200;

constexpr uint8_t VL53L0X_I2C_ADDRESS = 0x29;
constexpr uint8_t SHT3X_DEFAULT_I2C_ADDRESS = 0x44;
constexpr uint8_t SHT3X_ALTERNATE_I2C_ADDRESS = 0x45;
constexpr uint32_t SHT3X_MEASUREMENT_DELAY_MS = 20;

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

// Taratura finale validata tra 50 e 175 mm.
constexpr float CALIBRATION_SLOPE = 0.99605958f;
constexpr float CALIBRATION_INTERCEPT_MM = 6.13040452f;
constexpr float CALIBRATED_MIN_MM = 50.0f;
constexpr float CALIBRATED_MAX_MM = 175.0f;

constexpr uint32_t READING_INTERVAL_MS = TIMEINTERVAL * 1000UL;
constexpr uint32_t WIFI_TIMEOUT_MS = 20000;
constexpr uint32_t NTP_TIMEOUT_MS = 20000;
constexpr time_t MIN_VALID_EPOCH = 1704067200;  // 2024-01-01 UTC

constexpr char TIMEZONE[] = "CET-1CEST,M3.5.0/2,M10.5.0/3";
constexpr char NTP_SERVER_1[] = "pool.ntp.org";
constexpr char NTP_SERVER_2[] = "time.cloudflare.com";

}  // namespace Config
