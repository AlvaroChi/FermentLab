# FermentLab V2 — Codex handoff

Questo file è il contratto operativo per lavorare con Codex in VS Code. I documenti
tecnici dettagliati restano `fermentlab-v2-milestones.md`,
`fermentlab-v2-execution-plan.md` e il contratto dati V2.

## Obiettivo

Un solo ESP32-S3-Zero gestisce tre vasi. Ogni vaso ha VL53L4CD, SHT31-DIS e
DS18B20. ToF e SHT31 passano attraverso un canale dedicato del TCA9548A; i tre
DS18B20 usano un bus OneWire comune che bypassa il TCA. La microSD SPI è
l'archivio canonico. Il DS3231 mantiene l'ora offline. Il Wi-Fi sincronizza
periodicamente l'arretrato già salvato su SD; fra i cicli il sistema entra in deep
sleep.

## Hardware confermato e verifiche residue

- ESP32-S3-Zero / ESP32-S3FH4R2: pin definitivi e profilo PlatformIO da verificare
  sulla scheda reale.
- RTC HW-084: DS3231 + AT24C32, pin GND/VCC/SDA/SCL/SQW/32K. Il ramo
  `VCC -> R4 201 -> D2 -> BAT+` è stato ricostruito dalla scheda. Non inserire
  una CR2032 finché R4 non è stata rimossa manualmente.
- ToF ricevuto: breakout bianco serigrafato `VL53L4`, pin
  VIN/GND/SCL/SDA/INT/LPN, coerente con VL53L4CD. Non riutilizzare driver o
  calibrazioni VL53L0X.
- TCA9548A, microSD SPI 3,3 V, tre SHT31-DIS e tre DS18B20: da provare
  progressivamente sul banco.
- Alimentazione sensori prevista a 3,3 V. Powerbank e frigorifero entrano soltanto
  dopo il bring-up completo sul banco.
- `INT` e `LPN` dei ToF restano scollegati nei primi test.

Indirizzi attesi, da confermare con scanner: VL53L4CD `0x29`, SHT31
`0x44`/`0x45`, DS3231 `0x68`, AT24C32 `0x50`–`0x57`, TCA9548A
normalmente `0x70`. I DS18B20 non sono I2C: vanno identificati dalle ROM OneWire.

## Fonti di verità

Prima di agire leggere, nell'ordine:

1. eventuale `AGENTS.md`;
2. `README.md`;
3. `docs/fermentlab-v2-milestones.md`;
4. `docs/fermentlab-v2-execution-plan.md`;
5. contratto dati V2 e fixture;
6. `experiments/esp32/fermentation-v2/platformio.ini`;
7. sorgenti e README del target V2.

Codice, foto e misure reali prevalgono sulle pagine commerciali e sulla memoria
della chat. Distinguere sempre osservato, documentato, dedotto e non ancora
misurato.

## Stato dichiarato da verificare localmente

- coordinamento: `planning/fermentlab-v2`;
- contratto dati: `v2/d01-data-contract`;
- skeleton firmware: `v2/f01-firmware-skeleton`;
- primo bring-up: `v2/t01-hardware-tests`;
- nel branch T01 sono dichiarati l'ambiente PlatformIO `hardware_i2c_scan` e uno
  scanner I2C su SDA GPIO8 / SCL GPIO9.

Non assumere che branch, dipendenze, pin o build siano corretti: verificarli nel
clone locale prima di modificare o collegare hardware.

## Workflow obbligatorio

- Non lavorare direttamente su `main`.
- Un branch e un obiettivo verificabile per volta: `v2/tNN-...` per test,
  `v2/fNN-...` per firmware, `v2/dNN-...` per contratti/documentazione.
- Prima di modificare eseguire:

```bash
git status --short --branch
git branch --show-current
git log --oneline --decorate -5
git remote -v
pio --version
pio project config
```

- Non fare merge, rebase distruttivi, force-push o reset distruttivi.
- Commit piccoli e descrittivi. Non modificare file estranei al task.
- Una build riuscita non vale come test hardware.
- Non dichiarare eseguito un comando o superato un test che non è stato realmente
  eseguito.

## Credenziali

Non leggere, mostrare, stampare, modificare o committare `secrets.h`, token
InfluxDB, password Wi-Fi, dump NVS o altre credenziali. Verificare soltanto che
siano ignorati da Git. Per build offline usare placeholder o template già previsti.
Nessun collegamento automatico a InfluxDB reale.

## Ordine di bring-up

1. Verificare clone, branch e working tree.
2. Compilare lo skeleton simulato senza hardware.
3. Compilare e caricare `hardware_i2c_scan`; seriale stabile, nessun reboot.
4. RTC solo, senza batteria: attesi DS3231 `0x68` e AT24C32 `0x50`–`0x57`.
5. Test lettura RTC; backup con CR2032 solo dopo rimozione manuale di R4.
6. microSD sola: mount, write, close, reset, readback.
7. TCA solo: `0x70` e selezione indipendente dei canali.
8. Un VL53L4 diretto, poi TCA canale 0; quindi tre ToF sui canali 0–2.
9. Un SHT31, poi tre SHT31 sugli stessi canali 0–2.
10. Un DS18B20 con pull-up 4,7 kΩ, poi tre ROM sul bus comune.
11. Sistema completo sul banco per almeno 100 cicli senza reboot o sensori
    mescolati.
12. Cavi reali, deep sleep, powerbank, frigorifero e infine upload InfluxDB.

Aggiungere un solo componente per fase. Ogni test deve stampare identificazione,
valore, stato errore e criterio PASS/FAIL senza nascondere timeout o valori mancanti.

## Primo task Codex

Aprire `v2/t01-hardware-tests`, verificare che derivi dalla corretta base V2 e
compilare, senza cambiare codice:

```bash
cd experiments/esp32/fermentation-v2
pio run -e esp32s3zero
pio run -e hardware_i2c_scan
git diff --check
git status --short
```

Se una build fallisce, fermarsi, riportare l'errore completo e proporre la minima
correzione. Se entrambe riescono, riportare dimensioni firmware e preparare
l'upload dello scanner; non procedere automaticamente al cablaggio successivo.

## Rapporto finale richiesto a ogni agente

- branch e commit base;
- file modificati;
- comandi realmente eseguiti e relativo esito;
- distinzione fra build, test simulato e prova fisica;
- commit creato;
- limiti e prossimo singolo test manuale richiesto ad Alvaro.
