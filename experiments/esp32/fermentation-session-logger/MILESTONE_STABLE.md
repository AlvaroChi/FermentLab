# Milestone stabile ESP32-S3-Zero

**Stato: FUNZIONANTE E VERIFICATO**  
**Data di validazione: 9 agosto 2026**  
**Branch: `agent/fix-start-network-reset`**

Questa milestone e' il riferimento stabile per il logger FermentLab su
Waveshare ESP32-S3-Zero. Comprende i fix firmware dei commit:

- `d2e9cf9` - START non scrive piu' sulla coda LittleFS nel percorso critico;
- `9d8813c` - recupero sicuro della coda dopo scritture interrotte o perdita di
  alimentazione.

Il commit che contiene questo documento completa la baseline documentata. In
caso di regressione, confrontare prima il comportamento con questa milestone.

## Cosa e' stato verificato

La validazione e' stata eseguita su hardware reale, non soltanto tramite build:

- avvio e reset hardware senza boot loop (`reset_reason: POWERON`);
- nessun panic e `panic_safe_mode: false`;
- LittleFS, configurazione ricetta e coda persistente disponibili;
- configurazione dell'impasto conservata dopo il ripristino;
- START della sessione senza reset o `Network Error`;
- cinque misure consecutive con intervallo di 20 secondi;
- coda locale scaricata fino a zero;
- cinque punti ricevuti da InfluxDB con lo stesso `session_id`;
- STOP regolare della sessione;
- nuovo reset hardware con Wi-Fi, sensori, storage e coda nuovamente operativi.

Percorso validato:

```text
ESP32-S3-Zero -> Wi-Fi -> InfluxDB
```

Il collegamento USB al PC non e' necessario durante l'esperimento. La scheda
puo' essere alimentata da batteria o alimentatore USB; deve pero' avere
copertura della rete Wi-Fi configurata e l'endpoint InfluxDB selezionato deve
essere raggiungibile da quella rete.

## Comportamento stabile da preservare

- START crea lo stato della sessione in RAM e non accoda un evento
  `session_start` su LittleFS.
- Il primo checkpoint persistente viene scritto nel normale ciclo di misura,
  fuori dal percorso critico di START.
- Ogni misura completa viene accodata prima dell'invio a InfluxDB.
- Dopo un reset, la scansione recupera soltanto record completi terminati da
  newline.
- Un segmento incompleto non viene cancellato, riparato o riaperto durante il
  boot; le nuove scritture proseguono su un nuovo segmento.
- Un segmento viene eliminato solo dopo una risposta HTTP 2xx di InfluxDB.

Modifiche a questi punti richiedono una nuova prova su hardware reale con
reset, START, almeno cinque misure, verifica diretta in InfluxDB e STOP.

## Controllo rapido dopo il flash

Aprire `/api/status` e verificare almeno:

```text
panic_safe_mode: false
measurement_enabled: true
storage_ready: true
telemetry_queue_ready: true
recipe_config_ready: true
start_blocker: null
```

Durante una sessione, `session_measurements` deve aumentare. Se InfluxDB e'
raggiungibile, `queue_records` deve tornare a zero dopo gli invii. Una coda non
vuota non implica perdita di dati: indica arretrato locale ancora da inviare.

## Vincoli della milestone

La milestone certifica il profilo `esp32s3zero` e il flusso sopra descritto.
Non certifica copertura Wi-Fi dentro ogni frigorifero, autonomia di una
specifica batteria, disponibilita' del NAS o correttezza di credenziali e token
esterni al repository.
