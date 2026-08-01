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
    .metrics{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:16px}.metric{background:#101814;border:1px solid var(--line);border-radius:14px;padding:14px}.metric span{display:block;color:var(--muted);font-size:12px}.metric strong{display:block;font-size:21px;margin-top:4px}
    .notice{min-height:24px;margin-top:12px;color:var(--amber);font-size:14px}.details{display:grid;grid-template-columns:repeat(2,1fr);gap:8px 20px}.details div{display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid var(--line);padding:8px 0}.details span:first-child{color:var(--muted)}
    @media(max-width:540px){header,.session{align-items:flex-start;flex-direction:column}.actions,.metrics,.details{grid-template-columns:1fr}.badge{align-self:flex-start}}
  </style>
</head>
<body>
<main>
  <header><div><div class="eyebrow">ESP32 local control</div><h1>FermentLab</h1></div><div id="connection" class="badge">Connessione...</div></header>
  <section class="panel">
    <div class="session"><div><h2 id="sessionTitle">Sessione ferma</h2><div id="sessionId" class="muted">Nessuna sessione attiva</div></div><div id="time" class="muted"></div></div>
    <div class="actions"><button id="testButton" class="test">Test lettura</button><button id="toggleButton" class="toggle">START</button></div>
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
  </section>
</main>
<script>
  let state=null;
  const $=id=>document.getElementById(id);
  const value=(v,unit,digits=2)=>v==null?'—':Number(v).toFixed(digits)+' '+unit;
  async function api(path,options){const response=await fetch(path,{cache:'no-store',...options});if(!response.ok)throw new Error('HTTP '+response.status);return response.json()}
  function renderStatus(s){state=s;$('connection').textContent='Online';$('connection').className='badge on';$('sessionTitle').textContent=s.session_active?'Sessione attiva':'Sessione ferma';$('sessionId').textContent=s.session_active?s.session_id:'Nessuna sessione attiva';$('toggleButton').textContent=s.session_active?'STOP':'START';$('toggleButton').className=s.session_active?'toggle stop':'toggle';$('time').textContent=s.timestamp||'Ora non sincronizzata';$('device').textContent=s.device_id;$('ip').textContent=s.ip;$('rssi').textContent=s.rssi_dbm+' dBm';$('uptime').textContent=Math.floor(s.uptime_s/60)+' min';$('interval').textContent=s.reading_interval_s+' s';$('measurements').textContent=s.session_measurements;$('nextReading').textContent=s.next_reading_in_s==null?'—':s.next_reading_in_s+' s';$('lastMeasurement').textContent=s.last_measurement_at||'—';$('queue').textContent=s.queue_records+' letture / '+s.queue_segments+' segmenti / '+s.queue_bytes+' B';$('clock').textContent=s.time_valid?'Sincronizzato':'In attesa NTP';$('sensors').textContent=(s.distance_sensor_ready?'VL53 ✓':'VL53 ✕')+' / '+(s.ambient_sensor_ready?'SHT3x ✓':'SHT3x ✕');$('storage').textContent=(s.storage_ready?'LittleFS ✓':'LittleFS ✕')+' / '+(s.telemetry_queue_ready?'Coda ✓':'Coda ✕')}
  function renderTest(t){$('testTime').textContent=t.timestamp||'Timestamp non disponibile';$('temperature').textContent=value(t.ambient_temperature_c,'°C');$('humidity').textContent=value(t.humidity_pct,'%');$('distance').textContent=value(t.distance_corrected_mm,'mm',3);$('distanceStatus').textContent=t.distance_status}
  async function refresh(){try{renderStatus(await api('/api/status'))}catch(e){$('connection').textContent='Offline';$('connection').className='badge';$('notice').textContent='ESP32 non raggiungibile: '+e.message}}
  $('testButton').addEventListener('click',async()=>{const b=$('testButton');b.disabled=true;$('notice').textContent='Acquisizione in corso...';try{renderTest(await api('/api/test',{method:'POST'}));$('notice').textContent='Campione acquisito senza salvataggio.'}catch(e){$('notice').textContent='Test fallito: '+e.message}finally{b.disabled=false}});
  $('toggleButton').addEventListener('click',async()=>{const b=$('toggleButton'),before=state&&state.session_active;b.disabled=true;$('notice').textContent='Operazione in corso...';try{const next=await api('/api/session/toggle',{method:'POST'});renderStatus(next);$('notice').textContent=next.session_active===before?(next.start_blocker||'Comando non eseguito.'):(next.session_active?'Sessione avviata.':'Sessione terminata e salvata.')}catch(e){$('notice').textContent='Comando fallito: '+e.message}finally{b.disabled=false}});
  refresh();setInterval(refresh,2500);
</script>
</body>
</html>
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
  server_.on("/api/status", HTTP_GET,
             [this]() { sendJson(statusHandler_); });
  server_.on("/api/test", HTTP_POST,
             [this]() { sendJson(testHandler_); });
  server_.on("/api/session/toggle", HTTP_POST,
             [this]() { sendJson(toggleHandler_); });
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
