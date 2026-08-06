# FermentLab Analyzer

Applicazione locale per leggere le sessioni direttamente da InfluxDB e
trasformarle nelle prime curve operative di FermentLab:

- volume grezzo e filtrato, quando il contenitore è calibrato;
- altezza dell'impasto come alternativa per le sessioni senza volume;
- crescita percentuale rispetto alla baseline iniziale;
- temperatura dell'impasto e dell'ambiente;
- velocità di crescita relativa in `%/h`.

InfluxDB viene interrogato in sola lettura. Non è necessario esportare CSV.

## Configurazione

Creare in InfluxDB un token limitato alla lettura del bucket FermentLab, quindi
impostare queste variabili nell'ambiente locale:

```powershell
$env:FERMENTLAB_INFLUX_URL = "http://localhost:8086"
$env:FERMENTLAB_INFLUX_ORG = "FermentLab"
$env:FERMENTLAB_INFLUX_BUCKET = "fermentlab"
$env:FERMENTLAB_INFLUX_TOKEN = "TOKEN_READ_ONLY"
```

Il token non deve essere salvato nel repository. In alternativa può essere
inserito nel campo protetto della barra laterale a ogni avvio.

## Installazione e avvio

Dalla radice del repository:

```powershell
.venv\Scripts\python.exe -m pip install -r analysis\fermentlab_analyzer\requirements.txt
.venv\Scripts\python.exe -m streamlit run analysis\fermentlab_analyzer\app.py
```

L'applicazione elenca automaticamente i `session_id` disponibili e aggiorna le
query ogni 30 secondi. Il pulsante **Aggiorna dati** forza un nuovo caricamento.
Il controllo **Ignora i primi minuti** permette di spostare la baseline quando
il campione non era ancora stabile al momento dello START.
Se il bucket contiene anche il record `session_start` con il blocco `recipe`,
l'interfaccia mostra i parametri della ricetta sotto ai KPI della sessione.

## Test

```powershell
.venv\Scripts\python.exe -m unittest discover -s analysis\fermentlab_analyzer\tests
```

Le formule sono intenzionalmente semplici e verificabili: una mediana mobile
filtra il segnale disponibile, la baseline è la mediana della finestra iniziale
e la velocità di crescita è la pendenza della crescita percentuale nella
finestra temporale selezionata. Il volume ha priorità; quando manca,
l'applicazione usa l'altezza e lo segnala chiaramente.
