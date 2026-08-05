#pragma once

#include <Arduino.h>

namespace Config {

#if defined(FERMENTLAB_BOARD_ESP32) && \
    defined(FERMENTLAB_BOARD_S3_ZERO)
#error "Select only one FermentLab board profile"
#elif defined(FERMENTLAB_BOARD_ESP32)
constexpr char BOARD_PROFILE[] = "ESP32_CLASSIC";
constexpr uint8_t SDA_PIN = 21;
constexpr uint8_t SCL_PIN = 22;
constexpr uint8_t DS18B20_PIN = 27;
#if defined(FERMENTLAB_STATUS_LED_PIN)
constexpr int8_t STATUS_LED_PIN = FERMENTLAB_STATUS_LED_PIN;
#else
constexpr int8_t STATUS_LED_PIN = 2;
#endif
#elif defined(FERMENTLAB_BOARD_S3_ZERO)
constexpr char BOARD_PROFILE[] = "WAVESHARE_ESP32_S3_ZERO";
constexpr uint8_t SDA_PIN = 1;
constexpr uint8_t SCL_PIN = 2;
constexpr uint8_t DS18B20_PIN = 4;
#if defined(FERMENTLAB_STATUS_LED_PIN)
constexpr int8_t STATUS_LED_PIN = FERMENTLAB_STATUS_LED_PIN;
#else
constexpr int8_t STATUS_LED_PIN = 21;
#endif
#else
#error "No FermentLab board profile selected by PlatformIO"
#endif

#if defined(FERMENTLAB_STATUS_LED_ACTIVE_HIGH)
constexpr bool STATUS_LED_ACTIVE_HIGH = FERMENTLAB_STATUS_LED_ACTIVE_HIGH != 0;
#else
constexpr bool STATUS_LED_ACTIVE_HIGH = true;
#endif

#if defined(FERMENTLAB_STATUS_LED_IS_NEOPIXEL)
constexpr bool STATUS_LED_IS_NEOPIXEL =
    FERMENTLAB_STATUS_LED_IS_NEOPIXEL != 0;
#elif defined(FERMENTLAB_BOARD_S3_ZERO)
constexpr bool STATUS_LED_IS_NEOPIXEL = true;
#else
constexpr bool STATUS_LED_IS_NEOPIXEL = false;
#endif

static_assert(SDA_PIN != SCL_PIN && SDA_PIN != DS18B20_PIN &&
                  SCL_PIN != DS18B20_PIN,
              "Sensor pins must be unique");
static_assert(STATUS_LED_PIN < 0 ||
                  (STATUS_LED_PIN != static_cast<int8_t>(SDA_PIN) &&
                   STATUS_LED_PIN != static_cast<int8_t>(SCL_PIN) &&
                   STATUS_LED_PIN != static_cast<int8_t>(DS18B20_PIN)),
              "Status LED pin conflicts with sensor pins");

constexpr uint8_t DS18B20_RESOLUTION_BITS = 12;
constexpr uint32_t DS18B20_CONVERSION_MS = 750;
// 100 kHz is intentionally conservative for breadboards and longer jumpers.
constexpr uint32_t I2C_FREQUENCY_HZ = 100000;
constexpr uint16_t I2C_TRANSACTION_TIMEOUT_MS = 10;
constexpr uint32_t SERIAL_BAUD = 115200;
#if defined(FERMENTLAB_BOARD_S3_ZERO)
constexpr uint32_t STARTUP_UPLOAD_GRACE_MS = 8000;
#else
constexpr uint32_t STARTUP_UPLOAD_GRACE_MS = 500;
#endif

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

// Final-case calibration collected on 2026-08-04. Raw medians are mapped to
// distances measured from the smooth external datum of the enclosure. Linear
// interpolation preserves the measured close-range non-linearity caused by
// the recessed sensor and enclosure aperture.
struct DistanceCalibrationPoint {
  float rawMedianMm;
  float externalDistanceMm;
};

constexpr DistanceCalibrationPoint DISTANCE_CALIBRATION[] = {
    {73.000f, 10.0f},  {75.833f, 15.0f},  {79.000f, 20.0f},
    {81.333f, 25.0f},  {87.333f, 30.0f},  {94.000f, 35.0f},
    {98.200f, 40.0f},  {104.500f, 45.0f}, {109.500f, 50.0f},
    {114.500f, 55.0f}, {119.500f, 60.0f}, {124.000f, 65.0f},
    {129.667f, 70.0f}, {134.000f, 75.0f}, {138.000f, 80.0f},
    {143.000f, 85.0f}, {148.000f, 90.0f}, {152.000f, 95.0f},
    {157.333f, 100.0f}, {161.000f, 105.0f}, {166.000f, 110.0f},
    {171.000f, 115.0f}, {176.000f, 120.0f}, {181.000f, 125.0f},
    {184.500f, 130.0f}, {194.500f, 140.0f}, {200.000f, 145.0f},
    {203.333f, 150.0f}, {209.000f, 155.0f}, {213.500f, 160.0f},
};
constexpr size_t DISTANCE_CALIBRATION_COUNT =
    sizeof(DISTANCE_CALIBRATION) / sizeof(DISTANCE_CALIBRATION[0]);
constexpr float CALIBRATED_MIN_MM = 10.0f;
constexpr float CALIBRATED_MAX_MM = 148.0f;

// The interval is selected in the session draft and then frozen at START.
// Existing configurations without the field continue to use the default.
constexpr uint32_t DEFAULT_READING_INTERVAL_S = 10;
constexpr uint32_t MIN_READING_INTERVAL_S = 5;
constexpr uint32_t MAX_READING_INTERVAL_S = 24 * 60 * 60;
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
constexpr uint32_t WEB_SERVER_RETRY_INTERVAL_MS = 1000;

// Physical distance from the enclosure datum to the inner vessel bottom.
// The optical bottom reading is deliberately not used because the curved or
// reflective empty vessel produced position-dependent results.
constexpr float SENSOR_TO_CONTAINER_BOTTOM_MM = 148.0f;
constexpr float CONTAINER_CROSS_SECTION_CM2 = 0.0f;

constexpr char TIMEZONE[] = "CET-1CEST,M3.5.0/2,M10.5.0/3";
constexpr char NTP_SERVER_1[] = "pool.ntp.org";
constexpr char NTP_SERVER_2[] = "time.cloudflare.com";

}  // namespace Config
