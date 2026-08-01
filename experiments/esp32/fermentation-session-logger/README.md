# Fermentation Session Logger

Firmware ESP32 che avvia e chiude sessioni dall'interfaccia web locale. Ogni
misura viene salvata localmente su LittleFS prima di essere inviata
a InfluxDB 2.x; indisponibilita' temporanee di Wi-Fi, NAS o InfluxDB non causano
la perdita dell'arretrato.

## Hardware

| Funzione | Collegamento ESP32 |
|---|---|
| SDA VL53L0X + SHT3x | GPIO21 |
| SCL VL53L0X + SHT3x | GPIO22 |
| Alimentazione sensori | 3V3 - GND |

GPIO4 non viene configurato dal firmware e resta libero, senza pull-up interno.

## Wi-Fi e InfluxDB

Creare il file locale escluso da Git:

```powershell
Copy-Item include/secrets.example.h include/secrets.h
```

Compilare quindi `include/secrets.h` con SSID, password, URL del NAS, token,
organization e bucket. La configurazione attesa e':

```cpp
#define INFLUXDB_URL "http://<IP_NAS>:8086"
#define INFLUXDB_ORG "FermentLab"
#define INFLUXDB_BUCKET "fermentlab"
```

Il token non viene stampato nei log. `include/secrets.h` e' ignorato da Git;
nel repository rimane soltanto `include/secrets.example.h` con placeholder.

## Coda persistente e recupero

- le misure Influx Line Protocol vengono accodate in segmenti append-only in
  `/influx-queue` su LittleFS;
- ogni record viene terminato e sincronizzato prima che possa essere inviato;
- la presenza nel segmento equivale allo stato `not sent`;
- il segmento piu' vecchio viene inviato a `/api/v2/write` e cancellato solo
  dopo una risposta HTTP 2xx;
- timeout e backoff esponenziale evitano retry serrati;
- dopo reboot vengono recuperate tutte le righe complete; un'eventuale coda
  incompleta causata da un'interruzione di alimentazione non viene estesa;
- un retry dopo un reset puo' reinviare un batch gia' accettato: stessi tag e
  timestamp rendono la scrittura idempotente in InfluxDB.

La misura `fermentation_measurement` usa i tag `device_id` e `session_id` e
campi per sequenza, tempo trascorso, temperature, umidita', distanza, altezza e
volume. InfluxDB usa timestamp con precisione in secondi.

## Funzionamento

- connessione Wi-Fi, sincronizzazione NTP e recupero coda avvengono in
  background con una macchina a stati non bloccante;
- **START** dalla dashboard: avvio sessione quando l'orologio e' gia' sincronizzato;
- lettura immediata, poi ogni `TIMEINTERVAL` secondi;
- **STOP** dalla dashboard: chiusura e rinomina del file nella memoria dell'ESP32;
- dopo la chiusura stampa automaticamente l'intero JSONL nel Serial Monitor;
- fuso `Europe/Rome`, con passaggio automatico CET/CEST;
- ID hardware derivato dall'eFuse MAC dell'ESP32;
- distanza filtrata con mediana di 7 letture e correzione validata 50-175 mm;
- temperatura e umidita' SHT3x protette da controllo CRC.

Il sensore SHT3x attuale popola la temperatura ambiente. Il campo temperatura
impasto e' gia' previsto nello schema ma resta nullo finche' non viene collegato
un sensore dedicato. Per calcolare altezza e volume impostare in
`include/Config.h` `SENSOR_TO_CONTAINER_BOTTOM_MM` e
`CONTAINER_CROSS_SECTION_CM2`; lasciati a zero, i due campi restano nulli.

`TIMEINTERVAL` e' definito in `include/Config.h` e vale inizialmente 10 secondi.

## Interfaccia web locale

Quando il Wi-Fi e' connesso, l'ESP32 espone una pagina di controllo sulla rete
locale:

```text
http://fermentlab.local
```

Se il telefono o il router non risolvono mDNS, usare l'indirizzo IP mostrato
nel log `web_ready` oppure nella lista client del router, ad esempio
`http://192.168.68.x`.

La pagina offre:

- **Test lettura**: acquisisce un campione SHT3x/VL53L0X e lo mostra nella
  pagina senza salvarlo su LittleFS e senza inviarlo a InfluxDB;
- **START/STOP**: avvia e termina la sessione direttamente dalla dashboard;
- stato sessione, timestamp, IP, segnale Wi-Fi e uptime;
- intervallo previsto, letture effettuate, tempo alla prossima lettura e ultima
  misura;
- numero reale di letture in coda, segmenti e byte della coda InfluxDB
  persistente.

### Impasto, farine e preset

La pagina separata `http://fermentlab.local/config` (raggiungibile anche dal
pulsante **Impasto e farine** nella dashboard) permette di gestire senza editor
JSON:

- il catalogo personale delle farine, con marca, nome, tipo, proteine, W, P/L,
  note e fonte;
- preset riutilizzabili con una o piu' farine, percentuali della miscela,
  idratazione, sale, lievito e autolisi;
- la configurazione del prossimo impasto, anche partendo da un preset;
- esportazione e importazione di un backup JSON completo.

Al primo avvio vengono aggiunte Caputo Pizzeria e Caputo Nuvola con i dati
delle schede ufficiali. Italiamo Nuvola viene aggiunta con marca e nome, ma i
dati tecnici restano volutamente vuoti finche' non vengono copiati
dall'etichetta della confezione. I due preset inclusi sono esempi modificabili,
non ricette universali.

I documenti sono salvati in `/recipe-config` su LittleFS. Ogni modifica usa un
file temporaneo e una copia di recupero; catalogo e preset non vengono riscritti
durante le normali misurazioni. Gli ID e i riferimenti tra farine, preset e
impasto vengono validati prima della sostituzione. Durante una sessione attiva
l'interfaccia e le API rifiutano qualsiasi modifica.

Allo START la prima riga del JSONL include `recipe`: e' una fotografia della
configurazione corrente, comprese le schede delle farine e i grammi calcolati.
Modificare in seguito una farina o un preset non cambia quindi le sessioni gia'
registrate.

La pagina mostra separatamente lo stato di VL53L0X, SHT3x, LittleFS, coda e
NTP. Se un sensore non e' disponibile, START restituisce il motivo preciso e il
firmware tenta automaticamente una nuova inizializzazione ogni 15 secondi,
senza richiedere un riavvio.

L'interfaccia non richiede Internet, ma telefono ed ESP32 devono essere sulla
stessa rete locale. Non e' presente autenticazione: non pubblicare la porta 80
del dispositivo su Internet e usare una rete Wi-Fi considerata affidabile.

## Alimentazione senza PC

L'ESP32 puo' funzionare dalla porta USB con un normale alimentatore da telefono
5 V / 2 A. I 2 A indicano la corrente massima disponibile: la scheda assorbe
solo quella necessaria. Usare un cavo USB affidabile e verificare dalla pagina
che uptime, letture e invii continuino senza riavvii. Il buffer LittleFS
mantiene l'arretrato anche se durante la prova Wi-Fi o NAS non sono disponibili.

## Compilazione e caricamento

Aprire questa cartella direttamente in VS Code, poi usare PlatformIO Upload,
oppure:

```powershell
pio run --target upload --upload-port COM3
```

## Serial Monitor

Il normale Serial Monitor di PlatformIO mostra le misure durante la sessione.
Alla chiusura della sessione stampa `file_saved`, seguito dal contenuto completo del
file tra `file_dump_start` e `file_dump_end`.

## Acquisizione opzionale sul PC

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
