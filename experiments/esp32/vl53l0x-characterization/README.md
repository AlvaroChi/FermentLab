# Caratterizzazione VL53L0X con ESP32

Firmware e strumenti per misurare accuratezza, ripetibilità e tasso di letture
non valide di un sensore VL53L0X prima di usarlo su un processo di fermentazione.

## Collegamenti

| VL53L0X | ESP32 DevKit | Nota |
|---|---|---|
| VIN/VCC | 3V3 | Alimentazione prudente per breakout non documentati |
| GND | GND | Massa comune |
| SDA | GPIO 21 | Dati I2C |
| SCL | GPIO 22 | Clock I2C |
| XSHUT | non collegato | Non necessario con un solo sensore |
| GPIO1 | non collegato | Il firmware interroga lo stato via I2C |

Eseguire i collegamenti con la scheda spenta. Non usare 5 V se il breakout non
documenta chiaramente regolatore e level shifter.

## Compilazione e caricamento

Dalla radice di `FermentLab`:

```powershell
cd experiments\esp32\vl53l0x-characterization
pio run
pio run --target upload
pio device monitor
```

Il monitor seriale è configurato a 115200 baud con terminazione `LF`.

## Uso del firmware

All'avvio il firmware inizializza il sensore e mostra configurazione e comandi.
Una distanza numerica avvia una serie di acquisizioni:

```text
50
```

Il valore significa che il bersaglio è stato posizionato a una distanza reale di
50 mm dal riferimento geometrico scelto. Al termine vengono stampati:

- numero e percentuale di letture valide;
- timeout, errori I2C, stati sensore non validi e fuori intervallo;
- media, mediana, deviazione standard, min, max e percentili;
- errore rispetto alla distanza reale;
- una riga CSV pronta per l'analisi.

Durante una serie si può inviare `x` per interromperla.

### Comandi

| Comando | Effetto |
|---|---|
| `50` | Avvia una serie con distanza reale di 50 mm |
| `read` | Esegue una sola lettura |
| `n=200` | Imposta il numero di acquisizioni per serie |
| `delay=20` | Imposta la pausa aggiuntiva tra letture, in millisecondi |
| `budget=50` | Imposta il timing budget del sensore, in millisecondi |
| `status` | Mostra configurazione e stato del sensore |
| `header` | Ristampa l'intestazione CSV |
| `retry` | Ritenta l'inizializzazione dopo un problema di collegamento |
| `help` | Mostra i comandi |

Intervalli accettati:

- `n`: 10–10000;
- `delay`: 0–5000 ms;
- `budget`: 20–1000 ms;
- distanza reale: maggiore di 0 e non oltre 2000 mm.

Le impostazioni iniziali sono `n=200`, `delay=20` e `budget=50`. Prima di ogni
serie vengono effettuate cinque letture di warm-up non conteggiate.

## Prima campagna consigliata

Usare inizialmente un bersaglio rigido, piatto, opaco e abbastanza grande da
coprire il campo visivo del sensore. Sensore e bersaglio devono essere paralleli
e fissati a supporti stabili.

1. Definire un riferimento geometrico ripetibile per la distanza reale.
2. Accendere il sistema e attendere qualche minuto.
3. Verificare il funzionamento con `read`.
4. Impostare `n=200`, `delay=20` e `budget=50`.
5. Misurare almeno le distanze `20, 30, 40, 50, 75, 100, 125, 150` mm.
6. Eseguire almeno tre serie per distanza.
7. Tra le serie, rimuovere e riposizionare il bersaglio per misurare anche
   l'errore di posizionamento.
8. Ripetere in seguito la campagna più promettente con `budget=200`.

Il punto a 20 mm è critico e va mantenuto soltanto se i dati ne dimostrano
l'affidabilità. Non muovere sensore o bersaglio durante una serie.

## Salvare le misure

Usare il registratore dedicato, che crea immediatamente il file e forza ogni
blocco ricevuto su disco:

```powershell
python ..\..\..\tools\serial_capture.py --port COM3 --prefix calibration
```

Il percorso del log viene mostrato appena parte il programma. Inserire le
distanze nella stessa finestra e scrivere `fine` per chiudere la sessione. Il
programma mostra byte ricevuti e dimensione finale, e restituisce un errore se
non ha ricevuto dati reali dall'ESP32.

Il registratore richiede `pyserial`, incluso in `analysis/requirements.txt`.
In alternativa si può copiare da ogni blocco `CSV:` la riga numerica in
`data/misure.csv`, sotto l'intestazione di `data/misure_template.csv`.

Il formato è:

```text
distanza_reale_mm,n_totali,n_valide,n_non_valide,media_mm,mediana_mm,std_mm,min_mm,p05_mm,p25_mm,p75_mm,p95_mm,max_mm,errore_media_mm,errore_mediana_mm
```

Non mescolare nello stesso confronto sessioni con timing budget differenti
senza annotarlo nel nome del log o nelle note della campagna.

## Analisi Python

Dalla cartella dell'esperimento:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r analysis\requirements.txt
python analysis\analyze_vl53l0x.py data\misure.csv
```

Lo script accetta anche uno o più log completi:

```powershell
python analysis\analyze_vl53l0x.py logs\*.log -o analysis\results
```

Per verificare subito lo script senza misure reali:

```powershell
python analysis\analyze_vl53l0x.py data\esempio_sintetico.csv
```

Produce tabelle, grafici e la regressione:

```text
misurata_mm = a * reale_mm + b
reale_stimata_mm = (misurata_mm - b) / a
```

La regressione va calcolata su una campagna e verificata su una seconda campagna
indipendente. I risultati ottenuti sugli stessi dati usati per il fit sono
inevitabilmente ottimistici.

## Criteri iniziali

Come punto di partenza, nell'intervallo di utilizzo reale cercare:

- almeno il 99% di letture valide;
- deviazione standard entro circa 1 mm;
- ampiezza `P95-P05` entro circa 3 mm;
- errore medio assoluto entro 2 mm;
- nessun salto evidente tra distanze adiacenti.

Dopo il bersaglio rigido, ripetere la procedura su una superficie umida e
irregolare simile all'impasto. Una calibrazione geometrica non può compensare
un errore che cambia con colore, lucidità, forma o inclinazione della superficie.
