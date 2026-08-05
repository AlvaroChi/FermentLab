#pragma once

#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// Optional fallback networks, tried automatically in order.
#define WIFI_SSID_2 "YOUR_SECOND_WIFI_SSID"
#define WIFI_PASSWORD_2 "YOUR_SECOND_WIFI_PASSWORD"
#define WIFI_SSID_3 "YOUR_PHONE_HOTSPOT_SSID"
#define WIFI_PASSWORD_3 "YOUR_PHONE_HOTSPOT_PASSWORD"
// #define WIFI_SSID_4 "YOUR_FOURTH_WIFI_SSID"
// #define WIFI_PASSWORD_4 "YOUR_FOURTH_WIFI_PASSWORD"
// #define WIFI_SSID_5 "YOUR_FIFTH_WIFI_SSID"
// #define WIFI_PASSWORD_5 "YOUR_FIFTH_WIFI_PASSWORD"

// InfluxDB profile selection (choose one)
#define INFLUX_PROFILE_NAS
// #define INFLUX_PROFILE_PC

// NAS profile
#define INFLUX_NAS_URL "http://192.168.x.x:8086"
#define INFLUX_NAS_TOKEN "YOUR_NAS_INFLUX_TOKEN"
#define INFLUX_NAS_ORG "FermentLab"
#define INFLUX_NAS_BUCKET "fermentlab"

// PC profile (ESP32 must use LAN-reachable address, not localhost)
#define INFLUX_PC_URL "http://192.168.x.x:8086"
#define INFLUX_PC_TOKEN "YOUR_PC_INFLUX_TOKEN"
#define INFLUX_PC_ORG "FermentLab"
#define INFLUX_PC_BUCKET "fermentlab"

#if defined(INFLUX_PROFILE_NAS) && defined(INFLUX_PROFILE_PC)
#error "Select only one Influx profile: INFLUX_PROFILE_NAS or INFLUX_PROFILE_PC"
#elif defined(INFLUX_PROFILE_NAS)
#define INFLUX_URL    INFLUX_NAS_URL
#define INFLUX_TOKEN  INFLUX_NAS_TOKEN
#define INFLUX_ORG    INFLUX_NAS_ORG
#define INFLUX_BUCKET INFLUX_NAS_BUCKET
#elif defined(INFLUX_PROFILE_PC)
#define INFLUX_URL    INFLUX_PC_URL
#define INFLUX_TOKEN  INFLUX_PC_TOKEN
#define INFLUX_ORG    INFLUX_PC_ORG
#define INFLUX_BUCKET INFLUX_PC_BUCKET
#else
#error "Define one active Influx profile: INFLUX_PROFILE_NAS or INFLUX_PROFILE_PC"
#endif

// Backward compatibility aliases
#define INFLUXDB_URL    INFLUX_URL
#define INFLUXDB_TOKEN  INFLUX_TOKEN
#define INFLUXDB_ORG    INFLUX_ORG
#define INFLUXDB_BUCKET INFLUX_BUCKET
