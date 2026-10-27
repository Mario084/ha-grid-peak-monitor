import {number, escape, fmt, dayAt, timeAt, statusText, qualityText, mergeRows, normalizeConfig, targetControl, targetValue} from './model.js';

const css = `
[data-target-form]{margin-top:10px}[data-target-form] label{display:block;font-size:13px;color:#bfcdc8}[data-target-value]{display:block;width:100%;min-width:0;margin:5px 0 8px;background:#182729;color:#f3eee3;border:1px solid #78918a;border-radius:8px;padding:8px}.target-actions{display:flex;gap:6px;flex-wrap:wrap}button:disabled,input:disabled{opacity:.6;cursor:wait}
:host{display:block;color:var(--primary-text-color,#f3eee3);font:16px/1.45 system-ui,sans-serif}*{box-sizing:border-box}ha-card{display:block;background:#182729;color:#f3eee3;border-radius:18px;overflow:hidden}.wrap{padding:22px;min-width:0}h1{font-size:25px;margin:2px 0 15px;letter-spacing:-.025em}h2{font-size:17px;margin:0 0 10px}p{margin:7px 0}.muted{color:#bfcdc8;font-size:13px}.cap{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#e6b971;font-weight:750}.panel{background:#223839;border:1px solid #607672;border-radius:14px;padding:16px;margin:10px 0}.hero .value{font-size:clamp(50px,8vw,86px);font-weight:750;letter-spacing:-.04em;line-height:1.15;color:#e6b971}.hero .value small{font-size:.4em}.status{color:#e6b971;font-weight:700}.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.stats .panel{margin:0}.metric{font-size:24px;font-weight:700;overflow-wrap:anywhere}.budget{display:flex;gap:22px;flex-wrap:wrap}.budget strong{color:#e6b971}.tabs,.tools{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin:10px 0}button,input,select{font:inherit}button{border:1px solid #78918a;background:#223839;color:#f3eee3;padding:7px 11px;border-radius:8px;cursor:pointer}button.active{background:#e6b971;color:#182729;border-color:#e6b971}button:focus-visible,input:focus-visible{outline:3px solid #e6b971;outline-offset:3px}input[type=date]{max-width:100%;min-width:0;background:#182729;color:#f3eee3;border:1px solid #78918a;border-radius:8px;padding:7px;color-scheme:dark}.chart{overflow:hidden}.plot{position:relative;display:flex;height:160px;align-items:end;border-bottom:1px solid #78918a;gap:1px}.slot{flex:1;min-width:0;height:100%;display:flex;align-items:end;position:relative}.slot i{width:100%;background:#5fbab2;min-height:2px;display:block}.slot.portal i{background:#72a9e9}.slot button{position:absolute;inset:0;width:100%;padding:0;background:transparent;border:0;border-radius:0}.slot button:focus-visible{outline:2px solid #e6b971;z-index:2}.axis{display:flex;justify-content:space-between;color:#bfcdc8;font-size:11px;margin-top:6px}.legend{font-size:12px;color:#bfcdc8;margin-top:10px}.legend span{white-space:nowrap;margin-right:15px}.legend b{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;background:#5fbab2}.legend .portal{background:#72a9e9}.row{display:flex;justify-content:space-between;gap:10px;padding:9px 0;border-bottom:1px solid #49625c;align-items:center}.row:last-child{border:0}.row small{color:#bfcdc8}.top{width:100%;text-align:left;border:0;border-bottom:1px solid #49625c;border-radius:0;padding:9px 0}.top span{display:block;font-size:12px;color:#bfcdc8}.error{border-color:#d49b75}.reel{aspect-ratio:9/16;max-width:500px;margin:auto;display:flex;flex-direction:column;justify-content:center}.reel .stats{grid-template-columns:1fr}.empty{padding:22px;color:#bfcdc8}.day-grid{display:flex;align-items:end;gap:3px;height:80px}.day-grid button{padding:0;flex:1;min-width:2px;background:#5fbab2;border-radius:3px 3px 0 0}.day-grid button.partial{opacity:.45}a{color:#e6b971}@media(max-width:620px){.wrap{padding:13px}.stats{grid-template-columns:1fr}.stats .panel{padding:12px}.hero .value{font-size:58px}.tools{font-size:13px}h1{font-size:23px}.panel{padding:12px}.budget{gap:10px}.plot{height:135px}}
`;

class GridPeakCard extends HTMLElement {
  constructor(){super();this.attachShadow({mode:'open'});this._history=null;this._portal=null;this._seq=0;this._lastFetch=0;this._targetSeq=0;}
  setConfig(config){this._config=normalizeConfig(config);this._view=this._config.view;this._date=null;this._manualDate=false;this._history=null;this._lastFetch=0;this._seq++;this._loading=null;this._targetSeq++;this._targetEditing=false;this._targetSaving=false;this._targetNotice=null;this.render();if(this._hass)this.loadHistory();}
  set hass(hass){this._hass=hass;if(!this._config)return;this._zone=hass.config?.time_zone||'Europe/Vienna';const today=dayAt(Date.now()/1000,this._zone);if(!this._manualDate&&this._date!==today){this._date=today;this._history=null;this._detail=null;}this.render();this.loadHistory();}
  getCardSize(){return this._view==='reel'?9:8;}
  static async getConfigElement(){return document.createElement('grid-peak-card-editor');}
  static getStubConfig(hass){const entity=Object.keys(hass.states).find(id=>hass.states[id].attributes?.grid_peak_monitor&&hass.states[id].attributes?.metric==='forecast_kw');return {type:'custom:grid-peak-card',entity:entity||'sensor.netzspitzen_prognose'};}
  connectedCallback(){this.render();if(this._hass)this.loadHistory();}
  disconnectedCallback(){this._seq++;this._loading=null;this._lastFetch=0;}
  get state(){return this._hass?.states?.[this._config?.entity];}
  get snapshot(){return this.state?.attributes?.snapshot;}
  get target(){return typeof this._hass?.callService==='function'?targetControl(this._hass.states,this.state?.attributes?.monitor_id):null;}

  targetPanel(s){
    const control=this.target;
    const editing=this._targetEditing&&control?.entity_id===this._targetEditId;
    return `<div class="panel"><div class="cap">Persönliches Ziel</div><div class="metric">${fmt(s.target_kw)} kW</div>${this._view==='reel'?'':editing?`<form data-target-form aria-busy="${!!this._targetSaving}"><label>Neues Ziel in kW<input data-target-value type="text" inputmode="decimal" autocomplete="off" value="${escape(this._targetDraft)}" ${this._targetSaving?'disabled':''} aria-describedby="target-message"></label><div class="target-actions"><button type="submit" ${this._targetSaving?'disabled':''}>${this._targetSaving?'Wird gespeichert …':'Speichern'}</button><button type="button" data-target-cancel ${this._targetSaving?'disabled':''}>Abbrechen</button></div></form>`:control?'<button data-target-open>Ziel ändern</button>':'<p class="muted">Ziel hier derzeit nicht bearbeitbar.</p>'}<p id="target-message" class="muted" role="status" aria-live="polite">${escape(this._targetNotice||'')}</p></div>`;
  }

  openTarget(){
    const control=this.target;if(!control||this._targetSaving)return;
    this._targetEditing=true;this._targetEditId=control.entity_id;this._targetDraft=String(control.current).replace('.',',');this._targetNotice=null;
    this.render();const input=this.shadowRoot.querySelector('[data-target-value]');input?.focus();input?.select();
  }

  async saveTarget(){
    if(this._targetSaving)return;
    const control=this.target;
    if(!this._targetEditing||!control||control.entity_id!==this._targetEditId){this._targetNotice='Ziel derzeit nicht bearbeitbar.';this.shadowRoot.activeElement?.blur();this.render();return;}
    const value=targetValue(this._targetDraft,control);
    this.shadowRoot.activeElement?.blur();
    if(value===null){this._targetNotice=`Bitte ${fmt(control.min,1)} bis ${fmt(control.max,1)} kW in ${fmt(control.step,1)}-Schritten eingeben.`;this.render();return;}
    if(value===control.current){this._targetEditing=false;this._targetNotice='Ziel unverändert.';this.render();return;}
    const seq=++this._targetSeq;this._targetSaving=true;this._targetNotice=null;this.render();
    try{
      await this._hass.callService('number','set_value',{entity_id:control.entity_id,value});
      if(seq!==this._targetSeq)return;
      this._targetEditing=false;this._targetNotice='Ziel gespeichert.';
    }catch(error){if(seq!==this._targetSeq)return;this._targetNotice='Ziel konnte nicht gespeichert werden. Verbindung und Berechtigung prüfen.';}
    finally{if(seq===this._targetSeq){this._targetSaving=false;this.render();}}
  }

  async loadHistory(force=false){
    if(!this.isConnected||!this._date||!this.state?.attributes?.monitor_id)return;
    const key=this.state.attributes.monitor_id+'/'+this._date;
    if(!force&&(this._loading===key||(this._loadedKey===key&&Date.now()-this._lastFetch<60000)))return;
    const seq=++this._seq;this._loading=key;this._error=null;
    try{
      const history=await this._hass.callWS({type:'grid_peak_monitor/history',entry_id:this.state.attributes.monitor_id,date:this._date,month:this._date.slice(0,7)});
      let portal=null,portalError=null;
      if(this._config.portal_history){
        try{portal=await this._hass.callWS({type:'netznoe_quarter_audit/history',date:this._date,month:this._date.slice(0,7)});}catch(e){portalError='Netz-NÖ-Archiv nicht verfügbar';}
      }
      if(seq!==this._seq)return;
      this._history=history;this._portal=portal;this._portalError=portalError;this._loadedKey=key;this._lastFetch=Date.now();
    }catch(e){if(seq!==this._seq)return;this._history=null;this._portal=null;this._error='Verlauf nicht verfügbar. Integration und Zeitraum prüfen.';this._lastFetch=Date.now();this._loadedKey=key;}
    finally{if(seq===this._seq){this._loading=null;this.render();}}
  }

  changeDate(date){this._manualDate=true;this._date=date;this._history=null;this._portal=null;this._lastFetch=0;this._detail=null;this.render();this.loadHistory(true);}
  chart(){
    if(this._error)return `<p role="status">${escape(this._error)}</p>`;
    if(!this._history)return '<p class="muted" role="status">Verlauf wird geladen …</p>';
    const rows=mergeRows(this._history.rows,this._portal?.day?.quarters,this._date,this._zone);
    const scale=Math.max(1,number(this.snapshot?.target_kw)||0,...rows.map(r=>number(r.kw)||0));
    const bars=rows.map(row=>{
      const valid=row.quality==='valid'&&number(row.kw)!=null;
      const text=timeAt(row.start,this._zone,true)+'–'+timeAt(row.end,this._zone,true)+(valid?' · '+fmt(row.kw)+' kW · '+row.source+(row.method==='quantized_counter'?' · mit Zählerauflösung geprüft':''):' · keine vollständige Messung');
      return `<div class="slot ${row.source==='Netz NÖ'?'portal':''}">${valid?`<i style="height:${Math.max(1,row.kw/scale*100)}%"></i>`:''}<button data-slot="${row.start}" title="${escape(text)}" aria-label="${escape(text)}"></button></div>`;
    }).join('');
    return `<div class="cap">${escape(this._date)} · ${fmt(scale,0)} kW Skala</div><div class="plot">${bars}</div><div class="axis">${[0,.25,.5,.75,1].map(f=>`<span>${f===1?'24:00':timeAt(rows[Math.min(rows.length-1,Math.round(rows.length*f))].start,this._zone)}</span>`).join('')}</div><div class="legend"><span><b></b>HA-Schätzung</span><span><b class="portal"></b>Netz NÖ</span></div><p class="muted">${rows.filter(r=>r.quality==='valid').length}/${rows.length} bekannte Viertel · Lücken bleiben leer</p><p class="muted" role="status">${escape(this._detail||'Balken berühren oder mit der Tastatur auswählen.')}</p>${this._portalError?`<p class="muted">${escape(this._portalError)}</p>`:''}`;
  }

  historyPanel(){
    const today=dayAt(Date.now()/1000,this._zone);
    const top=this._history?.top||[];
    const daily=this._history?.daily||[];
    const maximum=Math.max(1,...daily.map(d=>d.kw));
    return `<div class="panel chart"><h2>Feste Viertelstunden</h2><div class="tools"><button data-day="today">Heute</button><button data-day="yesterday">Gestern</button><label>Tag <input type="date" value="${escape(this._date)}" max="${today}" aria-label="Tag auswählen"></label><button data-refresh>Aktualisieren</button></div>${this.chart()}</div>${this._view==='history'?`<div class="panel"><h2>Höchste lokale Viertel · ${escape(this._date.slice(0,7))}</h2>${top.length?top.map(row=>`<button class="top" data-date="${dayAt(row.start,this._zone)}">${fmt(row.kw,3)} kW<span>${dayAt(row.start,this._zone)} · ${timeAt(row.start,this._zone,true)} · HA-Schätzung</span></button>`).join(''):'<p class="muted">Noch keine gültigen Intervalle.</p>'}</div><div class="panel"><h2>Lokale Tagesmaxima</h2><div class="day-grid">${daily.map(d=>`<button class="${d.observed<d.expected?'partial':''}" data-date="${d.date}" style="height:${Math.max(3,d.kw/maximum*100)}%" title="${d.date} · ${fmt(d.kw)} kW · ${d.observed}/${d.expected}" aria-label="${d.date}: ${fmt(d.kw)} kW"></button>`).join('')}</div><p class="muted">Blasse Balken: nur ein Teil des Tages erfasst.</p></div>`:''}`;
  }

  devicesPanel(){return `<div class="panel"><h2>Geräte · Momentanwerte</h2>${this._config.devices.length?this._config.devices.map(id=>{const state=this._hass.states[id];const unit=state?.attributes?.unit_of_measurement;const raw=number(state?.state);const kw=raw!=null&&['W','kW'].includes(unit)?raw/(unit==='W'?1000:1):null;return `<div class="row"><span>${escape(state?.attributes?.friendly_name||id)}</span><strong>${fmt(kw)} kW</strong></div>`;}).join(''):'<p class="muted">Im Karteneditor kannst du eigene Leistungssensoren ergänzen.</p>'}<p class="muted">Momentanwerte erklären keinen vergangenen Viertelstundenpeak.</p></div>`;}

  render(){
    if(!this._config||!this._hass)return;
    if(this.shadowRoot.activeElement?.matches('input[type=date]'))return;
    const s=this.snapshot;
    if(!s){this.shadowRoot.innerHTML=`<style>${css}</style><ha-card><div class="empty">${this.state?'Dieser Sensor liefert noch keine Monitor-Daten.':'Wähle den Prognose-Sensor von Grid Peak Monitor.'}</div></ha-card>`;return;}
    const portalState=this._config.portal_peak?this._hass.states[this._config.portal_peak]:null;
    const portalPeak=portalState?.attributes?.unit_of_measurement==='kW'?number(portalState.state):null;
    const hero=`<div class="panel hero"><div class="cap">${timeAt(s.start,this._zone)}–${timeAt(s.end,this._zone)} · noch ${Math.floor(s.remaining_seconds/60).toString().padStart(2,'0')}:${(s.remaining_seconds%60).toString().padStart(2,'0')}</div><div class="value">${fmt(s.forecast_kw)} <small>kW</small></div><p>Prognose bei gleicher momentaner Leistung</p><p class="status">${escape(statusText[s.status]||s.status)}</p><p class="muted">${s.quality==='valid'?'Minimum '+fmt(s.minimum_kw)+' kW':escape(qualityText[s.quality]||s.quality)} · HA-Schätzung</p>${s.energy_freshness==='quantized_idle'?`<p class="muted">${fmt(s.energy_resolution_kwh*1000,0)}-Wh-Zähler unverändert · Stillstand mit frischer Netzleistung geprüft</p>`:''}</div>`;
    const stats=`<div class="stats"><div class="panel"><div class="cap">Netzbezug jetzt</div><div class="metric">${fmt(s.power_kw)} kW</div></div><div class="panel"><div class="cap">Letztes Viertel</div><div class="metric">${fmt(s.last_quarter_kw)} kW</div><div class="muted">${timeAt(s.start-900,this._zone)}–${timeAt(s.start,this._zone)}</div></div>${this.targetPanel(s)}</div>`;
    const budget=`<div class="panel budget"><div><div class="cap">Erlaubter Bezug für die Restzeit</div><strong>${fmt(s.allowed_power_kw)} kW</strong></div><div><div class="cap">Zusätzlich zur aktuellen Last</div><strong>${fmt(s.additional_power_kw)} kW</strong></div></div>`;
    // Keep the focused editor in place, while the live forecast, timer, status
    // and budgets continue updating from HA. Never turn a draft into a target.
    if(this._targetEditing&&this.target?.entity_id===this._targetEditId&&this.shadowRoot.activeElement?.closest('[data-target-form]')){
      const liveHero=this.shadowRoot.querySelector('.hero');if(liveHero)liveHero.outerHTML=hero;
      const updated=document.createElement('template');updated.innerHTML=stats;
      const panels=this.shadowRoot.querySelector('.stats')?.children;
      if(panels){for(let i=0;i<2;i++)panels[i].replaceWith(updated.content.querySelector('.stats').children[0]);panels[2].querySelector('.metric').textContent=fmt(s.target_kw)+' kW';}
      const liveBudget=this.shadowRoot.querySelector('.budget');if(liveBudget)liveBudget.outerHTML=budget;
      return;
    }
    this.shadowRoot.innerHTML=`<style>${css}</style><ha-card><section class="wrap ${this._view==='reel'?'reel':''}"><div class="cap">Daheim im Detail · Grid Peak Monitor</div><h1>${escape(this._config.title)}</h1>${this._view==='reel'?'<button data-view="overview">Zurück zum Überblick</button>':`<nav class="tabs" aria-label="Ansicht">${[['overview','Überblick'],['history','Verlauf'],['devices','Geräte'],['reel','9:16']].map(([key,title])=>`<button data-view="${key}" class="${this._view===key?'active':''}" aria-pressed="${this._view===key}">${title}</button>`).join('')}</nav>`}${this._view==='devices'?this.devicesPanel():this._view==='history'?this.historyPanel():hero+stats+budget+(this._view==='reel'?'':this.historyPanel()+`<div class="panel"><h2>Bekannte Monatsspitzen</h2><div class="row"><span>HA-Schätzung${s.month_complete?'':' · Teilmonat'}</span><strong>${fmt(s.month_peak_kw,3)} kW</strong></div><p class="muted">${s.month_observed}/${s.month_expected} abgeschlossene Viertel erfasst</p>${portalState?`<div class="row"><span>Netz NÖ · zeitversetzt</span><strong>${fmt(portalPeak,3)} kW</strong></div><p class="muted">Portalstand separat; Vollständigkeit beim Import prüfen.</p>`:''}</div>`)}</section></ha-card>`;
    this.shadowRoot.querySelectorAll('[data-view]').forEach(el=>el.onclick=()=>{this._view=el.dataset.view;this.render();});
    this.shadowRoot.querySelectorAll('[data-date]').forEach(el=>el.onclick=()=>this.changeDate(el.dataset.date));
    this.shadowRoot.querySelectorAll('[data-day]').forEach(el=>el.onclick=()=>{const today=dayAt(Date.now()/1000,this._zone);const date=new Date(today+'T12:00:00Z');if(el.dataset.day==='yesterday')date.setUTCDate(date.getUTCDate()-1);this.changeDate(date.toISOString().slice(0,10));});
    const picker=this.shadowRoot.querySelector('input[type=date]');if(picker)picker.onchange=()=>{const value=picker.value;picker.blur();if(/^\d{4}-\d{2}-\d{2}$/.test(value))this.changeDate(value);};
    if(picker)picker.onblur=()=>this.render();
    const refresh=this.shadowRoot.querySelector('[data-refresh]');if(refresh)refresh.onclick=()=>this.loadHistory(true);
    const targetOpen=this.shadowRoot.querySelector('[data-target-open]');if(targetOpen)targetOpen.onclick=()=>this.openTarget();
    const targetForm=this.shadowRoot.querySelector('[data-target-form]');if(targetForm)targetForm.onsubmit=event=>{event.preventDefault();this.saveTarget();};
    const targetInput=this.shadowRoot.querySelector('[data-target-value]');if(targetInput)targetInput.oninput=()=>{this._targetDraft=targetInput.value;};
    const targetCancel=this.shadowRoot.querySelector('[data-target-cancel]');if(targetCancel)targetCancel.onclick=()=>{if(this._targetSaving)return;this._targetEditing=false;this._targetNotice=null;this.shadowRoot.activeElement?.blur();this.render();};
    this.shadowRoot.querySelectorAll('[data-slot]').forEach(el=>el.onclick=()=>{this._detail=el.getAttribute('aria-label');const detail=this.shadowRoot.querySelector('.chart [role=status]');if(detail)detail.textContent=this._detail;});
  }
}

class GridPeakCardEditor extends HTMLElement {
  constructor(){super();this.attachShadow({mode:'open'});}
  setConfig(config){this._config={...config};this.render();}
  set hass(hass){this._hass=hass;this.render();}
  render(){if(!this._hass||!this._config)return;
    const candidates=Object.entries(this._hass.states).filter(([id,s])=>s.attributes?.grid_peak_monitor&&s.attributes?.metric==='forecast_kw');
    this.shadowRoot.innerHTML=`<style>label{display:block;margin:12px 0}input,select{width:100%;padding:9px;box-sizing:border-box;font:inherit}p{font:13px system-ui;color:var(--secondary-text-color)}</style><label>Prognose-Sensor<select data-key="entity"><option value="">Bitte wählen</option>${candidates.map(([id,s])=>`<option value="${escape(id)}" ${this._config.entity===id?'selected':''}>${escape(s.attributes.friendly_name||id)}</option>`).join('')}</select></label><label>Titel<input data-key="title" value="${escape(this._config.title||'Netzspitzen im Blick')}"></label><label>Startansicht<select data-key="view">${[['overview','Überblick'],['history','Verlauf'],['devices','Geräte'],['reel','9:16']].map(([id,label])=>`<option value="${id}" ${(this._config.view||'overview')===id?'selected':''}>${label}</option>`).join('')}</select></label><label>Geräte-Sensoren, eine Entity-ID pro Zeile<textarea data-key="devices" rows="3" style="width:100%">${escape((this._config.devices||[]).join('\n'))}</textarea></label><p>Optionaler Netz-NÖ-Import: portal_peak und portal_history können in der YAML-Konfiguration ergänzt werden. Die Integration braucht keinen Portalzugang.</p>`;
    this.shadowRoot.querySelectorAll('[data-key]').forEach(el=>el.onchange=()=>{const key=el.dataset.key;this._config[key]=key==='devices'?el.value.split(/\s+/).filter(Boolean):el.value;this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:this._config},bubbles:true,composed:true}));});
  }
}

if(!customElements.get('grid-peak-card'))customElements.define('grid-peak-card',GridPeakCard);
if(!customElements.get('grid-peak-card-editor'))customElements.define('grid-peak-card-editor',GridPeakCardEditor);
window.customCards=window.customCards||[];
if(!window.customCards.some(c=>c.type==='grid-peak-card'))window.customCards.push({type:'grid-peak-card',name:'Grid Peak Monitor',description:'Netzspitzen, Minimum und feste Viertelstunden',preview:true});
