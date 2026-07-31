# Fermentation Session Logger

Firmware ESP32 che avvia e chiude una sessione tramite un pulsante tra GPIO27
e GND. Ogni misura viene emessa come JSON Line e salvata dal PC in un file
rinominato automaticamente alla fine della sessione.

## Hardware

| Funzione | Collegamento ESP32 |
|---|---|
| SDA VL53L0X + SHT3x | GPIO21 |
| SCL VL53L0X + SHT3x | GPIO22 |
| Pulsante attivo basso | GPIO27 - GND |
| Alimentazione sensori | 3V3 - GND |

## Wi-Fi

Il file `include/Secrets.h` e' escluso da Git. Inserire localmente SSID e
password usando `include/Secrets.example.h` come riferimento.

## Funzionamento

- prima pressione: connessione Wi-Fi, sincronizzazione NTP e avvio sessione;
- lettura immediata, poi ogni `TIMEINTERVAL` secondi;
- seconda pressione: emissione dell'evento finale e chiusura del file sul PC;
- fuso `Europe/Berlin`, con passaggio automatico CET/CEST;
- ID hardware derivato dall'eFuse MAC dell'ESP32;
- distanza filtrata con mediana di 7 letture e correzione validata 50-175 mm;
- temperatura e umidita' SHT3x protette da controllo CRC.

`TIMEINTERVAL` e' definito in `include/Config.h` e vale inizialmente 10 secondi.

## Compilazione e caricamento

Aprire questa cartella direttamente in VS Code, poi usare PlatformIO Upload,
oppure:

```powershell
pio run --target upload --upload-port COM3
```

## Acquisizione e chiusura automatica

Dal terminale integrato aperto nella cartella di questo progetto:

```powershell
python ..\..\..\tools\fermentation_capture.py --port COM3
```

Non aprire contemporaneamente il Serial Monitor di PlatformIO: COM3 puo'
essere usata da un solo programma. I file completi vengono salvati in
`records/fermentations` con formato:

```text
AAAAMMGG_HHMMSS_HHMMSS_ESP32-ID.jsonl
```
