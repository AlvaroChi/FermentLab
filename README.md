# FermentLab

Laboratorio aperto per raccogliere esperimenti, documentazione, formulazioni e
registrazioni legate ai processi di fermentazione e agli strumenti usati per
misurarli.

## Organizzazione

- `experiments/`: prove in evoluzione, con codice, note e piccoli dataset.
- `docs/`: procedure e conoscenze consolidate.
- `formulations/`: formule e ricette versionate.
- `records/`: registrazioni di prove e fermentazioni reali, ordinate per data.
- `tools/`: strumenti riutilizzabili tra più esperimenti.

Le cartelle vengono create quando compare il primo contenuto utile, evitando
segnaposto vuoti.

## Esperimenti attivi

### ESP32 + VL53L0X

Il primo esperimento verifica l'uso di un sensore di distanza VL53L0X con ESP32,
come base per una futura caratterizzazione e calibrazione:

[`experiments/esp32/vl53l0x-characterization/`](experiments/esp32/vl53l0x-characterization/)

Per compilare il firmware dalla radice del repository:

```powershell
pio run -d experiments/esp32/vl53l0x-characterization
```

Il repository non deve contenere credenziali Wi-Fi, token, chiavi private o
registrazioni con informazioni personali.
