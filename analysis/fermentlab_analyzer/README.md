# FermentLab Analyzer

FermentLab Analyzer è un piccolo tool locale in Python per leggere sessioni
FermentLab direttamente da InfluxDB e trasformarle in curve operative visibili
in una UI Streamlit.

## Obiettivo

Il tool non scrive su InfluxDB: legge solo i dati esistenti e mostra:

- volume grezzo e filtrato, quando il contenitore è calibrato;
- altezza dell'impasto come fallback per sessioni senza volume;
- crescita percentuale rispetto a una baseline iniziale;
- temperatura dell'impasto e dell'ambiente;
- velocità di crescita e accelerazione in `%/h` e `%/h^2`;
- eventuali metadati della ricetta letti da `session_start`.

## Architettura del progetto

Il codice è organizzato in modo semplice, con una separazione chiara tra:

- [app.py](app.py): entry point della UI Streamlit. Gestisce la sidebar,
  la selezione della sessione, i parametri di elaborazione e il rendering
  delle metriche e dei grafici.
- [fermentlab_analyzer/influx.py](fermentlab_analyzer/influx.py): layer di accesso
  a InfluxDB. Esegue query read-only, carica le sessioni disponibili e recupera
  i metadati della sessione.
- [fermentlab_analyzer/processing.py](fermentlab_analyzer/processing.py): motore
  di analisi. Pulizia del segnale, smoothing, despike, baseline, crescita,
  velocità e accelerazione.
- [fermentlab_analyzer/fingerprint.py](fermentlab_analyzer/fingerprint.py):
  post-processing quantitativo. Estrae tempi caratteristici, velocità assolute
  e specifiche, fasi, metriche termiche, qualità ed export machine-readable.
- [fermentlab_analyzer/config.py](fermentlab_analyzer/config.py): impostazioni di
  connessione, leggibili da ambiente o dalla UI.

## Flusso di esecuzione

1. L'applicazione legge la configurazione InfluxDB da ambiente o dalla sidebar.
2. Carica l'elenco delle sessioni disponibili negli ultimi giorni configurati.
3. L'utente sceglie una sessione.
4. Il tool recupera i punti di misura della sessione e i metadati di start.
5. L'analisi calcola una baseline, il segnale filtrato e le curve operative.
6. La UI presenta prima i parametri in forma tabellare; i grafici restano
   disponibili come approfondimento dedicato.

## Configurazione

Creare in InfluxDB un token con permessi di sola lettura sul bucket di
FermentLab, quindi impostare queste variabili d'ambiente in locale:

```powershell
$env:FERMENTLAB_INFLUX_URL = "http://localhost:8086"
$env:FERMENTLAB_INFLUX_ORG = "FermentLab"
$env:FERMENTLAB_INFLUX_BUCKET = "fermentlab"
$env:FERMENTLAB_INFLUX_TOKEN = "TOKEN_READ_ONLY"
$env:FERMENTLAB_INFLUX_MEASUREMENT = "fermentation_measurement"
```

Il token non va salvato nel repository. In alternativa si può inserire nel
campo protetto della sidebar ogni volta che si avvia l'applicazione.

## Esecuzione locale

Dalla radice del repository:

```powershell
.venv\Scripts\python.exe -m pip install -r analysis\fermentlab_analyzer\requirements.txt
.venv\Scripts\python.exe -m streamlit run analysis\fermentlab_analyzer\app.py
```

Note utili:

- l'applicazione elenca automaticamente i `session_id` disponibili;
- la UI aggiorna le query ogni 30 secondi tramite caching;
- il pulsante "Aggiorna dati" forza un nuovo caricamento;
- il controllo "Ignora i primi minuti" sposta la baseline quando il campione
  non era ancora stabile al momento dello START;
- se il bucket contiene un record `session_start` con il blocco `recipe`,
  l'interfaccia mostra i parametri della ricetta sotto ai KPI.

## Modifiche tipiche per uno sviluppatore

- Per cambiare i KPI o le curve mostrate, lavorare su
  [fermentlab_analyzer/processing.py](fermentlab_analyzer/processing.py).
- Per cambiare come vengono lette le sessioni o i metadati da InfluxDB,
  lavorare su [fermentlab_analyzer/influx.py](fermentlab_analyzer/influx.py).
- Per cambiare etichette, textbox, slider o layout della UI, lavorare su
  [app.py](app.py).
- Per aggiungere o correggere logiche di calcolo, aggiungere test in
  [tests/test_processing.py](tests/test_processing.py).

## Confronto tra sessioni

Nella UI è disponibile anche una modalità "Compare Sessions" per confrontare
più sessioni FermentLab. La vista iniziale è una tabella testuale dei parametri
quantitativi; i grafici comparativi e i relativi controlli di allineamento si
aprono scegliendo esplicitamente "Grafici di confronto".

Funziona così:

- si selezionano più `session_id` con una multiselect;
- per ogni sessione si imposta un offset manuale in ore (o minuti, se si preferisce
  trasformarlo in frazioni d'ora);
- il tempo grafico viene calcolato come `elapsed_ms - offset_ms`, quindi
  `t = 0` rappresenta l'evento di allineamento scelto;
- l'eventuale linea verticale a `t = 0` aiuta a confrontare eventi come
  l'uscita dal frigo tra sessioni diverse;
- i dati InfluxDB non vengono modificati: l'offset è solo una trasformazione
  di analisi e visualizzazione.

## Test

```powershell
.venv\Scripts\python.exe -m unittest discover -s analysis\fermentlab_analyzer\tests
```

Le formule sono intenzionalmente semplici e verificabili: una mediana mobile
filtra il segnale disponibile, la baseline è la mediana della finestra iniziale
e la velocità di crescita è la pendenza della crescita percentuale nella
finestra temporale selezionata. Quando non c'è volume, l'applicazione usa
l'altezza e lo segnala chiaramente.

## Fermentation fingerprint

La prima scheda **Parametri** trasforma ogni sessione in un
`FermentationMetrics` numerico e ne presenta i risultati per gruppo, parametro,
valore, qualità e nota. Le schede successive raccolgono i grafici della singola
sessione, le curve derivate e l'analisi temperatura-dinamica. La pipeline è:

1. validazione e scelta automatica `volume_ml` → `dough_height_mm`;
2. despike e smoothing già eseguiti da `analyze_session`, senza modificare i raw;
3. regressione polinomiale locale centrata sul tempo reale, quindi compatibile
   anche con sampling non uniforme;
4. derivate della curva elaborata;
5. soglie interpolate, fasi, temperature e integrali termici.

I tempi `t10`…`t200` usano interpolazione lineare tra i campioni che
circondano la prima soglia. Se una soglia non viene raggiunta il valore resta
`N.A.`.

Il **lag time** è l'inizio del primo intervallo continuo in cui la velocità è
almeno una frazione configurabile di `vmax` (20% di default) per la durata
minima configurata. Il **plateau** richiede, dopo `vmax` e almeno +50% di
crescita, una velocità in valore assoluto inferiore alla frazione configurata
di `vmax` per un intervallo continuo. Il **collasso** richiede un picco
significativo e una perdita dal massimo superiore sia alla percentuale sia
alla durata configurate: una singola oscillazione non è sufficiente.

Ogni evento complesso espone uno stato `valid`, `unavailable` oppure
`low_confidence`. Il confronto multi-sessione calcola le metriche sulla
timeline originale; gli offset restano esclusivamente trasformazioni di
visualizzazione. CSV e JSON conservano valori numerici, unità e qualità senza
convertire le metriche in sole stringhe formattate.
