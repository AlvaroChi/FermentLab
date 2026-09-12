# FermentLab V2 — Milestone

Stato: pianificazione. Piano operativo e task delegabili: [fermentlab-v2-execution-plan.md](fermentlab-v2-execution-plan.md). Le caselle indicano lavoro da implementare e verificare, non funzionalità già presenti.

## Obiettivo concordato

Un ESP32 acquisisce tre vasi, registra tutte le letture su microSD e accende il Wi-Fi soltanto ogni X campionamenti per inviare l'arretrato a InfluxDB. Tra i campionamenti entra in deep sleep. La registrazione continua anche con PC, NAS o rete non disponibili.

## Architettura hardware

- Fuori frigo: **powerbank da etichetta fornita (marca/modello da rileggere, precedente trascrizione non affidabile) (celle 10.000 mAh, 3,7 V / 37 Wh; capacità nominale in uscita 6.000 mAh; USB 5 V)**, **ESP32-S3-Zero con ESP32-S3FH4R2 (USB-C, 4 MB flash e 2 MB PSRAM integrati)**, **modulo microSD SPI diretto a 3,3 V (circa 18 × 20 mm; pin 3V3, CS, MOSI, CLK, MISO, GND)** e **un solo RTC DS3231 con EEPROM AT24C32** e batteria tampone. Ordine mostrato: 3 moduli RTC; richiesto 1, ricezione da confermare.
- Un cavo a 6 conduttori raggiunge la scatola di derivazione nel frigo.
- Un solo **TCA9548A DAOKAI (marca mostrata nella pagina)** nella scatola, alimentato a 3,3 V, con un canale I2C dedicato a ogni vaso. Pagina relativa a confezione da 5: quantità fisicamente disponibile da confermare; richiesto 1 modulo. Ingresso: VIN, GND, SDA, SCL; `RST` e `A0–A2` da definire nello schema. Uscite: coppie `SDn/SCn` dei canali 0–7.
- Tre cavi a 6 conduttori dalla scatola ai rispettivi vasi.
- Ogni vaso: **1× ToF per vaso**. L'ordine dichiara 3× VL53L4CD, ma l'immagine del pinout mostra una scheda marcata `CJVL53L0XV2` (lettura della foto), apparentemente VL53L0X: modello fisico da verificare all'arrivo prima di scegliere driver e libreria, **SHT31-DIS/SHT3X temperatura-umidità, modulo viola APKLVSR dichiarato 2,4–5,5 V** (alimentazione prevista a 3,3 V; pin serigrafati VIN, GND, SCL, SDA, AL, AD; AL non usato; bias AD da verificare), e **sonda AZDelivery DS18B20 impermeabile in acciaio con cavo da 2 m**.
- Conduttori: alimentazione sensori, GND, SDA, SCL, DATA OneWire e riserva. Tensioni e pin da validare sui moduli effettivi.
- Alimentazione e GND distribuiti ai tre vasi; DATA bypassa il TCA e collega le tre sonde sullo stesso bus, distinguendole per indirizzo.

## M1 — Verificare base software e hardware

- [ ] Leggere codice e documentazione di `experiments/esp32/fermentation-session-logger/`, monitor altezza e Analyzer.
- [ ] Verificare la marcatura dei tre ToF ricevuti: VL53L4CD richiesto contro `CJVL53L0XV2` mostrato nell'immagine commerciale. Non implementare il driver definitivo finché l'identità non è confermata.
- [ ] Se la scheda reale coincide con l'immagine: pin VCC, GND, SCL, SDA, GPIO1 e XSHUT; per la misura bastano i primi quattro. Tenere il sesto conduttore in riserva: prima di assegnarlo a XSHUT verificare schema del breakout, livelli e pull-up. GPIO1 previsto non usato.
- [ ] Documentare la persistenza effettiva leggendo PersistentQueue e SessionConfigStore; distinguere archivio, coda di invio e configurazione.
- [ ] Confermare colori/funzioni dei tre fili delle sonde DS18B20 e lunghezze dei cavi di collegamento; definire pin e alimentazione.
- [ ] Verificare sul modulo ricevuto il pinout SHT31: nell'immagine commerciale la serigrafia mostra VIN, GND, SCL e SDA e contraddice le frecce. AL non usato; verificare il bias AD prima di lasciarlo scollegato.
- [ ] Alimentare le DS18B20 in modalità normale a tre fili e 3,3 V; prevedere una sola resistenza pull-up da 4,7 kΩ tra DATA e 3,3 V per l'intero bus OneWire, da validare con le lunghezze reali.
- [ ] Provare se il powerbank fornito mantiene attiva l'uscita USB durante il deep sleep: l'etichetta non dichiara una modalità a basso assorbimento o uscita permanente.
- [ ] Verificare il pinout effettivo della scheda ESP32-S3-Zero e riservare i GPIO necessari per SPI, I2C, OneWire, pulsante, LED e risveglio da deep sleep.
- [ ] Assegnare i GPIO SPI del modulo microSD 3,3 V e il pin CS, evitando conflitti con I2C, OneWire, pulsante e LED.
- [ ] Verificare assorbimento reale della microSD attiva e a riposo; se necessario prevedere un interruttore di alimentazione a MOSFET/load switch, senza alimentarla direttamente da un GPIO.
- [ ] Verificare sui moduli RTC DS3231/AT24C32 il tipo di batteria previsto e l'eventuale circuito di ricarica prima di inserire una CR2032 non ricaricabile.
- [ ] Verificare che il powerbank non si spenga durante il deep sleep e misurare il consumo dell'intero sistema, inclusi SD e sensori.
- [ ] Definire compatibilità del formato dati con Analyzer e InfluxDB esistenti.

Completata quando: stato attuale, componenti, pin e vincoli sono documentati; compilazione di riferimento riuscita. La compatibilità powerbank è un requisito per M4.

## M2 — Acquisizione dei tre vasi

- [ ] Gestire TCA9548A e ToF/SHT31D su tre canali distinti.
- [ ] Assegnare tre canali fisici del TCA ai vasi e documentare per ciascuno `SDA = SDn` e `SCL = SCn`; indirizzo del TCA previsto `0x70` con A0–A2 bassi, da verificare sulla scheda reale.
- [ ] Associare stabilmente gli indirizzi DS18B20 ai vasi 1–3.
- [ ] Conservare calibrazione e distanza iniziale separate per vaso.
- [ ] Salvare distanza ToF originale e altezza calcolata, temperatura impasto, temperatura e umidità ambiente.
- [ ] Rappresentare letture fallite come mancanti con stato errore; non sostituirle con zeri plausibili.

Completata quando: tutti i valori sono attribuiti al vaso corretto e un sensore scollegato non blocca gli altri.

## M3 — SD come archivio principale e gestione sessioni

- [ ] Definire schema versionato: cartella per sessione, `session.json` con metadati e `samples.jsonl` con letture (decisione V2: continuare con JSON Lines; CSV come export opzionale).
- [ ] Includere ID sessione, ID vaso, numero campione, timestamp UTC, tempo trascorso, misure e stati errore.
- [ ] Registrare ingredienti, calibrazioni e intervallo di campionamento nei metadati.
- [ ] Scrivere ogni campionamento, svuotare i buffer e chiudere il file prima del sonno.
- [ ] Recuperare sessione e ultimo campione valido dopo reset; gestire un'eventuale ultima riga incompleta.
- [ ] Gestire SD assente, piena o guasta con segnalazione esplicita, senza dichiarare dati salvati.
- [ ] Apertura/chiusura sessione tramite pulsante e LED di conferma per estrazione sicura SD.
- [ ] Eliminare le scritture periodiche delle misure nella flash interna; mantenere in NVS solo configurazioni persistenti quando cambiano.

Completata quando: una sessione resta leggibile dopo riavvio e un'interruzione durante la scrittura non rende inutilizzabili i campioni precedenti. Flush e chiusura non costituiscono garanzia assoluta contro guasti di alimentazione della SD.

## M4 — RTC e deep sleep

- [ ] Usare RTC esterno per data/ora anche senza rete; riconoscere orologio non valido o batteria persa.
- [ ] Prevedere sincronizzazione NTP in una finestra Wi-Fi, senza alterare i timestamp delle letture già salvate.
- [ ] Risveglio, lettura, salvataggio SD, eventuale invio, spegnimento Wi-Fi e deep sleep.
- [ ] Intervallo configurabile: proposta iniziale 60 secondi tra campionamenti, tenendo conto del tempo attivo.
- [ ] Ripristinare periferiche dopo ogni risveglio; gestire pulsante di arresto anche durante sleep.
- [ ] Usare memoria RTC interna per contatori temporanei, recuperando lo stato necessario da SD dopo perdita alimentazione.
- [ ] Verificare consumo e autonomia reali; valutare spegnimento periferiche solo se supportato dall'hardware.

Completata quando: campionamento e sessione sopravvivono ai cicli di sleep, l'ora rimane coerente e il powerbank mantiene l'alimentazione.

## M5 — Wi-Fi periodico e sincronizzazione InfluxDB

- [ ] Attivare Wi-Fi ogni X campionamenti; proposta iniziale X=15, configurabile.
- [ ] Salvare prima su SD e inviare direttamente a InfluxDB sul NAS o PC, senza richiedere Analyzer aperto.
- [ ] Configurare reti e destinazioni senza credenziali nel repository; verificare la logica NAS/PC già esistente prima di sostituirla.
- [ ] Leggere da SD tutti i dati non confermati e inviarli in blocchi con consumo RAM limitato.
- [ ] Usare timeout e budget di tempo per connessione/invio; riprendere l'arretrato nelle finestre successive senza compromettere il campionamento.
- [ ] Conservare su SD un segnalibro persistente, recuperabile in caso di scrittura interrotta; avanzarlo solo dopo conferma positiva del blocco da InfluxDB.
- [ ] Gestire risposte parziali/errori senza saltare campioni non confermati.
- [ ] Riutilizzare identici measurement, tag e timestamp originali nei tentativi ripetuti, verificando l'idempotenza con la versione InfluxDB effettiva.
- [ ] Se PC/NAS/rete non disponibili, continuare registrazione e sleep e riprovare alla finestra successiva.
- [ ] Chiusura sessione con tentativo finale limitato; conservare e recuperare anche arretrati delle sessioni chiuse.

Completata quando: dopo un periodo offline tutto l'arretrato arriva al database con orari originali, senza punti duplicati né blocchi dell'acquisizione.

## M6 — Monitoraggio e importazione manuale di recupero

- [ ] Adattare Analyzer alla nuova sessione e ai tre vasi, verificando i nomi dei campi esistenti.
- [ ] Mostrare grafici, ultima misura ricevuta e ritardo dei dati, distinguendo dati vecchi da valori correnti.
- [ ] Realizzare importazione da SD: copia locale, validazione e invio in blocchi a InfluxDB.
- [ ] Rendere import manuale e upload ESP32 coerenti sulle identità dei punti, anche se si sovrappongono.
- [ ] Conservare i file locali se InfluxDB non è raggiungibile e permettere di riprovare.

Completata quando: monitoraggio remoto e recupero da SD producono gli stessi dati utilizzabili dall'Analyzer.

## M7 — Prova completa e documentazione

- [ ] Eseguire una sessione di almeno 72 ore con tre vasi, campionamento e invio periodico.
- [ ] Verificare reset, perdita alimentazione, sensore assente, SD piena/assente e database/rete temporaneamente indisponibili.
- [ ] Confrontare conteggi, timestamp e valori tra SD e InfluxDB, inclusi invii ripetuti e chiusura con arretrato.
- [ ] Documentare autonomia misurata, configurazione, cablaggio, avvio/arresto e recupero dei dati.

Completata quando: i guasti provati hanno esiti documentati, i dati salvati sono recuperabili e i limiti residui sono espliciti.

## Ordine di lavoro

M1 → M2 → M3 → M4 → M5 → M6 → M7. Prima affidabilità della registrazione locale, poi risparmio energetico e sincronizzazione.

Le milestone sono contenute in questo file nel branch dedicato; non sono GitHub Milestones globali del repository. Nessuna implementazione è dichiarata completata da questo documento.
