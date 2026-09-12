# FermentLab V2 — Piano operativo e delega
Data: 12 settembre 2026. Branch di coordinamento: `planning/fermentlab-v2`.
Stato: audit statico e pianificazione completati; implementazione, build e prove fisiche non eseguite in questa attività.

## Obiettivo
Tre vasi su un ESP32-S3-Zero; archivio completo su microSD; campionamento iniziale ogni 60 s; Wi-Fi ogni 15 cicli per invio a InfluxDB; sleep fra cicli. Intervalli configurabili. PC/NAS spento non interrompe la registrazione.

## Evidenze del repository
Ricognizione read-only delegata a due agenti, rispettivamente firmware e Analyzer. Nessun AGENTS.md nel tree esaminato. Revisione principale di TelemetryRecord.cpp e InfluxUploader.cpp.
- Base firmware: `experiments/esp32/fermentation-session-logger/`.
- Persistenza attuale: LittleFS per log/coda. Non va chiamata genericamente EEPROM.
- Presenti: Wi-Fi multi-rete, NTP, interfaccia web, configurazione sessioni, coda persistente, upload Influx con retry.
- Assenti dalla base esaminata: SD, RTC DS3231, deep sleep, TCA9548A e driver VL53L4CD.
- `src/TelemetryRecord.cpp`: measurement `fermentation_measurement`, tag `device_id`, `session_id`; timestamp in secondi. Campi sequence, elapsed_ms, temperature_dough_c, temperature_ambient_c, humidity_pct, distance_mm, dough_height_mm, volume_ml.
- `src/InfluxUploader.cpp`: sceglie NAS/PC secondo SSID e tenta destinazione alternativa; elimina segmento di coda dopo 2xx e cancellazione riuscita. Questo non garantisce che un database contenga tutta una sessione.
- Analyzer: `analysis/fermentlab_analyzer/fermentlab_analyzer/influx.py`, `processing.py`, `app.py`. Già presenti confronto sessioni, offset, filtraggio e derivate. Va conservata la distinzione dei vasi.
- `tools/fermentation_capture.py` registra JSONL seriale sul PC: non è un importer SD.
- Test Analyzer esistenti: `tests/test_influx.py`, `tests/test_processing.py`; non equivalgono a prove fisiche o test end-to-end.
Prima di ciascun task registrare il commit base: il branch main può avanzare rispetto al branch di pianificazione.

## Hardware: dichiarato, osservato, da verificare
| Componente | Evidenza disponibile | Verifica residua |
|---|---|---|
| ESP32-S3-Zero / S3FH4R2 | Foto commerciale, 4 MB flash e 2 MB PSRAM previsti | Variante reale, pinout, regolatore e budget 3,3 V con picchi SD/Wi-Fi |
| microSD SPI | Foto fronte/retro: 3V3, CS, MOSI, CLK, MISO, GND | Prova lettura/scrittura e consumi; non alimentare da GPIO |
| DS3231 + AT24C32 | Ordine mostrato, modulo tipo ZS-042 | Batteria e circuito di carica reali; EEPROM esterna non necessaria al progetto |
| ToF | Ordine VL53L4CD; altra foto marcata CJVL53L0XV2 | La foto non prova una consegna errata: identificare i moduli ricevuti e driver corretti |
| SHT31-DIS | Descrizione e foto commerciale SHT3X con frecce errate | Seguire serigrafia reale, controllare bias AD e pull-up; AL non usato |
| DS18B20 AZDelivery | Descrizione cavo 2 m, tre sonde necessarie | Numero posseduto, fili, indirizzi e stabilità del bus |
| TCA9548A | Pagina DAOKAI da 5 moduli | Richiesto uno; quantità ricevuta non deducibile dalla confezione mostrata; RST, A0–A2 e pull-up |
| Powerbank | Etichetta: 37 Wh, celle 10 Ah a 3,7 V, capacità dichiarata 6 Ah in uscita | Marca/modello precedentemente trascritti in modo non affidabile; auto-spegnimento e autonomia da misurare |
| Cavi | Sei conduttori, disposizione concordata | Lunghezza main→scatola, tre rami e lunghezza sonde effettivamente mantenuta |

### Decisioni elettriche da validare prima del cablaggio definitivo
- RTC sul bus principale; TCA dentro frigo; canali 0,1,2 ai vasi. Ogni canale porta ToF e SHT31.
- Selezionare un solo canale TCA alla volta per evitare conflitti fra sensori con stesso indirizzo. Il TCA è uno switch, non un estensore di distanza: verificare capacità, pull-up in parallelo e fronti con i cavi reali.
- DS18B20 a tre fili su DATA comune, un pull-up iniziale da 4,7 kΩ da validare. Tre rami lunghi non sono automaticamente affidabili.
- Sesto filo ancora riservato: non assegnare XSHUT comune senza verifica dei livelli elettrici dei breakout. Considerare anche il recupero del TCA con RST.
- Verificare pull-up di RST e livelli definiti su A0–A2. Non assumere che siano predisposti sulla scheda.
- Misurare cadute di tensione e picchi SD/Wi-Fi. Se si spegne una periferica, evitare retroalimentazione dai segnali.
- Supporto sensori: evitare condensa sulle finestre ToF/SHT31; calibrare nella geometria finale. La dichiarazione “impermeabile” delle sonde non documenta di per sé idoneità al contatto alimentare.
Fonti per il task elettrico: [datasheet TI TCA9548A](https://www.ti.com/lit/ds/symlink/tca9548a.pdf). Le foto dei breakout prevalgono sulle ipotesi di pinout, ma non sostituiscono schema e misure.

## Decisioni software
1. Conservare JSON Lines come archivio canonico. La precedente proposta CSV non è un requisito: CSV sarà un export opzionale. Cartella per sessione con session.json (configurazione versionata), samples.jsonl (eventi/campioni) e stato upload separato.
2. Estendere lo schema con schema_version, vessel_id stabile, stato dei sensori e qualità dell'ora. Conservare nomi e unità dei campi compatibili; calibrazione/baseline e metadati distinti per vaso.
3. Definire nel task D01 identità e semantica: una sessione raggruppa tre vasi, ciclo comune e una riga per vaso. Differenziare distanza grezza, distanza calibrata, altezza assoluta e crescita rispetto alla baseline. Non applicare coefficienti VL53L0X al VL53L4CD.
4. SD resta archivio completo anche dopo upload. Riutilizzare serializer/retry esistenti, sostituendo la semantica “cancella campioni consegnati” con cursore confermato separato.
5. Influx: aggiungere vessel_id ai tag e usare identità identiche in upload ESP32 e importer PC. Fissare precisione timestamp e politica per correzione dell'ora prima dell'implementazione. Non usare il momento di importazione come timestamp misura.
6. RTC esterno per tempo offline. elapsed_ms non può dipendere soltanto da millis() perché riparte dopo deep sleep. Ora non valida: conservare sequenza e qualità tempo senza inventare UTC; importazione dopo correzione esplicita.
7. Destinazione Influx fissata per sessione alla partenza dal profilo rete/configurazione. Se cambia destinazione, replica esplicita con cursore separato per database; niente fallback silenzioso che disperda la sessione fra NAS e PC.
8. Due modalità: configurazione/manutenzione con Wi-Fi e web UI attivi; acquisizione con finestre radio limitate. In deep sleep la web UI ESP32 non è raggiungibile: monitoraggio normale tramite Influx/Analyzer.
9. Timeout limitati e budget upload compatibile con prossima misura; gestione arretrato anche dopo session_end. Scritture SD controllate e recovery riga finale incompleta; niente promessa assoluta di sopravvivenza a guasto SD/alimentazione.
10. Avvio/arresto, resume dopo reset e pulsante durante sleep sono parte del controller di sessione, non accessori.

## Task delegabili
Modello predefinito per task circoscritti: Luna. Terra per integrazioni con più stati e I/O. Modello coordinatore per contratti, conflitti architetturali e review finale. Escalation dopo un tentativo motivato fallito, non cicli infiniti.

| ID | Task e perimetro | Modello | Dipende da | Criterio di accettazione |
|---|---|---|---|---|
| D01 | Contratto dati V2 e fixture: docs + esempi sintetici; specificare eventi, vasi, errori, tempi, destinazioni e mapping Influx | Coordinatore | Audit | Esempi normali/offline/ora non valida, mapping univoco e validazione concordata |
| H01 | Inventario verificabile, pin budget e schema elettrico preliminare; fonti dei moduli | Coordinatore | Foto esistenti | Tabella pin senza conflitti e lista precisa delle sole verifiche fisiche mancanti |
| F01 | Nuovo target experiments/esp32/fermentation-v2 con configurazione S3-Zero e acquisizione simulata | Luna | D01 | Build senza credenziali reali; legacy ancora compilabile; tre vasi simulati |
| F02 | Archivio SD e resume sessione, cursore robusto separato, nessuna cancellazione dei campioni confermati | Terra | D01,F01 | Reset/riga tronca/SD piena simulati; replay coerente; prova SD fisica distinta |
| F03 | Adapter SensorHub: TCA, tre SHT31 e DS18B20 associati per ROM; interfaccia ToF sostituibile | Luna | D01,F01,H01 | Errore di un sensore non blocca altri; mapping stabile verificato |
| F04 | Driver ToF selezionato e calibrazione per vaso | Luna | F03,identità ToF | Driver/build corretti e misure con distanze note nella geometria del vaso |
| F05 | RTC, controller sessione, deep sleep e modalità manutenzione | Terra | F02,F03,H01 | Resume senza nuova sessione/baseline; tempi validi; pulsante funzionante; test powerbank |
| F06 | Upload periodico e riuso InfluxUploader; destinazione esplicita e cursore | Terra | D01,F02,F05 | Offline/retry/conferma persa; dati SD intatti; nessuna misura saltata per invio lungo |
| P01 | Parser/validatore JSONL + importer PC con dry-run e mapping condiviso tramite fixture | Luna | D01 | File incompleto gestito; stessi punti di F06; seconda importazione non duplica |
| A01 | Analyzer: mantenere vessel_id in query/pivot, selezione e confronto dei vasi, latenza dati | Luna | D01 | Legacy leggibile; valori simultanei dei tre vasi mai mescolati |
| Q01 | Integrazione e test recupero, confronto SD/Influx, sessione 72 h | Coordinatore | F04,F05,F06,P01,A01 | Conteggi e identità concordi; guasti e autonomia documentati |
| Q02 | Documentazione finale uso, cablaggio e recupero | Luna | Q01 | Istruzioni coerenti con firmware realmente verificato |

Task subito eseguibili: D01 e H01. Dopo D01, P01 e A01 possono procedere in parallelo al firmware simulato. L'identità ToF blocca F04, non parser/importer/Analyzer o test SD. Il powerbank blocca la validazione sleep, non tutto lo sviluppo.
Milestone M1–M7 restano la vista sintetica; questa tabella definisce le dipendenze operative.

## Regole per delegare senza moltiplicare i token
- Un coordinatore, massimo due esecutori contemporanei nella fase iniziale.
- Ogni nuovo esecutore riceve il task e i soli riferimenti utili, senza l'intera cronologia o le pagine Amazon.
- Branch di task derivati dal commit di integrazione indicato: ad esempio v2/f02-sd-storage. Non modificare main direttamente.
- Un solo proprietario per file. Non parallelizzare due modifiche a main.cpp o allo schema dati.
- Nessun refactoring generale: riuso mirato e adapter. Non ricreare Analyzer o networking già presenti.
- Esecutore restituisce: diff/commit, file modificati, test effettivamente eseguiti, limiti e decisioni richieste. Non ripete il contesto.
- Coordinatore controlla contratti e casi limite; fa escalation soltanto se il task richiede una decisione nuova.
- Non stimare risparmi economici senza misure: meno contesto e meno rilavorazioni sono l'obiettivo, non una garanzia di costo.

## Brief da copiare per ogni task
Task: [ID, obiettivo].
Base: [repository, branch, commit verificato].
Leggi: [contratto dati + massimo i file pertinenti].
Puoi modificare: [perimetro preciso].
Input/output attesi: [interfaccia o fixture].
Accettazione: [prove concrete della riga task].
Vincoli: preserva compatibilità; nessuna credenziale; non modificare altri moduli; non cambiare schema autonomamente.
Consegna: diff/commit, esito dei test, blocchi residui. Se manca un dato hardware, usa adapter/mock esplicito e non dichiarare prova fisica riuscita.
