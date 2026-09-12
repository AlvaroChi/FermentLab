# FermentLab V2 firmware skeleton

Target iniziale per ESP32-S3-Zero / ESP32-S3FH4R2. È separato dal logger V1 e
non contiene credenziali.

## Cosa fa

Al boot il simulatore emette sul Serial Monitor un ciclo JSONL ogni due secondi:
una riga `fermentlab.v2` per `vessel-1`, `vessel-2` e `vessel-3`, con
`sequence` comune e `vessel_sequence` per vaso. Il simulatore non usa RTC,
quindi emette `timestamp_utc_ms: null` e `time_quality: "invalid"`, come
richiesto dal contratto D01. Periodicamente simula un timeout DS18B20 del solo
vaso 2, con valore nullo e stato sensore `error`.

`SensorHub` è l'adapter sostituibile: F03 potrà implementare il SensorHub
fisico senza cambiare serializzazione o controller del ciclo.

Non sono ancora implementati SD, Wi-Fi/Influx, RTC, deep sleep, sensori fisici,
TCA, web UI o eventi di apertura/chiusura sessione.

## Build

Da questa cartella:

```sh
pio run -e esp32s3zero
```

Il target usa il board ID PlatformIO `esp32-s3-devkitm-1`, verificato nella
documentazione ufficiale PlatformIO, come profilo proxy: non è una dichiarazione
che la S3-Zero coincida elettricamente con la DevKitM-1. `board_upload.flash_size
= 4MB`, `ARDUINO_USB_MODE=1` e `ARDUINO_USB_CDC_ON_BOOT=1` configurano il
profilo iniziale per la flash dichiarata dell'S3FH4R2 e la seriale USB nativa.
Build, upload, variante fisica, flash e partizioni restano da verificare sulla
scheda ricevuta.

Per osservare JSONL:

```sh
pio device monitor -b 115200
```

Il formato prodotto è definito in
[`docs/fermentlab-v2-data-contract.md`](../../../docs/fermentlab-v2-data-contract.md).

## Hardware test T01: I2C scanner

Branch: `v2/t01-hardware-tests`. The simulator remains the default environment.
The scanner is built explicitly with:

```sh
pio run -e hardware_i2c_scan
pio run -e hardware_i2c_scan -t upload
pio device monitor -b 115200
```

Initial pin assignment for the ESP32-S3-Zero:

| Signal | GPIO |
|---|---:|
| SDA | 8 |
| SCL | 9 |

Start with one module at a time, powered at 3.3 V, and keep the RTC battery
holder empty during the first test. Expected addresses include DS3231 `0x68`,
AT24C32 `0x50`–`0x57`, VL53L4CD `0x29`, SHT31 `0x44` or `0x45`,
and TCA9548A `0x70` when A0–A2 are low. The scan only probes I2C addresses;
it does not write registers or alter device configuration.
