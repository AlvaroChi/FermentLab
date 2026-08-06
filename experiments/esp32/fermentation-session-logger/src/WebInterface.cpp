#include "WebInterface.h"

#include <ESPmDNS.h>

#include <utility>

#include "Config.h"

namespace {

const char INDEX_HTML[] PROGMEM = R"HTML(
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>FermentLab</title>
  <style>
    :root{color-scheme:dark;--bg:#101714;--panel:#18231e;--line:#2b3c33;--text:#f3f7f4;--muted:#a9b8af;--green:#52d68a;--red:#ff6b6b;--amber:#ffc857}
    *{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#20372b 0,var(--bg) 48%);color:var(--text);font:16px/1.45 system-ui,sans-serif;min-height:100vh}
    main{width:min(760px,calc(100% - 28px));margin:0 auto;padding:28px 0 48px}header{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:22px}
    h1{font-size:clamp(28px,7vw,46px);letter-spacing:-.04em;margin:0}.eyebrow{color:var(--green);font-size:12px;font-weight:800;letter-spacing:.16em;text-transform:uppercase}
    .badge{border:1px solid var(--line);border-radius:999px;padding:8px 12px;color:var(--muted);white-space:nowrap}.badge.on{border-color:#327850;color:var(--green)}
    .panel{background:rgba(24,35,30,.92);border:1px solid var(--line);border-radius:20px;padding:20px;box-shadow:0 18px 50px #0005;margin-bottom:16px}
    .session{display:flex;align-items:center;justify-content:space-between;gap:16px}.session h2,.panel h2{margin:0 0 4px;font-size:20px}.muted{color:var(--muted);font-size:14px;overflow-wrap:anywhere}
    .actions{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:18px}button{appearance:none;border:0;border-radius:14px;padding:15px 18px;font:inherit;font-weight:800;cursor:pointer;transition:.15s transform,.15s opacity}
    button:active{transform:scale(.98)}button:disabled{opacity:.45;cursor:wait}.test{background:#e8efe9;color:#152019}.toggle{background:var(--green);color:#102017}.toggle.stop{background:var(--red);color:#2b0d0d}
    .config-link{grid-column:1/-1;display:block;border:1px solid var(--line);border-radius:14px;padding:14px 18px;text-align:center;color:var(--text);background:#101814;text-decoration:none;font-weight:800}.config-link:hover{border-color:var(--green)}
    .metrics{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:16px}.metric{background:#101814;border:1px solid var(--line);border-radius:14px;padding:14px}.metric span{display:block;color:var(--muted);font-size:12px}.metric strong{display:block;font-size:21px;margin-top:4px}
    .notice{min-height:24px;margin-top:12px;color:var(--amber);font-size:14px}.start-blocker{min-height:24px;margin-top:8px;color:var(--amber);font-size:13px}.details{display:grid;grid-template-columns:repeat(2,1fr);gap:8px 20px}.details div{display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid var(--line);padding:8px 0}.details span:first-child{color:var(--muted)}
    a.nav{color:var(--text);border:1px solid var(--line);border-radius:12px;padding:9px 12px;text-decoration:none;font-weight:700}.header-actions{display:flex;align-items:center;gap:8px}
    @media(max-width:540px){header,.session{align-items:flex-start;flex-direction:column}.actions,.metrics,.details{grid-template-columns:1fr}.badge{align-self:flex-start}}
  </style>
</head>
<body>
<main>
  <header><div><div class="eyebrow">ESP32 local control</div><h1>FermentLab</h1></div><div class="header-actions"><a class="nav" href="/config">Impasto e farine</a><div id="connection" class="badge">Connessione...</div></div></header>
  <section class="panel">
    <div class="session"><div><h2 id="sessionTitle">Sessione ferma</h2><div id="sessionId" class="muted">Nessuna sessione attiva</div></div><div id="time" class="muted"></div></div>
    <div class="actions"><button id="testButton" class="test">Test lettura</button><button id="toggleButton" class="toggle">START</button><a class="config-link" href="/config">Configura prossimo impasto, farine e preset →</a></div>
    <div id="notice" class="notice"></div>
    <div id="startBlocker" class="start-blocker"></div>
  </section>
  <section class="panel">
    <h2>Ultimo test</h2><div id="testTime" class="muted">Premi “Test lettura” per acquisire un campione.</div>
    <div class="metrics">
      <div class="metric"><span>Temperatura impasto</span><strong id="doughTemperature">—</strong></div>
      <div class="metric"><span>Stato sonda impasto</span><strong id="doughStatus">—</strong></div>
      <div class="metric"><span>Temperatura ambiente</span><strong id="temperature">—</strong></div>
      <div class="metric"><span>Umidità</span><strong id="humidity">—</strong></div>
      <div class="metric"><span>Altezza impasto</span><strong id="distance">—</strong></div>
      <div class="metric"><span>Stato distanza</span><strong id="distanceStatus">—</strong></div>
    </div>
  </section>
  <section class="panel details">
    <div><span>Dispositivo</span><span id="device">—</span></div><div><span>IP</span><span id="ip">—</span></div>
    <div><span>Segnale Wi-Fi</span><span id="rssi">—</span></div><div><span>Uptime</span><span id="uptime">—</span></div>
    <div><span>Intervallo previsto</span><span id="interval">—</span></div><div><span>Letture sessione</span><span id="measurements">—</span></div>
    <div><span>Prossima lettura</span><span id="nextReading">—</span></div><div><span>Ultima misura</span><span id="lastMeasurement">—</span></div>
    <div><span>Letture in coda</span><span id="queue">—</span></div><div><span>Orologio</span><span id="clock">—</span></div>
    <div><span>Sensori</span><span id="sensors">—</span></div><div><span>LittleFS / coda</span><span id="storage">—</span></div>
    <div><span>Bus I²C</span><span id="i2cBus">—</span></div><div><span>Indirizzi I²C</span><span id="i2cAddresses">—</span></div>
    <div><span>Prossimo impasto</span><span id="draftName">—</span></div><div><span>Farina / idratazione</span><span id="draftRecipe">—</span></div>
  </section>
</main>
<script>
  let state=null,actionInProgress=false,refreshFailures=0;
  const $=id=>document.getElementById(id);
  const value=(v,unit,digits=2)=>v==null?'—':Number(v).toFixed(digits)+' '+unit;
  async function api(path,options={}){const{timeoutMs=4500,...fetchOptions}=options;const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeoutMs);try{const response=await fetch(path,{cache:'no-store',...fetchOptions,signal:controller.signal});if(!response.ok)throw new Error('HTTP '+response.status);return await response.json()}catch(error){if(error&&error.name==='AbortError')throw new Error('timeout');throw error}finally{clearTimeout(timer)}}
  const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  function renderStatus(s){state=s;$('connection').textContent='Online';$('connection').className='badge on';$('sessionTitle').textContent=s.session_active?'Sessione attiva':'Sessione ferma';$('sessionId').textContent=s.session_active?s.session_id:'Nessuna sessione attiva';$('toggleButton').textContent=s.session_active?'STOP':'START';$('toggleButton').className=s.session_active?'toggle stop':'toggle';$('time').textContent=s.timestamp||'Ora non sincronizzata';$('device').textContent=s.device_id;$('ip').textContent=s.ip;$('rssi').textContent=s.rssi_dbm+' dBm';$('uptime').textContent=Math.floor(s.uptime_s/60)+' min';$('interval').textContent=s.reading_interval_s+' s';$('measurements').textContent=s.session_measurements;$('nextReading').textContent=s.next_reading_in_s==null?'—':s.next_reading_in_s+' s';$('lastMeasurement').textContent=s.last_measurement_at||'—';$('queue').textContent=s.queue_records+' letture / '+s.queue_segments+' segmenti / '+s.queue_bytes+' B';$('clock').textContent=s.time_valid?'Sincronizzato':'In attesa NTP';$('sensors').textContent=(s.distance_sensor_ready?'VL53 ✓':'VL53 ✕')+' / '+(s.ambient_sensor_ready?'SHT3x ✓':'SHT3x ✕')+' / '+(s.dough_sensor_ready?'DS18B20 ✓':'DS18B20 ✕');$('storage').textContent=(s.storage_ready?'LittleFS ✓':'LittleFS ✕')+' / '+(s.telemetry_queue_ready?'Coda ✓':'Coda ✕');$('i2cBus').textContent=(s.i2c_bus_valid?'OK · ':'BLOCCATO · ')+'SDA '+s.i2c_sda_level+' / SCL '+s.i2c_scl_level+' @ '+Math.round(s.i2c_frequency_hz/1000)+' kHz';$('i2cAddresses').textContent=s.i2c_addresses+' ('+s.i2c_device_count+')';$('draftName').textContent=s.draft_name||'—';$('draftRecipe').textContent=(s.draft_flours||'—')+(s.draft_hydration_pct==null?'':' / '+s.draft_hydration_pct+'%');$('startBlocker').textContent=!s.session_active&&s.start_blocker?('START bloccato: '+s.start_blocker):''}
  function renderTest(t){$('testTime').textContent=t.timestamp||'Timestamp non disponibile';$('doughTemperature').textContent=value(t.dough_temperature_c,'°C');$('doughStatus').textContent=t.dough_status;$('temperature').textContent=value(t.ambient_temperature_c,'°C');$('humidity').textContent=value(t.humidity_pct,'%');const height=value(t.dough_height_mm,'mm',2),raw=t.distance_raw_median_mm==null?'raw —':'raw '+t.distance_raw_median_mm+' mm';$('distance').textContent=height+' ('+raw+')';$('distanceStatus').textContent=t.distance_status}
  async function refresh(){if(actionInProgress){setTimeout(refresh,2500);return}try{renderStatus(await api('/api/status',{timeoutMs:3000}));refreshFailures=0}catch(e){refreshFailures++;if(refreshFailures>=2){$('connection').textContent='Offline';$('connection').className='badge';$('notice').textContent='ESP32 non raggiungibile: '+e.message}}setTimeout(refresh,2500)}
  $('testButton').addEventListener('click',async()=>{const b=$('testButton');b.disabled=true;$('notice').textContent='Acquisizione in corso...';try{renderTest(await api('/api/test',{method:'POST'}));$('notice').textContent='Campione acquisito senza salvataggio.'}catch(e){$('notice').textContent='Test fallito: '+e.message}finally{b.disabled=false}});
  $('toggleButton').addEventListener('click',async()=>{const b=$('toggleButton'),before=state&&state.session_active;if(before){const name=state.draft_name||'Impasto senza nome',id=state.session_id||'ID non disponibile';if(!confirm('Questo terminera la sessione "'+name+'".\n\nID: '+id+'\n\nI dati saranno salvati e la sessione non potra essere ripresa. Confermi lo STOP?')){$('notice').textContent='STOP annullato: la sessione continua.';return}}actionInProgress=true;b.disabled=true;$('notice').textContent='Operazione in corso...';try{await api('/api/session/toggle',{method:'POST',timeoutMs:12000});let next=null;for(let attempt=0;attempt<40;attempt++){await wait(250);try{next=await api('/api/status',{timeoutMs:2500})}catch(_){continue}if(next.session_active!==before)break}if(next){renderStatus(next);$('notice').textContent=next.session_active===before?(next.start_blocker||'Comando non eseguito.'):(next.session_active?'Sessione avviata.':'Sessione terminata e salvata.')}else{$('notice').textContent='ESP32 non raggiungibile subito dopo il comando. Attendi qualche secondo e riprova.'}}catch(e){$('notice').textContent='Comando fallito: '+e.message}finally{actionInProgress=false;b.disabled=false}});
  refresh();
</script>
</body>
</html>
)HTML";

const char CONFIG_HTML[] PROGMEM = R"HTML(
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Workflow Impasto · FermentLab</title>
  <style>
    :root{color-scheme:dark;--bg:#0f1818;--bg2:#162429;--panel:#1a2a2f;--line:#2f464f;--text:#ecf2f5;--muted:#9bb0ba;--ok:#5dd39e;--danger:#ff7a7a;--warn:#f4bf67;--sky:#7ec8ff}
    *{box-sizing:border-box}
    body{margin:0;background:radial-gradient(circle at 15% -20%,#2f5d5f 0,#162429 40%,#0f1818 75%);color:var(--text);font:15px/1.5 Segoe UI,system-ui,sans-serif;min-height:100vh}
    main{width:min(1040px,calc(100% - 28px));margin:auto;padding:26px 0 60px}
    header{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;margin-bottom:16px}
    h1{font-size:clamp(30px,6vw,48px);margin:0;letter-spacing:-.03em}
    h2{margin:0;font-size:22px;letter-spacing:-.02em}
    h3{margin:18px 0 8px}
    .eyebrow{color:var(--sky);font-size:12px;font-weight:800;letter-spacing:.16em;text-transform:uppercase}
    .muted{color:var(--muted);font-size:13px}
    .panel{background:linear-gradient(180deg,rgba(26,42,47,.96) 0,rgba(22,35,40,.96) 100%);border:1px solid var(--line);border-radius:18px;padding:18px;margin-bottom:14px;box-shadow:0 14px 36px #0005}
    .workflow{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}
    .step{border:1px solid var(--line);border-radius:12px;padding:12px;background:#112024}
    .step strong{display:block;font-size:13px;color:var(--sky);margin-bottom:2px}
    .notice{position:sticky;top:8px;z-index:8;border:1px solid #80602e;background:#3a2b16;border-radius:12px;padding:10px 12px;margin-bottom:12px;display:none}
    .notice.show{display:block}
    .notice.error{border-color:#965151;background:#402222}
    .lock{color:var(--warn);font-weight:700}
    .status{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
    .pill{border:1px solid var(--line);border-radius:999px;padding:7px 10px;font-size:12px;background:#101a1f;color:var(--muted)}
    .pill.ok{border-color:#2f6a53;color:var(--ok)}
    .pill.warn{border-color:#7a5d2f;color:var(--warn)}
    .pill.info{border-color:#3f6476;color:var(--sky)}
    a,button{font:inherit;font-weight:760}
    a.back{color:var(--text);border:1px solid var(--line);border-radius:12px;padding:10px 12px;text-decoration:none;background:#101a1f}
    button{border:0;border-radius:11px;background:var(--ok);color:#102117;padding:10px 13px;cursor:pointer}
    button.secondary{background:#dce8ee;color:#162229}
    button.danger{background:var(--danger);color:#350f0f}
    button.ghost{background:transparent;color:var(--text);border:1px solid var(--line)}
    button:disabled,input:disabled,select:disabled,textarea:disabled{opacity:.45;cursor:not-allowed}
    input:read-only{opacity:.65;cursor:not-allowed}
    .toolbar{display:flex;flex-wrap:wrap;align-items:end;gap:9px;margin:12px 0}
    .toolbar .grow{flex:1;min-width:220px}
    .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
    .span2{grid-column:span 2}
    .full{grid-column:1/-1}
    label{display:block;color:var(--muted);font-size:12px;font-weight:700}
    input,select,textarea{display:block;width:100%;margin-top:5px;border:1px solid var(--line);border-radius:10px;background:#101a1f;color:var(--text);font:inherit;padding:10px}
    textarea{min-height:76px;resize:vertical}
    .check{display:flex;align-items:center;gap:8px;margin-top:22px;color:var(--text);font-size:14px}
    .check input{width:auto;margin:0}
    .mix-row{display:grid;grid-template-columns:1fr 140px auto;gap:8px;align-items:end;margin-bottom:8px}
    .mix-summary{margin-top:8px;font-size:12px;color:var(--muted)}
    .mix-summary.error{color:var(--danger)}
    .cards{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:12px 0}
    .card{border:1px solid var(--line);border-radius:12px;background:#101a1f;padding:11px;text-align:left;color:var(--text)}
    .card.selected{border-color:var(--ok)}
    .card small{display:block;color:var(--muted);margin-top:3px}
    .status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--ok);margin-right:6px}
    .status-dot.unverified{background:var(--warn)}
    fieldset{border:0;padding:0;margin:0}
    .backup{display:flex;flex-wrap:wrap;gap:9px;margin-top:12px}
    .backup label{border:1px solid var(--line);border-radius:11px;padding:10px 12px;color:var(--text);cursor:pointer;background:#101a1f}
    .backup input{display:none}
    .divider{height:1px;background:var(--line);margin:14px 0}
    .sticky-actions{position:sticky;bottom:10px;z-index:7;display:flex;flex-wrap:wrap;gap:9px;justify-content:space-between;align-items:center;border:1px solid var(--line);border-radius:14px;padding:10px 12px;background:#0f1a1ee6;backdrop-filter:blur(6px)}
    .sticky-actions .left{display:flex;gap:8px;align-items:center}
    @media(max-width:820px){.workflow{grid-template-columns:1fr}.grid{grid-template-columns:1fr 1fr}.cards{grid-template-columns:1fr 1fr}}
    @media(max-width:560px){header{flex-direction:column}.grid,.cards{grid-template-columns:1fr}.span2{grid-column:auto}.mix-row{grid-template-columns:1fr 105px auto}}
  </style>
</head>
<body><main>
  <header>
    <div>
      <div class="eyebrow">FermentLab workflow locale</div>
      <h1>Configura il prossimo impasto</h1>
      <div class="muted">Flusso guidato: scegli preset, applica, salva bozza e poi START da dashboard.</div>
      <div class="workflow">
        <div class="step"><strong>Step 1</strong>Seleziona o crea un preset in libreria.</div>
        <div class="step"><strong>Step 2</strong>Applica il preset alla bozza e rifinisci i valori.</div>
        <div class="step"><strong>Step 3</strong>Salva bozza: sara la fotografia usata allo START.</div>
      </div>
    </div>
    <a class="back" href="/">← Dashboard</a>
  </header>
  <div id="notice" class="notice"></div>
  <div class="panel">
    <h2>Stato configurazione</h2>
    <div class="status">
      <span id="sessionLockBadge" class="pill info">Sessione: controllo...</span>
      <span id="draftState" class="pill warn">Bozza: da verificare</span>
      <span id="presetState" class="pill warn">Preset: da verificare</span>
      <span id="mixState" class="pill warn">Mix farine: da verificare</span>
    </div>
  </div>

  <section class="panel">
    <h2>1) Preset e applicazione alla bozza</h2>
    <div class="muted">Il preset non parte da solo: applicalo esplicitamente alla bozza e poi salva la bozza.</div>
    <div class="toolbar">
      <label class="grow">Preset da applicare alla bozza<select id="draftPreset"></select></label>
      <button id="applyPreset" type="button" class="secondary">Applica preset alla bozza</button>
      <button id="newPresetTop" type="button" class="ghost">+ Nuovo preset</button>
    </div>
    <div id="selectedPresetHint" class="muted"></div>
  </section>

  <section class="panel">
    <h2>2) Bozza prossimo impasto</h2>
    <div id="lockText" class="muted">Questa bozza viene fotografata nella testa del JSONL quando premi START.</div>
    <fieldset id="draftFieldset">
      <div class="grid">
        <label class="span2">Nome impasto<input id="draftName" maxlength="80"></label><label>Farina totale (g)<input id="draftTotal" type="number" min="1" step="1"></label>
        <label>Idratazione (%)<input id="draftHydration" type="number" min="0" max="200" step="0.1"></label><label>Sale (%)<input id="draftSalt" type="number" min="0" max="20" step="0.01"></label><label>Massa iniziale impasto (g, facoltativa)<input id="draftMass" type="number" min="1" step="1"></label>
        <label>Intervallo acquisizione (secondi)<input id="draftInterval" type="number" min="5" max="86400" step="1"></label><label>Tipo lievito<select id="draftYeastType"><option value="fresh">Fresco</option><option value="dry">Secco</option><option value="sourdough">Lievito madre</option><option value="none">Nessuno</option></select></label><label>Lievito (%)<input id="draftYeast" type="number" min="0" max="20" step="0.001"></label>
        <label class="check"><input id="draftAutolyse" type="checkbox">Autolisi</label>
        <label>Autolisi (minuti)<input id="draftAutolyseMin" type="number" min="0" max="10080" step="1"></label><label class="full">Note<textarea id="draftNotes"></textarea></label>
      </div>
      <h3>Miscela farine bozza</h3>
      <div id="draftMix"></div>
      <button type="button" class="secondary" data-add-mix="draftMix">+ Aggiungi farina</button>
      <div id="draftMixSummary" class="mix-summary">Somma mix: --</div>
      <div class="divider"></div>
      <button id="saveDraft" type="button">Salva bozza impasto</button>
    </fieldset>
  </section>

  <section class="panel">
    <h2>3) Libreria preset</h2>
    <div class="muted">Crea o modifica ricette riutilizzabili. Dopo il salvataggio, applica il preset alla bozza.</div>
    <fieldset id="presetFieldset">
      <div class="toolbar"><label class="grow">Preset da modificare<select id="presetSelect"></select></label><button id="newPreset" type="button" class="secondary">Nuovo</button><button id="deletePreset" type="button" class="danger">Elimina</button><button id="savePreset" type="button">Salva preset</button></div>
      <div class="grid">
        <label>ID stabile<input id="presetId" maxlength="48" placeholder="mia-ricetta"></label><label class="span2">Nome<input id="presetName" maxlength="80"></label>
        <label>Farina totale (g)<input id="presetTotal" type="number" min="1" step="1"></label><label>Idratazione (%)<input id="presetHydration" type="number" min="0" max="200" step="0.1"></label><label>Sale (%)<input id="presetSalt" type="number" min="0" max="20" step="0.01"></label>
        <label>Intervallo acquisizione (secondi)<input id="presetInterval" type="number" min="5" max="86400" step="1"></label><label>Tipo lievito<select id="presetYeastType"><option value="fresh">Fresco</option><option value="dry">Secco</option><option value="sourdough">Lievito madre</option><option value="none">Nessuno</option></select></label><label>Lievito (%)<input id="presetYeast" type="number" min="0" max="20" step="0.001"></label>
        <label class="check"><input id="presetAutolyse" type="checkbox">Autolisi</label>
        <label>Autolisi (minuti)<input id="presetAutolyseMin" type="number" min="0" max="10080" step="1"></label><label class="full">Note<textarea id="presetNotes"></textarea></label>
      </div>
      <h3>Miscela farine preset</h3><div id="presetMix"></div><button type="button" class="secondary" data-add-mix="presetMix">+ Aggiungi farina</button>
      <div id="presetMixSummary" class="mix-summary">Somma mix: --</div>
      <div class="divider"></div>
      <button id="savePresetTop" type="button" class="secondary">Salva preset</button>
    </fieldset>
  </section>

  <section class="panel">
    <h2>Catalogo farine</h2><div class="muted">Caputo è precaricata da schede ufficiali. Italiamo Nuvola resta da completare dalla confezione.</div>
    <fieldset id="flourFieldset"><div id="flourCards" class="cards"></div>
      <div class="toolbar"><button id="newFlour" type="button" class="secondary">Nuova farina</button><button id="deleteFlour" type="button" class="danger">Elimina</button><button id="saveFlour" type="button">Salva farina</button></div>
      <div class="grid">
        <label>ID stabile<input id="flourId" maxlength="48" placeholder="marca-prodotto"></label><label>Marca<input id="flourBrand" maxlength="60"></label><label>Nome<input id="flourName" maxlength="60"></label>
        <label>Tipo<input id="flourType" maxlength="20" placeholder="0 / 00"></label><label>Proteine (%)<input id="flourProtein" type="number" min="0" max="30" step="0.01"></label><label>Verificata<label class="check"><input id="flourVerified" type="checkbox">Dati controllati</label></label>
        <label>W minimo<input id="flourWMin" type="number" min="50" max="700"></label><label>W massimo<input id="flourWMax" type="number" min="50" max="700"></label><span></span>
        <label>P/L minimo<input id="flourPlMin" type="number" min="0" max="5" step="0.01"></label><label>P/L massimo<input id="flourPlMax" type="number" min="0" max="5" step="0.01"></label><label>Fonte URL<input id="flourSource" type="url"></label>
        <label class="full">Note<textarea id="flourNotes"></textarea></label>
      </div>
    </fieldset>
  </section>

  <section class="panel"><h2>Backup</h2><div class="muted">Esporta periodicamente una copia. L’importazione sostituisce catalogo, preset e prossimo impasto dopo averli validati.</div><div class="backup"><a class="back" href="/api/config/export" download="fermentlab-backup.json">Esporta JSON</a><label>Importa JSON<input id="importFile" type="file" accept="application/json,.json"></label></div></section>

  <section class="sticky-actions">
    <div class="left">
      <span id="stickyHint" class="muted">Salva la bozza prima di tornare alla dashboard.</span>
    </div>
    <button id="stickySaveDraft" type="button">Salva bozza adesso</button>
  </section>
</main>
<script>
const $=id=>document.getElementById(id);let floursDoc,presetsDoc,draft,active=false,flourIndex=0,presetIndex=0,draftDirty=false,presetDirty=false;
const num=(id,nullable=false)=>{const v=$(id).value.trim();return v===''&&nullable?null:Number(v)};
const val=v=>v==null?'':v;const slug=s=>s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,48);
function message(text,error=false){const n=$('notice');n.textContent=text;n.className='notice show'+(error?' error':'')}
async function get(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);return r.json()}
async function put(path,data){const r=await fetch(path,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const out=await r.json();if(!r.ok||!out.ok)throw Error(out.message||('HTTP '+r.status));message(out.message);return out}
function flourLabel(id){const f=floursDoc.items.find(x=>x.id===id);return f?(f.brand+' '+f.name):id}
function recipeFrom(prefix){return {reading_interval_s:num(prefix+'Interval'),total_flour_g:num(prefix+'Total'),hydration_pct:num(prefix+'Hydration'),salt_pct:num(prefix+'Salt'),yeast_type:$(prefix+'YeastType').value,yeast_pct:num(prefix+'Yeast'),autolyse:$(prefix+'Autolyse').checked,autolyse_min:num(prefix+'AutolyseMin'),flours:[...$(prefix+'Mix').querySelectorAll('.mix-row')].map(r=>({flour_id:r.querySelector('select').value,pct:Number(r.querySelector('input').value)})),notes:$(prefix+'Notes').value}}
function fillRecipe(prefix,r){$(prefix+'Interval').value=val(r.reading_interval_s??10);$(prefix+'Total').value=val(r.total_flour_g);$(prefix+'Hydration').value=val(r.hydration_pct);$(prefix+'Salt').value=val(r.salt_pct);$(prefix+'YeastType').value=r.yeast_type||'fresh';$(prefix+'Yeast').value=val(r.yeast_pct);$(prefix+'Autolyse').checked=!!r.autolyse;$(prefix+'AutolyseMin').value=val(r.autolyse_min);$(prefix+'Notes').value=r.notes||'';renderMix(prefix+'Mix',r.flours||[])}
function renderMix(containerId,mix){const box=$(containerId);box.innerHTML='';(mix.length?mix:[{flour_id:floursDoc.items[0]?.id||'',pct:100}]).forEach(x=>addMix(containerId,x))}
function mixTotal(containerId){return [...$(containerId).querySelectorAll('.mix-row input')].reduce((sum,input)=>sum+(Number(input.value)||0),0)}
function updateMixSummary(prefix){const total=mixTotal(prefix+'Mix');const summary=$(prefix+'MixSummary');const close=Math.abs(total-100)<=0.2;summary.textContent='Somma mix: '+total.toFixed(1)+'%'+(close?' (ok)':' (atteso 100%)');summary.className='mix-summary'+(close?'':' error');if(prefix==='draft'){updateMixState(close)}}
function addMix(containerId,item={flour_id:floursDoc.items[0]?.id||'',pct:0}){const row=document.createElement('div');row.className='mix-row';const options=floursDoc.items.length?floursDoc.items.map(f=>`<option value="${f.id}">${f.brand} ${f.name}</option>`).join(''):'<option value="">Nessuna farina nel catalogo</option>';row.innerHTML=`<label>Farina<select>${options}</select></label><label>Percentuale<input type="number" min="0.01" max="100" step="0.1" value="${item.pct}"></label><button type="button" class="danger">×</button>`;row.querySelector('select').value=item.flour_id;row.querySelector('button').onclick=()=>{row.remove();if(containerId==='draftMix')markDraftDirty();if(containerId==='presetMix')markPresetDirty();updateMixSummary(containerId==='draftMix'?'draft':'preset')};row.querySelector('input').oninput=()=>{if(containerId==='draftMix')markDraftDirty();if(containerId==='presetMix')markPresetDirty();updateMixSummary(containerId==='draftMix'?'draft':'preset')};row.querySelector('select').onchange=()=>{if(containerId==='draftMix')markDraftDirty();if(containerId==='presetMix')markPresetDirty()};$(containerId).appendChild(row);updateMixSummary(containerId==='draftMix'?'draft':'preset')}
function applyPresetToDraft(showMessage=true){const p=presetsDoc.items.find(x=>x.id===$('draftPreset').value);if(!p){message('Seleziona prima un preset.',true);return false}draft={...draft,...JSON.parse(JSON.stringify(p)),schema:'fermentlab.session-draft.v1',revision:(draft.revision||0)+1,name:draft.name||p.name,preset_id:p.id,initial_dough_mass_g:draft.initial_dough_mass_g??null};renderDraft();markDraftDirty();if(showMessage)message('Preset applicato alla bozza. Salva la bozza per confermare.');return true}
function renderDraft(){ $('draftName').value=draft.name||'';$('draftMass').value=val(draft.initial_dough_mass_g);fillRecipe('draft',draft);$('draftPreset').innerHTML='<option value="">-- scegli --</option>'+presetsDoc.items.map(p=>`<option value="${p.id}">${p.name}</option>`).join('');$('draftPreset').value=draft.preset_id||'';updateSelectedPresetHint();updateMixSummary('draft')}
function refreshPresetSelects(){const options=presetsDoc.items.map((p,i)=>`<option value="${i}">${p.name}</option>`).join('');$('presetSelect').innerHTML=options;$('draftPreset').innerHTML='<option value="">-- scegli --</option>'+presetsDoc.items.map(p=>`<option value="${p.id}">${p.name}</option>`).join('');updateSelectedPresetHint()}
function updateSelectedPresetHint(){const selected=presetsDoc.items.find(x=>x.id===$('draftPreset').value);$('selectedPresetHint').textContent=selected?('Preset selezionato: '+selected.name+' · id '+selected.id):'Nessun preset selezionato: la bozza usa i valori correnti manuali.'}
function editPreset(index){presetIndex=index;const p=presetsDoc.items[index];$('presetId').readOnly=!!p;if(!p){$('presetId').value='';$('presetName').value='';fillRecipe('preset',{reading_interval_s:10,total_flour_g:1000,hydration_pct:65,salt_pct:2.5,yeast_type:'fresh',yeast_pct:.1,autolyse:false,autolyse_min:0,flours:[{flour_id:floursDoc.items[0]?.id,pct:100}],notes:''});return}$('presetSelect').value=index;$('presetId').value=p.id;$('presetName').value=p.name;fillRecipe('preset',p)}
function renderFlours(){const cards=$('flourCards');cards.innerHTML='';floursDoc.items.forEach((f,i)=>{const b=document.createElement('button');b.type='button';b.className='card'+(i===flourIndex?' selected':'');b.innerHTML=`<span class="status-dot ${f.verified?'':'unverified'}"></span>${f.brand} · ${f.name}<small>${f.type?'Tipo '+f.type:'Tipo da inserire'} · ${f.protein_pct==null?'proteine da inserire':f.protein_pct+'% proteine'}</small>`;b.onclick=()=>editFlour(i);cards.appendChild(b)})}
function editFlour(index){flourIndex=index;const f=floursDoc.items[index]||{};$('flourId').value=f.id||'';$('flourBrand').value=f.brand||'';$('flourName').value=f.name||'';$('flourType').value=val(f.type);$('flourProtein').value=val(f.protein_pct);$('flourWMin').value=val(f.w_min);$('flourWMax').value=val(f.w_max);$('flourPlMin').value=val(f.pl_min);$('flourPlMax').value=val(f.pl_max);$('flourNotes').value=f.notes||'';$('flourSource').value=f.source_url||'';$('flourVerified').checked=!!f.verified;renderFlours()}
function setLock(on){active=on;['draftFieldset','presetFieldset','flourFieldset'].forEach(id=>$(id).disabled=on);['newPresetTop','savePresetTop','applyPreset','stickySaveDraft'].forEach(id=>$(id).disabled=on);$('lockText').innerHTML=on?'<span class="lock">Sessione attiva: configurazione bloccata fino allo STOP.</span>':'Questa bozza viene fotografata nella testa del JSONL quando premi START.';$('sessionLockBadge').className='pill '+(on?'warn':'ok');$('sessionLockBadge').textContent=on?'Sessione attiva: modifiche bloccate':'Sessione ferma: modifiche abilitate'}
function updateDraftState(){if(draftDirty){$('draftState').className='pill warn';$('draftState').textContent='Bozza: modifiche non salvate';$('stickyHint').textContent='Hai modifiche in bozza non salvate.'}else{$('draftState').className='pill ok';$('draftState').textContent='Bozza: salvata';$('stickyHint').textContent='Bozza allineata. Puoi tornare alla dashboard.'}}
function updatePresetState(){if(presetDirty){$('presetState').className='pill warn';$('presetState').textContent='Preset: modifiche non salvate'}else{$('presetState').className='pill ok';$('presetState').textContent='Preset: salvato'}}
function updateMixState(ok){$('mixState').className='pill '+(ok?'ok':'warn');$('mixState').textContent=ok?'Mix farine: 100%':'Mix farine: da correggere'}
function markDraftDirty(){draftDirty=true;updateDraftState()}
function markPresetDirty(){presetDirty=true;updatePresetState()}
function validateMix(prefix){const rows=[...$(prefix+'Mix').querySelectorAll('.mix-row')];if(rows.length===0)return {ok:false,error:'Inserisci almeno una farina nel mix.'};const total=mixTotal(prefix+'Mix');if(Math.abs(total-100)>0.2)return {ok:false,error:'La somma delle percentuali del mix deve essere 100% (ora '+total.toFixed(1)+'%).'};return {ok:true}}
async function load(){try{[floursDoc,presetsDoc,draft]=await Promise.all([get('/api/config/flours'),get('/api/config/presets'),get('/api/config/draft')]);refreshPresetSelects();renderDraft();editPreset(0);editFlour(0);const s=await get('/api/status');setLock(s.session_active)}catch(e){message('Caricamento fallito: '+e.message,true)}}
document.querySelectorAll('[data-add-mix]').forEach(b=>b.onclick=()=>{addMix(b.dataset.addMix);if(b.dataset.addMix==='draftMix')markDraftDirty();if(b.dataset.addMix==='presetMix')markPresetDirty()});
$('draftPreset').onchange=()=>{updateSelectedPresetHint()};
$('applyPreset').onclick=()=>{applyPresetToDraft(true)};
$('saveDraft').onclick=async()=>{try{const mixCheck=validateMix('draft');if(!mixCheck.ok)throw Error(mixCheck.error);draft={schema:'fermentlab.session-draft.v1',revision:(draft.revision||0)+1,name:$('draftName').value.trim(),preset_id:$('draftPreset').value||null,initial_dough_mass_g:num('draftMass',true),...recipeFrom('draft')};await put('/api/config/draft',draft);draftDirty=false;updateDraftState()}catch(e){message(e.message,true)}};
$('stickySaveDraft').onclick=()=>$('saveDraft').click();
$('presetSelect').onchange=()=>editPreset(Number($('presetSelect').value));$('newPreset').onclick=()=>{presetIndex=-1;editPreset(-1)};
$('newPresetTop').onclick=()=>$('newPreset').click();
$('savePresetTop').onclick=()=>$('savePreset').click();
$('savePreset').onclick=async()=>{try{const mixCheck=validateMix('preset');if(!mixCheck.ok)throw Error(mixCheck.error);const id=slug($('presetId').value||$('presetName').value);if(!id)throw Error('Inserisci un ID o un nome.');const p={id,name:$('presetName').value.trim(),...recipeFrom('preset')};if(presetIndex<0)presetsDoc.items.push(p);else presetsDoc.items[presetIndex]=p;presetsDoc.revision=(presetsDoc.revision||0)+1;await put('/api/config/presets',presetsDoc);refreshPresetSelects();editPreset(Math.max(0,presetIndex<0?presetsDoc.items.length-1:presetIndex));presetDirty=false;updatePresetState()}catch(e){message(e.message,true)}};
$('deletePreset').onclick=async()=>{if(presetIndex<0||!presetsDoc.items[presetIndex])return;if(!confirm('Eliminare questo preset?'))return;try{presetsDoc.items.splice(presetIndex,1);presetsDoc.revision=(presetsDoc.revision||0)+1;await put('/api/config/presets',presetsDoc);refreshPresetSelects();editPreset(0)}catch(e){message(e.message,true)}};
$('newFlour').onclick=()=>{flourIndex=-1;editFlour(-1)};
$('saveFlour').onclick=async()=>{try{const id=slug($('flourId').value||($('flourBrand').value+' '+$('flourName').value));if(!id)throw Error('Inserisci marca e nome.');const f={id,brand:$('flourBrand').value.trim(),name:$('flourName').value.trim(),type:$('flourType').value.trim()||null,protein_pct:num('flourProtein',true),w_min:num('flourWMin',true),w_max:num('flourWMax',true),pl_min:num('flourPlMin',true),pl_max:num('flourPlMax',true),notes:$('flourNotes').value,source_url:$('flourSource').value.trim(),verified:$('flourVerified').checked};if(flourIndex<0)floursDoc.items.push(f);else floursDoc.items[flourIndex]=f;floursDoc.revision=(floursDoc.revision||0)+1;await put('/api/config/flours',floursDoc);flourIndex=flourIndex<0?floursDoc.items.length-1:flourIndex;renderFlours();editFlour(flourIndex);renderDraft();editPreset(Math.max(0,presetIndex))}catch(e){message(e.message,true)}};
$('deleteFlour').onclick=async()=>{const f=floursDoc.items[flourIndex];if(!f)return;const used=draft.flours?.some(x=>x.flour_id===f.id)||presetsDoc.items.some(p=>p.flours?.some(x=>x.flour_id===f.id));if(used){message('Farina usata da un preset o dal prossimo impasto: sostituiscila prima.',true);return}if(!confirm('Eliminare '+f.brand+' '+f.name+'?'))return;try{floursDoc.items.splice(flourIndex,1);floursDoc.revision=(floursDoc.revision||0)+1;await put('/api/config/flours',floursDoc);flourIndex=0;editFlour(0)}catch(e){message(e.message,true)}};
$('importFile').onchange=async e=>{const file=e.target.files[0];if(!file)return;if(!confirm('Sostituire tutta la configurazione con questo backup?'))return;try{const text=await file.text();const r=await fetch('/api/config/import',{method:'POST',headers:{'Content-Type':'application/json'},body:text});const out=await r.json();if(!out.ok)throw Error(out.message);message(out.message);await load()}catch(err){message('Importazione fallita: '+err.message,true)}finally{e.target.value=''}};
['draftFieldset','presetFieldset'].forEach(id=>$(id).addEventListener('input',e=>{if(id==='draftFieldset')markDraftDirty();else markPresetDirty();if(e.target&&e.target.closest('.mix-row'))updateMixSummary(id==='draftFieldset'?'draft':'preset')}));
['draftFieldset','presetFieldset'].forEach(id=>$(id).addEventListener('change',()=>{if(id==='draftFieldset')markDraftDirty();else markPresetDirty()}));
load().then(()=>{draftDirty=false;presetDirty=false;updateDraftState();updatePresetState();updateMixSummary('draft');updateMixSummary('preset')});
setInterval(async()=>{try{setLock((await get('/api/status')).session_active)}catch(e){}},3000);
</script></body></html>
)HTML";

}  // namespace

WebInterface::WebInterface() : server_(Config::WEB_SERVER_PORT) {}

void WebInterface::configure(JsonHandler statusHandler,
                             JsonHandler testHandler,
                             JsonHandler toggleHandler) {
  statusHandler_ = std::move(statusHandler);
  testHandler_ = std::move(testHandler);
  toggleHandler_ = std::move(toggleHandler);
}

void WebInterface::configureRecipes(JsonHandler floursHandler,
                                    JsonBodyHandler saveFloursHandler,
                                    JsonHandler presetsHandler,
                                    JsonBodyHandler savePresetsHandler,
                                    JsonHandler draftHandler,
                                    JsonBodyHandler saveDraftHandler,
                                    JsonHandler backupHandler,
                                    JsonBodyHandler importHandler) {
  floursHandler_ = std::move(floursHandler);
  saveFloursHandler_ = std::move(saveFloursHandler);
  presetsHandler_ = std::move(presetsHandler);
  savePresetsHandler_ = std::move(savePresetsHandler);
  draftHandler_ = std::move(draftHandler);
  saveDraftHandler_ = std::move(saveDraftHandler);
  backupHandler_ = std::move(backupHandler);
  importHandler_ = std::move(importHandler);
}

bool WebInterface::begin() {
  if (running()) {
    return true;
  }

  const uint32_t now = millis();
  if (static_cast<int32_t>(now - nextStartAttemptMs_) < 0) {
    return false;
  }
  nextStartAttemptMs_ = now + Config::WEB_SERVER_RETRY_INTERVAL_MS;

  configureRoutes();
  server_.begin(Config::WEB_SERVER_PORT);
  if (!server_.listening()) {
    running_ = false;
    mdnsReady_ = false;
    return false;
  }

  MDNS.end();
  mdnsReady_ = MDNS.begin(Config::WEB_HOSTNAME);
  if (mdnsReady_) {
    MDNS.addService("http", "tcp", Config::WEB_SERVER_PORT);
  }
  running_ = true;
  return true;
}

void WebInterface::stop() {
  if (!running_ && !server_.listening()) {
    return;
  }
  server_.close();
  MDNS.end();
  running_ = false;
  mdnsReady_ = false;
}

void WebInterface::tick() {
  if (running_ && !server_.listening()) {
    running_ = false;
    mdnsReady_ = false;
    return;
  }
  if (running_) {
    server_.handleClient();
  }
}

bool WebInterface::running() {
  if (running_ && !server_.listening()) {
    running_ = false;
    mdnsReady_ = false;
  }
  return running_;
}

void WebInterface::configureRoutes() {
  if (routesConfigured_) {
    return;
  }
  server_.on("/", HTTP_GET, [this]() {
    server_.sendHeader("Cache-Control", "no-store");
    server_.send_P(200, "text/html; charset=utf-8", INDEX_HTML);
  });
  server_.on("/config", HTTP_GET, [this]() {
    server_.sendHeader("Cache-Control", "no-store");
    server_.send_P(200, "text/html; charset=utf-8", CONFIG_HTML);
  });
  server_.on("/api/status", HTTP_GET,
             [this]() { sendJson(statusHandler_); });
  server_.on("/api/test", HTTP_POST,
             [this]() { sendJson(testHandler_); });
  server_.on("/api/session/toggle", HTTP_POST,
             [this]() { sendJson(toggleHandler_); });
  server_.on("/api/config/flours", HTTP_GET,
             [this]() { sendJson(floursHandler_); });
  server_.on("/api/config/flours", HTTP_PUT,
             [this]() { sendJsonBody(saveFloursHandler_); });
  server_.on("/api/config/presets", HTTP_GET,
             [this]() { sendJson(presetsHandler_); });
  server_.on("/api/config/presets", HTTP_PUT,
             [this]() { sendJsonBody(savePresetsHandler_); });
  server_.on("/api/config/draft", HTTP_GET,
             [this]() { sendJson(draftHandler_); });
  server_.on("/api/config/draft", HTTP_PUT,
             [this]() { sendJsonBody(saveDraftHandler_); });
  server_.on("/api/config/export", HTTP_GET, [this]() {
    if (!backupHandler_) {
      server_.send(503, "application/json", "{\"error\":\"not_ready\"}");
      return;
    }
    server_.sendHeader("Cache-Control", "no-store");
    server_.sendHeader("Content-Disposition",
                       "attachment; filename=fermentlab-backup.json");
    server_.send(200, "application/json", backupHandler_());
  });
  server_.on("/api/config/import", HTTP_POST,
             [this]() { sendJsonBody(importHandler_); });
  server_.onNotFound([this]() {
    server_.send(404, "application/json", "{\"error\":\"not_found\"}");
  });
  routesConfigured_ = true;
}

void WebInterface::sendJson(const JsonHandler& handler) {
  server_.sendHeader("Cache-Control", "no-store");
  if (!handler) {
    server_.send(503, "application/json", "{\"error\":\"not_ready\"}");
    return;
  }
  server_.send(200, "application/json", handler());
}

void WebInterface::sendJsonBody(const JsonBodyHandler& handler) {
  server_.sendHeader("Cache-Control", "no-store");
  if (!handler) {
    server_.send(503, "application/json", "{\"error\":\"not_ready\"}");
    return;
  }
  const String body = server_.arg("plain");
  if (body.length() == 0) {
    server_.send(400, "application/json",
                 "{\"ok\":false,\"message\":\"Body JSON mancante.\"}");
    return;
  }
  if (body.length() > Config::CONFIG_BACKUP_MAX_BYTES) {
    server_.send(
        413, "application/json",
        "{\"ok\":false,\"message\":\"Body troppo grande per l'ESP32.\"}");
    return;
  }
  server_.send(200, "application/json", handler(body));
}
