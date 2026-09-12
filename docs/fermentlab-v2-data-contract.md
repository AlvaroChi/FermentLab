# FermentLab V2 — Contratto dati

Stato: contratto D01. Questo documento definisce l'archivio SD canonico e il mapping
InfluxDB per V2. Non implementa il firmware.

## Compatibilità

I record V2 conservano i nomi e le unità V1: `sequence`, `elapsed_ms`,
`temperature_dough_c`, `temperature_ambient_c`, `humidity_pct`,
`distance_mm`, `dough_height_mm` e `volume_ml`. Influx conserva
`fermentation_measurement` e i tag `device_id` e `session_id`; V2 aggiunge
il tag `vessel_id`. Un consumer V1 che ignora tag/campi sconosciuti può quindi
leggere i punti V2, ma deve filtrare un vaso per non mescolare le tre serie.

JSONL è l'archivio completo e immutabile. Influx è una proiezione ripetibile:
l'avvenuto upload non autorizza mai la cancellazione o la riscrittura dei
campioni SD.

## Layout SD

Una sessione raggruppa esattamente tre vasi e ha un ID ASCII stabile
`[a-z0-9-]{1,48}`. Ogni vaso usa un ID stabile nella sessione
(`vessel-1`, `vessel-2`, `vessel-3` nelle fixture); non usare il numero del
canale TCA o un indice di array come identità persistente.

```text
/fermentlab-v2/sessions/<session_id>/
  session.json
  samples.jsonl
  upload/
    <destination_id>.cursor.json
```

- `session.json` è scritto all'avvio, una volta sola: configurazione congelata,
  tre vasi, calibrazioni/baseline per vaso, intervallo, destinazione Influx e
  metadati. Può essere completato con `ended_at_utc_ms` alla chiusura, senza
  cambiare la configurazione iniziale.
- `samples.jsonl` contiene un oggetto JSON UTF-8 per riga, con LF. Una riga
  incompleta alla fine dopo interruzione non è un record e viene ignorata in
  recovery; tutte le righe complete precedenti restano valide.
- `upload/` contiene solo stato derivato e ricostruibile. Non contiene token,
  URL con credenziali o campioni.

## Oggetti JSONL e tipi

Ogni riga ha:

| Campo | Tipo | Regola |
|---|---|---|
| `schema_version` | string | Sempre `fermentlab.v2`. |
| `event_type` | string enum | `session_start`, `sample`, `session_end`, `system_event`. |
| `event_id` | string | Identità stabile: `<session_id>:<event_type>:<ordinal>[:<vessel_id>]`. |
| `device_id`, `session_id` | string | ID stabili, non vuoti. |
| `timestamp_utc_ms` | integer o null | Millisecondi Unix UTC. `null` se l'ora non è affidabile. Mai stimare UTC al momento dell'import. |
| `time_quality` | string enum | `rtc_valid`, `ntp_synced`, `uncertain`, `invalid`. Solo i primi due sono esportabili a Influx senza riparazione esplicita. |
| `elapsed_ms` | integer ≥ 0 | Durata dalla partenza sessione, ricostruita dopo sleep/reset; non deriva solo da `millis()`. |

Un `sample` contiene inoltre `vessel_id`, `sequence` e
`vessel_sequence`, tutti interi senza segno. `sequence` è il numero di ciclo
comune ai tre vasi (e conserva la semantica del campo V1); ogni ciclo produce
al massimo una riga per vaso. `vessel_sequence` cresce solo per quel vaso.
La coppia `(session_id, vessel_id, sequence)` è unica. Il `event_id` è
l'identità dell'evento archivio; per un campione è
`<session_id>:sample:<sequence>:<vessel_id>`.

I numeri di misura sono JSON number finiti, non stringhe. Un valore non letto è
`null`, mai `0`, `NaN` o un valore precedente. Le unità sono:

| Campo | Tipo | Unità / significato |
|---|---|---|
| `temperature_dough_c` | number/null | °C DS18B20 |
| `temperature_ambient_c` | number/null | °C SHT31 |
| `humidity_pct` | number/null | percento relativo, 0–100 |
| `distance_mm` | number/null | distanza ToF grezza dal riferimento sensore |
| `distance_calibrated_mm` | number/null | distanza dopo la calibrazione del vaso |
| `dough_height_mm` | number/null | altezza assoluta dal fondo del vaso |
| `dough_growth_mm` | number/null | altezza meno baseline del vaso |
| `volume_ml` | number/null | volume calcolato; nullo se geometria non configurata |

`baseline_height_mm` e la calibrazione appartengono a `session.json`, per
vaso; non sostituiscono i valori grezzi in ogni campione. Non applicare una
calibrazione VL53L0X a hardware VL53L4CD.

### Sensori ed errori

Ogni campione ha `sensors`, oggetto con le chiavi `dough`, `ambient` e
`tof`. Ogni chiave contiene:

```json
{"state":"ok|missing|error|stale","error_code":null,"detail":null}
```

`state=ok` richiede i relativi valori presenti; `missing` indica hardware non
disponibile; `error` una lettura/CRC/timeout fallita; `stale` è consentito
solo quando viene esplicitamente riusata una misura marcata con la sua età (non
nelle fixture). `error_code` è un codice ASCII stabile, ad esempio
`DS18B20_TIMEOUT`, `SHT31_CRC`, `TOF_TIMEOUT`; `detail` è opzionale,
diagnostico e non usato come identità.

`session_start` e `session_end` sono eventi di audit e non campioni:
contengono `session_id`, `device_id`, `elapsed_ms`, tempo/qualità e
rispettivamente snapshot/configuration hash oppure motivo di chiusura. Un
`system_event` registra condizioni come `SD_WRITE_FAILED` senza fingere che
un campione sia stato salvato.

## Tempo, ordine e riparazione

`elapsed_ms` e i contatori stabiliscono l'ordine anche quando l'RTC è
invalidato. Non modificare `timestamp_utc_ms` dei record già salvati dopo una
sincronizzazione NTP. I record con `uncertain` o `invalid` restano su SD e
non vengono inviati a Influx. Un importer può esportarli solo dopo una
riparazione esplicita e tracciata che produca una nuova proiezione con
`time_repaired=true` e la regola/origine della correzione; l'archivio
originale non cambia.

Precisione V2: UTC al millisecondo. L'uploader traduce
`timestamp_utc_ms * 1_000_000` in timestamp Influx a nanosecondi. La
precisione richiesta alla write API è `ns`; non usare l'ora di importazione.

## Mapping InfluxDB

Per un `sample` con ora valida, scrivere un punto:

```text
fermentation_measurement,device_id=<...>,session_id=<...>,vessel_id=<...>,schema_version=fermentlab.v2 <fields> <timestamp_ns>
```

Tag: `device_id`, `session_id`, `vessel_id`, `schema_version`.
Campi legacy mantengono gli stessi nomi; `sequence`, `vessel_sequence` e
`elapsed_ms` sono integer Influx; le misure sono float. Valori JSON `null`
sono omessi dai campi numerici. Ogni stato sensore è esportato come string field
`sensor_<name>_state`; `error_code`, se non nullo, come
`sensor_<name>_error_code`. I nuovi campi geometrici sono float.

Gli eventi validi usano le measurement `session_start`, `session_end` e
`system_event`, con tag `device_id`, `session_id`, `schema_version`
(e `vessel_id` solo quando applicabile). `event_id`, `elapsed_ms`,
`time_quality`, `reason` e gli stati sono campi. I metadati strutturati,
ingredienti e calibrazioni restano in `session.json`; non vengono serializzati
come tag ad alta cardinalità.

L'identità del punto Influx è
`(measurement, device_id, session_id, vessel_id, timestamp_ns)`. Per i
campioni, `sequence` e il timestamp derivano dall'evento immutabile; un retry
scrive la stessa identità e non crea una nuova misura. Una collisione di due
eventi diversi su questa identità è un errore di contratto: l'importer deve
fermare il batch invece di sovrascrivere silenziosamente.

## Cursore upload

Ogni `<destination_id>.cursor.json` ha schema
`fermentlab.upload-cursor.v2`, `session_id`, `destination_id`,
`confirmed_event_id`, `confirmed_line_number`, `updated_at_utc_ms` e
`status` (`pending|complete|error`). Il cursore avanza solo dopo risposta
Influx 2xx per il batch contenente quella riga; dopo reset è lecito reinviare
dal precedente cursore. Una destinazione è fissata in `session.json` allo
start. Repliche deliberate usano un `destination_id` e cursore separati:
nessun fallback implicito NAS/PC.

## Regole di validazione

Il parser deve rifiutare JSON non valido, ID mancanti, `sequence` duplicata
per vaso, campi numerici non finiti e un sample senza `sensors`. Deve
accettare una sessione offline, errori di singoli sensori e timestamp nulli.
La compatibilità V1 rimane in lettura: record senza `schema_version` né
`vessel_id` sono interpretati come V1, vaso logico `legacy`, senza
riscrivere l'archivio.
