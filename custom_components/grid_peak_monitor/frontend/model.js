// Presentation helpers only. Authoritative live calculations come from HA.
export const number = value => value == null || value === '' || typeof value === 'boolean' || !Number.isFinite(Number(value)) ? null : Number(value);
export const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const fmt = (value, digits = 2) => number(value) == null ? '—' : new Intl.NumberFormat('de-AT', {minimumFractionDigits:digits, maximumFractionDigits:digits}).format(Number(value));
export const dayAt = (seconds, zone) => new Intl.DateTimeFormat('sv-SE', {timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(seconds * 1000));
export const timeAt = (seconds, zone, offset=false) => new Intl.DateTimeFormat('de-AT', {timeZone:zone,hour:'2-digit',minute:'2-digit', ...(offset ? {timeZoneName:'shortOffset'} : {})}).format(new Date(seconds * 1000));
export const statusText = {no_data:'Messwerte prüfen',exceeded:'Bereits überschritten',reached:'Ziel erreicht',risk:'Spitze droht',checking:'Prüfung läuft',near:'Wenig Spielraum',below:'Unter dem Ziel'};
export const qualityText = {legacy_boundary:'Intervall aus älterer Testversion nicht verlässlich',valid:'Gültige lokale Schätzung',power_stale:'Netzleistung fehlt oder ist veraltet',counter_stalled:'Importzähler steht trotz Netzbezug still',energy_stale:'Importzähler fehlt oder ist veraltet',waiting_boundary:'Erste vollständige Viertelstunde abwarten',waiting_report:'Neuen Zählerbericht abwarten',energy_invalid:'Ungültiger Importzähler',counter_reset:'Zählerstand ist zurückgesprungen',conflicting_report:'Widersprüchlicher Zählerbericht',energy_gap:'Lücke in der Energiequelle',energy_jump:'Unplausibler Zählersprung'};

export function targetControl(states, monitorId) {
  if (!monitorId) return null;
  const matches=Object.entries(states||{}).filter(([id,s])=>/^number\.[a-z0-9_]+$/.test(id)
    &&s?.attributes?.grid_peak_target===true&&s.attributes.monitor_id===monitorId
    &&s.attributes.metric==='target_kw'&&s.attributes.unit_of_measurement==='kW');
  if(matches.length!==1)return null;
  const [entity_id,state]=matches[0],a=state.attributes;
  const current=number(state.state),min=Math.max(.1,number(a.min)??.1),max=Math.min(1000,number(a.max)??1000),step=number(a.step)??.1;
  return current!=null&&min<=max&&step>0?{entity_id,current,min,max,step}:null;
}

export function targetValue(text, control) {
  if(!control||typeof text!=='string'||!/^\d+(?:[.,]\d+)?$/.test(text.trim()))return null;
  const value=Number(text.trim().replace(',','.'));
  if(!Number.isFinite(value)||value<control.min||value>control.max)return null;
  const steps=(value-control.min)/control.step;
  return Math.abs(steps-Math.round(steps))<1e-7?value:null;
}

export function mergeRows(local, portal, selected, zone) {
  const rows = new Map(local.map(row => [row.start, {...row}]));
  for (const row of portal || []) {
    const start = row.utc ? Date.parse(row.utc) / 1000 : number(row.start);
    const kw = number(row.kw);
    if (!Number.isFinite(start) || start % 900 || kw == null || kw < 0 || dayAt(start, zone) !== selected) continue;
    if (!rows.has(start)) continue;
    rows.set(start, {start, end:start+900, kw, quality:'valid',source:'Netz NÖ'});
  }
  return [...rows.values()].sort((a,b)=>a.start-b.start);
}

export function normalizeConfig(config) {
  if (!config || typeof config.entity !== 'string' || !/^sensor\.[a-z0-9_]+$/.test(config.entity)) throw new Error('Wähle den Prognose-Sensor von Grid Peak Monitor.');
  if (config.devices != null && (!Array.isArray(config.devices) || config.devices.some(id=>typeof id!=='string'||!/^sensor\.[a-z0-9_]+$/.test(id)))) throw new Error('devices muss eine Liste von sensor.-IDs sein.');
  return {...config, title:typeof config.title==='string'?config.title:'Netzspitzen im Blick', view:['overview','history','devices','reel'].includes(config.view)?config.view:'overview',devices:config.devices||[]};
}
