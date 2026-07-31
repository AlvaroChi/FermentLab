# Caratterizzazione VL53L0X con ESP32

## Versione attuale: test hardware semplice

Il firmware attivo in `src/main.cpp` verifica il collegamento del VL53L0X e
stampa una distanza in millimetri ogni 2 secondi. L'intervallo si modifica in
`include/Config.h`:

```cpp
constexpr uint32_t READ_INTERVAL_SECONDS = 2;
```

Compilare, caricare e aprire il monitor seriale a 115200 baud:

```powershell
pio run
pio run --target upload
pio device monitor
```

Un avvio corretto produce un output simile:

```text
=== Test hardware ESP32 + VL53L0X ===
Inizializzazione VL53L0X...
Sensore pronto.
Intervallo letture: 2 s
Distanza: 153 mm
Distanza: 151 mm
```

Le sezioni successive conservano il piano e gli strumenti già preparati per la
futura fase di calibrazione. I comandi interattivi descritti sotto non fanno
parte del firmware hardware-test attuale.

## Piano per la calibrazione successiva

Questo progetto misura accuratezza, ripetibilità e tasso di letture non valide di
un modulo CJ-VL53L0X V2 / VL53L0X. Non presume che il sensore sia adatto
all'impasto: prima si caratterizza un bersaglio rigido, piatto e opaco, poi si
ripete la stessa campagna su una superficie umida e irregolare.

## Collegamenti

Configurazione predefinita per un ESP32 DevKit / ESP32-WROOM:

| VL53L0X | ESP32 | Nota |
|---|---|---|
| VCC oppure VIN | 3V3 | Alimentazione prudente per moduli di provenienza incerta |
| GND | GND | Massa comune |
| SDA | GPIO 21 | I2C dati |
| SCL | GPIO 22 | I2C clock |
| XSHUT | non collegato | Serve solo per spegnimento/indirizzi multipli |
| GPIO1 | non collegato | Il firmware interroga lo stato via I2C |

Non alimentare il modulo a 5 V se non è documentata la presenza del regolatore e
del level shifter sulla specifica schedina. I GPIO dell'ESP32 non sono
5 V tolerant. Con cavi corti, la configurazione usa I2C a 400 kHz; in presenza
di errori I2C provare 100000 in `include/Config.h`.

L'indirizzo I2C predefinito del VL53L0X è `0x29`. Molti breakout includono già
le resistenze di pull-up; se mancano, aggiungere circa 4.7 kohm da SDA e SCL a
3.3 V. Evitare pull-up a 5 V.

## Libreria e impostazioni

La libreria consigliata è `pololu/VL53L0X @ 1.3.1`, fissata in
`platformio.ini`. È compatta, stabile e rende disponibili anche i registri
necessari a controllare lo stato grezzo della misura.

Impostazioni iniziali:

- modalità continua back-to-back;
- timing budget: 50 ms;
- limite segnale: 0.25 MCPS (valore standard Pololu/ST);
- timeout software: almeno 500 ms;
- 200 acquisizioni registrate;
- 5 letture iniziali di warm-up non conteggiate;
- pausa aggiuntiva: 20 ms;
- validità: I2C corretto, stato hardware `RANGECOMPLETE`, distanza 5..2000 mm.

Il tempo tra campioni è approssimativamente `timing budget + delay`; quindi le
impostazioni iniziali producono circa una misura ogni 70 ms. Per privilegiare
l'accuratezza, ripetere almeno una campagna con `budget=200`. Non mescolare test
a budget diversi nello stesso confronto senza annotarlo: il CSV base non
contiene questa impostazione.

## Compilazione, caricamento e Serial Monitor

Aprire in VS Code **questa cartella**, non la cartella `src`, poi usare i pulsanti
PlatformIO **Build**, **Upload** e **Serial Monitor**. In alternativa:

```powershell
cd D:\_Data\Documents\PlatformIO\Projects\VL53L0X_Calibration
pio run
pio run --target upload
pio device monitor
```

Il monitor è configurato a 115200 baud. Premere Invio dopo ogni comando:

```text
50
n=500
delay=20
budget=200
status
header
retry
help
```

Una distanza, per esempio `50`, avvia subito il test. Il firmware torna
automaticamente in attesa al termine.

## Formato CSV

Ogni test stampa un riepilogo umano e poi intestazione e riga CSV:

```text
distanza_reale_mm,n_totali,n_valide,n_non_valide,media_mm,mediana_mm,std_mm,min_mm,p05_mm,p25_mm,p75_mm,p95_mm,max_mm,errore_media_mm,errore_mediana_mm
```

La deviazione standard è campionaria (`n-1`). Mediana e percentili usano
interpolazione lineare alla posizione `p*(n-1)`. Gli errori hanno segno
`misurata - reale`.

### Salvare l'output

Metodo semplice: copiare da ogni blocco `CSV:` la sola riga numerica dentro
`data/misure.csv`, sotto l'intestazione di `data/misure_template.csv`.

Per registrare automaticamente tutto il monitor:

```powershell
pio device monitor --filter log2file
```

PlatformIO salva un `.log` nella cartella `logs`. Lo script di analisi accetta
direttamente anche questo log misto e ignora messaggi, prompt e intestazioni
ripetute.

Per ottenere un CSV pulito da un log è sufficiente eseguire l'analisi: tra gli
output verrà creato `dati_estratti.csv`.

## Campagna di prova

Usare un supporto rigido per sensore e bersaglio. Il riferimento geometrico deve
essere il piano frontale del sensore o un'origine definita e sempre identica.
Attendere qualche minuto dopo l'accensione e non muovere nulla durante una
serie.

Eseguire, nell'ordine o in ordine casualizzato:

```text
20
30
40
50
75
100
125
150
```

Raccomandazioni:

1. Fare almeno 3 serie indipendenti per distanza.
2. Tra le serie, rimuovere e riposizionare bersaglio o sensore: così si misura
   anche la riproducibilità del montaggio.
3. Usare prima `n=200`, `delay=20`, `budget=50`.
4. Ripetere la campagna più promettente a `budget=200`.
5. Annotare illuminazione, materiale/colore, temperatura, budget e numero serie
   in un quaderno o nel nome del file.
6. Considerare 20 mm un punto critico, da accettare solo se i dati lo
   giustificano.

Il campo visivo del sensore è ampio (circa 25 gradi): il diametro osservato è
approssimativamente `2*d*tan(12.5°)`, quindi circa 9 mm a 20 mm e 67 mm a
150 mm. Allineamento, bordo del vaso e pareti possono cambiare la lettura.

## Analisi Python

Da PowerShell, nella cartella del progetto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r analysis\requirements.txt
python analysis\analyze_vl53l0x.py data\misure.csv
```

Oppure analizzare direttamente uno o più log:

```powershell
python analysis\analyze_vl53l0x.py logs\*.log -o analysis\results_rigido_50ms
```

`data/esempio_sintetico.csv` serve soltanto per provare subito lo script e non
contiene misure del sensore reale:

```powershell
python analysis\analyze_vl53l0x.py data\esempio_sintetico.csv
```

Output:

- `01_reale_vs_misurata.png`;
- `02_errore_assoluto.png`;
- `03_deviazione_standard.png`;
- `dati_estratti.csv`;
- `tabella_riassuntiva.csv`;
- `regressione_calibrazione.txt`.

La regressione primaria è:

```text
misurata = a * reale + b
reale_stimata = (misurata - b) / a
```

Il secondo formato è l'equazione da applicare a nuove misure. RMSE e MAE
calibrati calcolati sugli stessi punti del fit sono ottimistici: per una verifica
seria, ricavare `a` e `b` da una campagna e provarli su una seconda campagna.

## Criteri pratici di decisione

Non usare un unico numero per dichiarare valido il sensore. Per ogni distanza
valutare:

- **Intervallo affidabile:** tratto continuo con almeno 99% di letture valide,
  nessun salto evidente nei percentili e nessuna dipendenza critica da piccoli
  disallineamenti. Un punto isolato buono non estende l'intervallo.
- **Accuratezza effettiva:** MAE e massimo errore assoluto su dati di verifica,
  prima e dopo calibrazione. Come obiettivo iniziale per un vaso da 150 mm:
  MAE <= 2 mm e massimo errore <= 4 mm.
- **Ripetibilità:** `std_mm` entro circa 1 mm e ampiezza `P95-P05` entro 3 mm
  sono un buon punto di partenza. Confrontare anche la deviazione tra le medie
  delle serie riposizionate.
- **Offset sistematico:** errori con stesso segno e quasi costanti indicano
  offset; una pendenza diversa da 1 indica errore di scala. Calibrare solo se
  offset e pendenza rimangono stabili in giorni, temperatura e materiali
  diversi.
- **Utilità per la lievitazione:** la crescita `Delta h` corrisponde alla
  diminuzione della distanza. Un offset costante si cancella nelle differenze,
  ma rumore, deriva e bias dipendente dalla superficie no. La variazione minima
  interessante dovrebbe essere almeno 3 volte la deviazione standard combinata
  e maggiore dell'errore di riposizionamento.

Per decidere sul caso reale:

1. scegliere l'intervallo di distanza che il montaggio sopra il vaso userà
   davvero;
2. superare i criteri sul bersaglio rigido;
3. ripetere identica campagna con superficie umida e irregolare simile
   all'impasto;
4. confrontare bias, dispersione e tasso di validità tra le due superfici;
5. fare una prova dinamica con misure manuali di altezza indipendenti.

Se la superficie tipo impasto sposta la media di diversi millimetri, aumenta
molto `P95-P05`, o produce salti quando cambia forma/lucidità, il sensore non è
adatto come misura assoluta anche se il bersaglio rigido aveva dato ottimi
risultati. Potrebbe restare utile solo come indicatore qualitativo o con
filtraggio temporale e geometria controllata.
