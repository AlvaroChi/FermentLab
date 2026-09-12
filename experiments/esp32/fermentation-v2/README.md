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
documentazione ufficiale PlatformIO; `board_upload.flash_size = 4MB` adatta il
profilo alla flash dichiarata dell'S3FH4R2. Prima di caricare verificare
fisicamente variante, flash e partizioni della scheda ricevuta.

Per osservare JSONL:

```sh
pio device monitor -b 115200
```

Il formato prodotto è definito in
[`docs/fermentlab-v2-data-contract.md`](../../../docs/fermentlab-v2-data-contract.md).
