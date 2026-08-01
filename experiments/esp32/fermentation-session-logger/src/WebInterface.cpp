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
    .notice{min-height:24px;margin-top:12px;color:var(--amber);font-size:14px}.details{display:grid;grid-template-columns:repeat(2,1fr);gap:8px 20px}.details div{display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid var(--line);padding:8px 0}.details span:first-child{color:var(--muted)}
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
  </section>
  <section class="panel">
    <h2>Ultimo test</h2><div id="testTime" class="muted">Premi “Test lettura” per acquisire un campione.</div>
    <div class="metrics">
      <div class="metric"><span>Temperatura ambiente</span><strong id="temperature">—</strong></div>
      <div class="metric"><span>Umidità</span><strong id="humidity">—</strong></div>
      <div class="metric"><span>Distanza corretta</span><strong id="distance">—</strong></div>
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
    <div><span>Prossimo impasto</span><span id="draftName">—</span></div><div><span>Farina / idratazione</span><span id="draftRecipe">—</span></div>
  </section>
</main>
<script>
  let state=null;
  const $=id=>document.getElementById(id);
  const value=(v,unit,digits=2)=>v==null?'—':Number(v).toFixed(digits)+' '+unit;
  async function api(path,options){const response=await fetch(path,{cache:'no-store',...options});if(!response.ok)throw new Error('HTTP '+response.status);return response.json()}
  function renderStatus(s){state=s;$('connection').textContent='Online';$('connection').className='badge on';$('sessionTitle').textContent=s.session_active?'Sessione attiva':'Sessione ferma';$('sessionId').textContent=s.session_active?s.session_id:'Nessuna sessione attiva';$('toggleButton').textContent=s.session_active?'STOP':'START';$('toggleButton').className=s.session_active?'toggle stop':'toggle';$('time').textContent=s.timestamp||'Ora non sincronizzata';$('device').textContent=s.device_id;$('ip').textContent=s.ip;$('rssi').textContent=s.rssi_dbm+' dBm';$('uptime').textContent=Math.floor(s.uptime_s/60)+' min';$('interval').textContent=s.reading_interval_s+' s';$('measurements').textContent=s.session_measurements;$('nextReading').textContent=s.next_reading_in_s==null?'—':s.next_reading_in_s+' s';$('lastMeasurement').textContent=s.last_measurement_at||'—';$('queue').textContent=s.queue_records+' letture / '+s.queue_segments+' segmenti / '+s.queue_bytes+' B';$('clock').textContent=s.time_valid?'Sincronizzato':'In attesa NTP';$('sensors').textContent=(s.distance_sensor_ready?'VL53 ✓':'VL53 ✕')+' / '+(s.ambient_sensor_ready?'SHT3x ✓':'SHT3x ✕');$('storage').textContent=(s.storage_ready?'LittleFS ✓':'LittleFS ✕')+' / '+(s.telemetry_queue_ready?'Coda ✓':'Coda ✕');$('draftName').textContent=s.draft_name||'—';$('draftRecipe').textContent=(s.draft_flours||'—')+(s.draft_hydration_pct==null?'':' / '+s.draft_hydration_pct+'%')}
  function renderTest(t){$('testTime').textContent=t.timestamp||'Timestamp non disponibile';$('temperature').textContent=value(t.ambient_temperature_c,'°C');$('humidity').textContent=value(t.humidity_pct,'%');$('distance').textContent=value(t.distance_corrected_mm,'mm',3);$('distanceStatus').textContent=t.distance_status}
  async function refresh(){try{renderStatus(await api('/api/status'))}catch(e){$('connection').textContent='Offline';$('connection').className='badge';$('notice').textContent='ESP32 non raggiungibile: '+e.message}}
  $('testButton').addEventListener('click',async()=>{const b=$('testButton');b.disabled=true;$('notice').textContent='Acquisizione in corso...';try{renderTest(await api('/api/test',{method:'POST'}));$('notice').textContent='Campione acquisito senza salvataggio.'}catch(e){$('notice').textContent='Test fallito: '+e.message}finally{b.disabled=false}});
  $('toggleButton').addEventListener('click',async()=>{const b=$('toggleButton'),before=state&&state.session_active;b.disabled=true;$('notice').textContent='Operazione in corso...';try{const next=await api('/api/session/toggle',{method:'POST'});renderStatus(next);$('notice').textContent=next.session_active===before?(next.start_blocker||'Comando non eseguito.'):(next.session_active?'Sessione avviata.':'Sessione terminata e salvata.')}catch(e){$('notice').textContent='Comando fallito: '+e.message}finally{b.disabled=false}});
  refresh();setInterval(refresh,2500);
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
  <title>Impasto e farine · FermentLab</title>
  <style>
    :root{color-scheme:dark;--bg:#101714;--panel:#18231e;--line:#2b3c33;--text:#f3f7f4;--muted:#a9b8af;--green:#52d68a;--red:#ff6b6b;--amber:#ffc857}
    *{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#20372b 0,var(--bg) 48%);color:var(--text);font:15px/1.45 system-ui,sans-serif;min-height:100vh}
    main{width:min(980px,calc(100% - 28px));margin:auto;padding:26px 0 60px}header{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:20px}h1{font-size:clamp(28px,6vw,44px);margin:0;letter-spacing:-.04em}h2{margin:0 0 5px}h3{margin:18px 0 8px}.eyebrow{color:var(--green);font-size:12px;font-weight:800;letter-spacing:.15em;text-transform:uppercase}
    .panel{background:rgba(24,35,30,.94);border:1px solid var(--line);border-radius:20px;padding:20px;margin-bottom:16px;box-shadow:0 18px 50px #0004}.muted{color:var(--muted);font-size:13px}.notice{position:sticky;top:8px;z-index:5;border:1px solid #705d25;background:#332b16;border-radius:12px;padding:10px 13px;margin-bottom:14px;display:none}.notice.show{display:block}.notice.error{border-color:#873e3e;background:#351d1d}.lock{color:var(--amber);font-weight:700}
    a,button{font:inherit;font-weight:750}a.back{color:var(--text);border:1px solid var(--line);border-radius:12px;padding:10px 13px;text-decoration:none}button{border:0;border-radius:11px;background:var(--green);color:#102017;padding:10px 13px;cursor:pointer}button.secondary{background:#e8efe9;color:#152019}button.danger{background:var(--red);color:#2b0d0d}button:disabled,input:disabled,select:disabled,textarea:disabled{opacity:.48;cursor:not-allowed}
    .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.span2{grid-column:span 2}.full{grid-column:1/-1}label{display:block;color:var(--muted);font-size:12px;font-weight:700}input,select,textarea{display:block;width:100%;margin-top:5px;border:1px solid var(--line);border-radius:10px;background:#101814;color:var(--text);font:inherit;padding:10px}textarea{min-height:78px;resize:vertical}.check{display:flex;align-items:center;gap:8px;margin-top:22px;color:var(--text);font-size:14px}.check input{width:auto;margin:0}
    .toolbar{display:flex;flex-wrap:wrap;align-items:end;gap:9px;margin:14px 0}.toolbar .grow{flex:1;min-width:210px}.mix-row{display:grid;grid-template-columns:1fr 130px auto;gap:8px;align-items:end;margin-bottom:8px}.mix-row button{padding:10px 12px}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:13px 0}.card{border:1px solid var(--line);border-radius:12px;background:#101814;padding:12px;text-align:left;color:var(--text)}.card.selected{border-color:var(--green)}.card small{display:block;color:var(--muted);margin-top:3px}.status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--green);margin-right:5px}.status-dot.unverified{background:var(--amber)}fieldset{border:0;padding:0;margin:0}.backup{display:flex;flex-wrap:wrap;gap:9px;margin-top:14px}.backup label{border:1px solid var(--line);border-radius:11px;padding:10px 13px;color:var(--text);cursor:pointer}.backup input{display:none}
    @media(max-width:720px){header{align-items:flex-start;flex-direction:column}.grid{grid-template-columns:1fr 1fr}.cards{grid-template-columns:1fr}.span2{grid-column:span 2}}@media(max-width:480px){.grid{grid-template-columns:1fr}.span2{grid-column:auto}.mix-row{grid-template-columns:1fr 90px auto}}
  </style>
</head>
<body><main>
  <header><div><div class="eyebrow">Configurazione locale</div><h1>Impasto e farine</h1><div class="muted">I dati restano nella memoria LittleFS dell’ESP32.</div></div><a class="back" href="/">← Dashboard</a></header>
  <div id="notice" class="notice"></div>

  <section class="panel">
    <h2>Prossimo impasto</h2><div id="lockText" class="muted">Questa configurazione verrà fotografata nella testa del JSONL allo START.</div>
    <fieldset id="draftFieldset">
      <div class="toolbar"><label class="grow">Applica un preset<select id="draftPreset"></select></label><button id="applyPreset" type="button" class="secondary">Applica</button><button id="saveDraft" type="button">Salva prossimo impasto</button></div>
      <div class="grid">
        <label class="span2">Nome impasto<input id="draftName" maxlength="80"></label><label>Farina totale (g)<input id="draftTotal" type="number" min="1" step="1"></label>
        <label>Idratazione (%)<input id="draftHydration" type="number" min="0" max="200" step="0.1"></label><label>Sale (%)<input id="draftSalt" type="number" min="0" max="20" step="0.01"></label><label>Massa iniziale impasto (g, facoltativa)<input id="draftMass" type="number" min="1" step="1"></label>
        <label>Tipo lievito<select id="draftYeastType"><option value="fresh">Fresco</option><option value="dry">Secco</option><option value="sourdough">Lievito madre</option><option value="none">Nessuno</option></select></label><label>Lievito (%)<input id="draftYeast" type="number" min="0" max="20" step="0.001"></label><label class="check"><input id="draftAutolyse" type="checkbox">Autolisi</label>
        <label>Autolisi (minuti)<input id="draftAutolyseMin" type="number" min="0" max="10080" step="1"></label><label class="full">Note<textarea id="draftNotes"></textarea></label>
      </div>
      <h3>Miscela farine</h3><div id="draftMix"></div><button type="button" class="secondary" data-add-mix="draftMix">+ Aggiungi farina</button>
    </fieldset>
  </section>

  <section class="panel">
    <h2>Preset</h2><div class="muted">Ricette riutilizzabili: applicandone una, i valori vengono copiati nel prossimo impasto.</div>
    <fieldset id="presetFieldset">
      <div class="toolbar"><label class="grow">Preset da modificare<select id="presetSelect"></select></label><button id="newPreset" type="button" class="secondary">Nuovo</button><button id="deletePreset" type="button" class="danger">Elimina</button><button id="savePreset" type="button">Salva preset</button></div>
      <div class="grid">
        <label>ID stabile<input id="presetId" maxlength="48" placeholder="mia-ricetta"></label><label class="span2">Nome<input id="presetName" maxlength="80"></label>
        <label>Farina totale (g)<input id="presetTotal" type="number" min="1" step="1"></label><label>Idratazione (%)<input id="presetHydration" type="number" min="0" max="200" step="0.1"></label><label>Sale (%)<input id="presetSalt" type="number" min="0" max="20" step="0.01"></label>
        <label>Tipo lievito<select id="presetYeastType"><option value="fresh">Fresco</option><option value="dry">Secco</option><option value="sourdough">Lievito madre</option><option value="none">Nessuno</option></select></label><label>Lievito (%)<input id="presetYeast" type="number" min="0" max="20" step="0.001"></label><label class="check"><input id="presetAutolyse" type="checkbox">Autolisi</label>
        <label>Autolisi (minuti)<input id="presetAutolyseMin" type="number" min="0" max="10080" step="1"></label><label class="full">Note<textarea id="presetNotes"></textarea></label>
      </div>
      <h3>Miscela farine</h3><div id="presetMix"></div><button type="button" class="secondary" data-add-mix="presetMix">+ Aggiungi farina</button>
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
</main>
<script>
const $=id=>document.getElementById(id);let floursDoc,presetsDoc,draft,active=false,flourIndex=0,presetIndex=0;
const num=(id,nullable=false)=>{const v=$(id).value.trim();return v===''&&nullable?null:Number(v)};
const val=v=>v==null?'':v;const slug=s=>s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,48);
function message(text,error=false){const n=$('notice');n.textContent=text;n.className='notice show'+(error?' error':'');clearTimeout(message.timer);message.timer=setTimeout(()=>n.className='notice',5000)}
async function get(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);return r.json()}
async function put(path,data){const r=await fetch(path,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const out=await r.json();if(!r.ok||!out.ok)throw Error(out.message||('HTTP '+r.status));message(out.message);return out}
function flourLabel(id){const f=floursDoc.items.find(x=>x.id===id);return f?(f.brand+' '+f.name):id}
function recipeFrom(prefix){return {total_flour_g:num(prefix+'Total'),hydration_pct:num(prefix+'Hydration'),salt_pct:num(prefix+'Salt'),yeast_type:$(prefix+'YeastType').value,yeast_pct:num(prefix+'Yeast'),autolyse:$(prefix+'Autolyse').checked,autolyse_min:num(prefix+'AutolyseMin'),flours:[...$(prefix+'Mix').querySelectorAll('.mix-row')].map(r=>({flour_id:r.querySelector('select').value,pct:Number(r.querySelector('input').value)})),notes:$(prefix+'Notes').value}}
function fillRecipe(prefix,r){$(prefix+'Total').value=val(r.total_flour_g);$(prefix+'Hydration').value=val(r.hydration_pct);$(prefix+'Salt').value=val(r.salt_pct);$(prefix+'YeastType').value=r.yeast_type||'fresh';$(prefix+'Yeast').value=val(r.yeast_pct);$(prefix+'Autolyse').checked=!!r.autolyse;$(prefix+'AutolyseMin').value=val(r.autolyse_min);$(prefix+'Notes').value=r.notes||'';renderMix(prefix+'Mix',r.flours||[])}
function renderMix(containerId,mix){const box=$(containerId);box.innerHTML='';(mix.length?mix:[{flour_id:floursDoc.items[0]?.id||'',pct:100}]).forEach(x=>addMix(containerId,x))}
function addMix(containerId,item={flour_id:floursDoc.items[0]?.id||'',pct:0}){const row=document.createElement('div');row.className='mix-row';const options=floursDoc.items.map(f=>`<option value="${f.id}">${f.brand} ${f.name}</option>`).join('');row.innerHTML=`<label>Farina<select>${options}</select></label><label>Percentuale<input type="number" min="0.01" max="100" step="0.1" value="${item.pct}"></label><button type="button" class="danger">×</button>`;row.querySelector('select').value=item.flour_id;row.querySelector('button').onclick=()=>row.remove();$(containerId).appendChild(row)}
function renderDraft(){ $('draftName').value=draft.name||'';$('draftMass').value=val(draft.initial_dough_mass_g);fillRecipe('draft',draft);$('draftPreset').innerHTML='<option value="">— scegli —</option>'+presetsDoc.items.map(p=>`<option value="${p.id}">${p.name}</option>`).join('');$('draftPreset').value=draft.preset_id||''}
function refreshPresetSelects(){const options=presetsDoc.items.map((p,i)=>`<option value="${i}">${p.name}</option>`).join('');$('presetSelect').innerHTML=options;$('draftPreset').innerHTML='<option value="">— scegli —</option>'+presetsDoc.items.map(p=>`<option value="${p.id}">${p.name}</option>`).join('')}
function editPreset(index){presetIndex=index;const p=presetsDoc.items[index];if(!p){$('presetId').value='';$('presetName').value='';fillRecipe('preset',{total_flour_g:1000,hydration_pct:65,salt_pct:2.5,yeast_type:'fresh',yeast_pct:.1,autolyse:false,autolyse_min:0,flours:[{flour_id:floursDoc.items[0]?.id,pct:100}],notes:''});return}$('presetSelect').value=index;$('presetId').value=p.id;$('presetName').value=p.name;fillRecipe('preset',p)}
function renderFlours(){const cards=$('flourCards');cards.innerHTML='';floursDoc.items.forEach((f,i)=>{const b=document.createElement('button');b.type='button';b.className='card'+(i===flourIndex?' selected':'');b.innerHTML=`<span class="status-dot ${f.verified?'':'unverified'}"></span>${f.brand} · ${f.name}<small>${f.type?'Tipo '+f.type:'Tipo da inserire'} · ${f.protein_pct==null?'proteine da inserire':f.protein_pct+'% proteine'}</small>`;b.onclick=()=>editFlour(i);cards.appendChild(b)})}
function editFlour(index){flourIndex=index;const f=floursDoc.items[index]||{};$('flourId').value=f.id||'';$('flourBrand').value=f.brand||'';$('flourName').value=f.name||'';$('flourType').value=val(f.type);$('flourProtein').value=val(f.protein_pct);$('flourWMin').value=val(f.w_min);$('flourWMax').value=val(f.w_max);$('flourPlMin').value=val(f.pl_min);$('flourPlMax').value=val(f.pl_max);$('flourNotes').value=f.notes||'';$('flourSource').value=f.source_url||'';$('flourVerified').checked=!!f.verified;renderFlours()}
function setLock(on){active=on;['draftFieldset','presetFieldset','flourFieldset'].forEach(id=>$(id).disabled=on);$('lockText').innerHTML=on?'<span class="lock">Sessione attiva: configurazione bloccata fino allo STOP.</span>':'Questa configurazione verrà fotografata nella testa del JSONL allo START.'}
async function load(){try{[floursDoc,presetsDoc,draft]=await Promise.all([get('/api/config/flours'),get('/api/config/presets'),get('/api/config/draft')]);refreshPresetSelects();renderDraft();editPreset(0);editFlour(0);const s=await get('/api/status');setLock(s.session_active)}catch(e){message('Caricamento fallito: '+e.message,true)}}
document.querySelectorAll('[data-add-mix]').forEach(b=>b.onclick=()=>addMix(b.dataset.addMix));
$('applyPreset').onclick=()=>{const p=presetsDoc.items.find(x=>x.id===$('draftPreset').value);if(!p)return;draft={...draft,...JSON.parse(JSON.stringify(p)),schema:'fermentlab.session-draft.v1',revision:(draft.revision||0)+1,name:draft.name||p.name,preset_id:p.id,initial_dough_mass_g:draft.initial_dough_mass_g??null};renderDraft();message('Preset copiato. Premi “Salva prossimo impasto”.')};
$('saveDraft').onclick=async()=>{try{draft={schema:'fermentlab.session-draft.v1',revision:(draft.revision||0)+1,name:$('draftName').value.trim(),preset_id:$('draftPreset').value||null,initial_dough_mass_g:num('draftMass',true),...recipeFrom('draft')};await put('/api/config/draft',draft)}catch(e){message(e.message,true)}};
$('presetSelect').onchange=()=>editPreset(Number($('presetSelect').value));$('newPreset').onclick=()=>{presetIndex=-1;editPreset(-1)};
$('savePreset').onclick=async()=>{try{const id=slug($('presetId').value||$('presetName').value);if(!id)throw Error('Inserisci un ID o un nome.');const p={id,name:$('presetName').value.trim(),...recipeFrom('preset')};if(presetIndex<0)presetsDoc.items.push(p);else presetsDoc.items[presetIndex]=p;presetsDoc.revision=(presetsDoc.revision||0)+1;await put('/api/config/presets',presetsDoc);refreshPresetSelects();editPreset(Math.max(0,presetIndex<0?presetsDoc.items.length-1:presetIndex))}catch(e){message(e.message,true)}};
$('deletePreset').onclick=async()=>{if(presetIndex<0||!presetsDoc.items[presetIndex])return;if(!confirm('Eliminare questo preset?'))return;try{presetsDoc.items.splice(presetIndex,1);presetsDoc.revision=(presetsDoc.revision||0)+1;await put('/api/config/presets',presetsDoc);refreshPresetSelects();editPreset(0)}catch(e){message(e.message,true)}};
$('newFlour').onclick=()=>{flourIndex=-1;editFlour(-1)};
$('saveFlour').onclick=async()=>{try{const id=slug($('flourId').value||($('flourBrand').value+' '+$('flourName').value));if(!id)throw Error('Inserisci marca e nome.');const f={id,brand:$('flourBrand').value.trim(),name:$('flourName').value.trim(),type:$('flourType').value.trim()||null,protein_pct:num('flourProtein',true),w_min:num('flourWMin',true),w_max:num('flourWMax',true),pl_min:num('flourPlMin',true),pl_max:num('flourPlMax',true),notes:$('flourNotes').value,source_url:$('flourSource').value.trim(),verified:$('flourVerified').checked};if(flourIndex<0)floursDoc.items.push(f);else floursDoc.items[flourIndex]=f;floursDoc.revision=(floursDoc.revision||0)+1;await put('/api/config/flours',floursDoc);flourIndex=flourIndex<0?floursDoc.items.length-1:flourIndex;renderFlours();editFlour(flourIndex);renderDraft();editPreset(Math.max(0,presetIndex))}catch(e){message(e.message,true)}};
$('deleteFlour').onclick=async()=>{const f=floursDoc.items[flourIndex];if(!f)return;const used=draft.flours?.some(x=>x.flour_id===f.id)||presetsDoc.items.some(p=>p.flours?.some(x=>x.flour_id===f.id));if(used){message('Farina usata da un preset o dal prossimo impasto: sostituiscila prima.',true);return}if(!confirm('Eliminare '+f.brand+' '+f.name+'?'))return;try{floursDoc.items.splice(flourIndex,1);floursDoc.revision=(floursDoc.revision||0)+1;await put('/api/config/flours',floursDoc);flourIndex=0;editFlour(0)}catch(e){message(e.message,true)}};
$('importFile').onchange=async e=>{const file=e.target.files[0];if(!file)return;if(!confirm('Sostituire tutta la configurazione con questo backup?'))return;try{const text=await file.text();const r=await fetch('/api/config/import',{method:'POST',headers:{'Content-Type':'application/json'},body:text});const out=await r.json();if(!out.ok)throw Error(out.message);message(out.message);await load()}catch(err){message('Importazione fallita: '+err.message,true)}finally{e.target.value=''}};
load();setInterval(async()=>{try{setLock((await get('/api/status')).session_active)}catch(e){}},3000);
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
  if (running_) {
    return true;
  }
  configureRoutes();
  server_.begin();
  const bool mdnsReady = MDNS.begin(Config::WEB_HOSTNAME);
  if (mdnsReady) {
    MDNS.addService("http", "tcp", Config::WEB_SERVER_PORT);
  }
  running_ = true;
  return mdnsReady;
}

void WebInterface::stop() {
  if (!running_) {
    return;
  }
  server_.close();
  MDNS.end();
  running_ = false;
}

void WebInterface::tick() {
  if (running_) {
    server_.handleClient();
  }
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
  server_.send(200, "application/json", handler(server_.arg("plain")));
}
