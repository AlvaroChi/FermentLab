# Fermentation Height Monitor

Firmware operativo ESP32 + VL53L0X + SHT3x per seguire la crescita di un
impasto e registrare temperatura e umidita' dell'ambiente.

## Collegamenti SHT3x

Il modulo condivide il bus I2C del VL53L0X:

| SHT3x | ESP32 DevKit V1 |
|---|---|
| `VCC` | `3V3` |
| `GND` | `GND` |
| `SDA` | `GPIO21` |
| `SCL` | `GPIO22` |

Il firmware cerca automaticamente gli indirizzi `0x44` e `0x45`, effettua
misure single-shot ad alta ripetibilita' e scarta i dati che non superano il
controllo CRC.

## Campo di utilizzo

La calibrazione è stata validata esclusivamente tra 50 e 175 mm:

```text
distanza_corretta = (distanza_filtrata - 6.13040452) / 0.99605958
```

Nel test indipendente la correzione ha ottenuto MAE 1,02 mm, RMSE 1,17 mm ed
errore massimo 1,90 mm. Fuori dal range validato il firmware stampa `nan` per
distanza corretta e crescita.

## Funzionamento

- configura un pulsante tra GPIO4 e GND con pull-up interno;
- resta in attesa all'accensione;
- una pressione avvia una nuova sessione e azzera la baseline;
- una seconda pressione ferma l'acquisizione;
- legge temperatura e umidita' ambiente dall'SHT3x;
- acquisisce sette letture valide;
- usa la mediana per respingere valori isolati;
- applica la calibrazione;
- usa la prima misura valida come baseline automatica;
- calcola `crescita = baseline - distanza_attuale`;
- stampa una riga CSV ogni 30 secondi.

Un valore di crescita positivo indica che la superficie si è avvicinata al
sensore. Un riavvio dell'ESP32 azzera la baseline.

## Compilazione e caricamento

```powershell
cd experiments\esp32\fermentation-height-monitor
pio run
pio run --target upload --upload-port COM3
```

## Registrazione

Dalla cartella del progetto, con il monitor PlatformIO chiuso:

```powershell
python ..\..\..\tools\serial_capture.py --port COM3 --prefix fermentation
```

Il file viene creato nella cartella locale `logs`. Scrivere `fine` per chiudere
e forzare il salvataggio finale.

## Comandi seriali

| Comando | Effetto |
|---|---|
| `start` | Avvia una sessione come la pressione del pulsante |
| `stop` | Ferma la sessione come la pressione del pulsante |
| `read` | Lettura immediata anche quando la sessione e' ferma |
| `baseline` | Usa l'ultima distanza valida come nuovo zero |
| `clear` | Cancella lo zero; la prossima misura valida diventa baseline |
| `interval=30` | Imposta i secondi tra le letture |
| `status` | Mostra configurazione e baseline |
| `header` | Ristampa l'intestazione CSV |
| `retry` | Ritenta l'inizializzazione del sensore |
| `help` | Mostra i comandi |

## Formato CSV

```text
tempo_ms,temperatura_ambiente_c,umidita_ambiente_pct,n_valide,n_tentativi,raw_min_mm,raw_media_mm,raw_mediana_mm,raw_max_mm,distanza_corretta_mm,crescita_mm,stato_distanza,stato_ambiente
```

Prima della prova sull'impasto verificare il montaggio con un bersaglio rigido e
controllare che lo stato sia `OK` o `OK_BASELINE_INIZIALE`.
