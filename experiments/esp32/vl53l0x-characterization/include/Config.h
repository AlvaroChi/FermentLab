#pragma once

#include <Arduino.h>

namespace Config {

#if defined(FERMENTLAB_BOARD_ESP32) && defined(FERMENTLAB_BOARD_S3_ZERO)
#error "Select only one FermentLab board profile"
#elif defined(FERMENTLAB_BOARD_ESP32)
constexpr char BOARD_PROFILE[] = "ESP32_CLASSIC";
constexpr uint8_t SDA_PIN = 21;
constexpr uint8_t SCL_PIN = 22;
constexpr uint32_t STARTUP_UPLOAD_GRACE_MS = 500;
#elif defined(FERMENTLAB_BOARD_S3_ZERO)
constexpr char BOARD_PROFILE[] = "WAVESHARE_ESP32_S3_ZERO";
constexpr uint8_t SDA_PIN = 1;
constexpr uint8_t SCL_PIN = 2;
constexpr uint32_t STARTUP_UPLOAD_GRACE_MS = 8000;
#else
#error "No FermentLab board profile selected by PlatformIO"
#endif

// Match the conservative bus configuration used by the final logger.
constexpr uint32_t I2C_FREQUENCY_HZ = 100000;
constexpr uint8_t SENSOR_I2C_ADDRESS = 0x29;

constexpr uint32_t SERIAL_BAUD = 115200;

constexpr size_t DEFAULT_SAMPLE_COUNT = 200;
constexpr size_t MIN_SAMPLE_COUNT = 10;
constexpr size_t MAX_SAMPLE_COUNT = 10000;

// Pausa aggiuntiva dopo ogni misura; si somma al timing budget.
constexpr uint32_t DEFAULT_SAMPLE_DELAY_MS = 20;
constexpr uint32_t MAX_SAMPLE_DELAY_MS = 5000;

constexpr uint32_t DEFAULT_TIMING_BUDGET_MS = 50;
constexpr uint32_t MIN_TIMING_BUDGET_MS = 20;
constexpr uint32_t MAX_TIMING_BUDGET_MS = 1000;

constexpr uint16_t SENSOR_TIMEOUT_MS = 500;
constexpr uint32_t TIMEOUT_MARGIN_MS = 250;
constexpr float SIGNAL_RATE_LIMIT_MCPS = 0.25f;

constexpr size_t WARMUP_READINGS = 5;

constexpr uint16_t MIN_VALID_RANGE_MM = 5;
constexpr uint16_t MAX_VALID_RANGE_MM = 2000;
constexpr double MAX_REAL_DISTANCE_MM = 2000.0;

// Codice grezzo ST "RANGECOMPLETE", prima della mappatura API.
constexpr uint8_t DEVICE_STATUS_RANGE_COMPLETE = 11;

}  // namespace Config
