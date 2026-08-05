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

// SSID considered as "home" for Influx preference. If connected to this
// network, NAS is tried first; otherwise PC is tried first.
#define INFLUX_HOME_WIFI_SSID WIFI_SSID

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

// Runtime logic in firmware:
// - if current SSID == INFLUX_HOME_WIFI_SSID: try NAS, then fallback to PC
// - otherwise: try PC, then fallback to NAS
