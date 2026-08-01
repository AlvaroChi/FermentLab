#pragma once

#include <Arduino.h>

// Intervallo tra misure espresso in secondi.
#define TIMEINTERVAL 10

namespace Config {

constexpr uint8_t SDA_PIN = 21;
constexpr uint8_t SCL_PIN = 22;
constexpr uint8_t BUTTON_PIN = 4;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 50;
// 100 kHz is intentionally conservative for breadboards and longer jumpers.
constexpr uint32_t I2C_FREQUENCY_HZ = 100000;
constexpr uint16_t I2C_TRANSACTION_TIMEOUT_MS = 10;
constexpr uint32_t SERIAL_BAUD = 115200;

constexpr uint8_t VL53L0X_I2C_ADDRESS = 0x29;
constexpr uint8_t SHT3X_DEFAULT_I2C_ADDRESS = 0x44;
constexpr uint8_t SHT3X_ALTERNATE_I2C_ADDRESS = 0x45;
constexpr uint32_t SHT3X_MEASUREMENT_DELAY_MS = 20;

constexpr uint16_t SENSOR_TIMEOUT_MS = 500;
constexpr uint32_t SENSOR_RETRY_INTERVAL_MS = 15000;
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
constexpr uint32_t WIFI_RETRY_INITIAL_MS = 5000;
constexpr uint32_t WIFI_RETRY_MAX_MS = 60000;
constexpr uint32_t NTP_TIMEOUT_MS = 20000;
constexpr time_t MIN_VALID_EPOCH = 1704067200;  // 2024-01-01 UTC

// Persistent InfluxDB queue. A segment is deleted only after a successful
// HTTP response. Small segments bound RAM use and limit retransmission after
// a reset. Presence in this directory is the record's "not sent" state.
constexpr char TELEMETRY_QUEUE_DIRECTORY[] = "/influx-queue";
constexpr size_t TELEMETRY_SEGMENT_MAX_BYTES = 12 * 1024;
constexpr uint32_t INFLUX_HTTP_TIMEOUT_MS = 5000;
constexpr uint32_t INFLUX_RETRY_INITIAL_MS = 5000;
constexpr uint32_t INFLUX_RETRY_MAX_MS = 5 * 60 * 1000UL;
constexpr uint32_t INFLUX_SUCCESS_PAUSE_MS = 250;

// Recipe data is changed only from the local configuration page. Each file is
// replaced atomically so a power loss cannot leave the only copy truncated.
constexpr char RECIPE_CONFIG_DIRECTORY[] = "/recipe-config";
constexpr char FLOURS_FILE[] = "/recipe-config/flours.json";
constexpr char PRESETS_FILE[] = "/recipe-config/presets.json";
constexpr char SESSION_DRAFT_FILE[] = "/recipe-config/session-draft.json";
constexpr size_t CONFIG_DOCUMENT_MAX_BYTES = 32 * 1024;
constexpr size_t CONFIG_BACKUP_MAX_BYTES = 64 * 1024;

constexpr uint16_t WEB_SERVER_PORT = 80;
constexpr char WEB_HOSTNAME[] = "fermentlab";

// Set the vessel geometry when known. Zero keeps calculated height/volume
// absent instead of publishing invented values.
constexpr float SENSOR_TO_CONTAINER_BOTTOM_MM = 0.0f;
constexpr float CONTAINER_CROSS_SECTION_CM2 = 0.0f;

constexpr char TIMEZONE[] = "CET-1CEST,M3.5.0/2,M10.5.0/3";
constexpr char NTP_SERVER_1[] = "pool.ntp.org";
constexpr char NTP_SERVER_2[] = "time.cloudflare.com";

}  // namespace Config
