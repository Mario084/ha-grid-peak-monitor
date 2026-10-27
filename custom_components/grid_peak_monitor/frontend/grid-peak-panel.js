// A supported custom panel hosts the same card renderer as personal dashboards.
import './grid-peak-card.js?v=0.1.0-alpha.6';
import {escape} from './model.js';

class GridPeakPanel extends HTMLElement {
  constructor(){
    super();this.attachShadow({mode:'open'});this._monitors=[];this._request=0;
    try{this._selected=sessionStorage.getItem('grid-peak-monitor:selected');}catch{}
    this.shadowRoot.innerHTML=`<style>
      :host{display:block;height:100%;overflow:auto;background:var(--primary-background-color,#111d1e);color:var(--primary-text-color);font:16px system-ui,sans-serif}
      *{box-sizing:border-box}header{display:flex;align-items:center;gap:12px;min-height:64px;padding:8px 16px;border-bottom:1px solid var(--divider-color,#49625c);background:var(--app-header-background-color,#182729);color:var(--app-header-text-color,#f3eee3)}
      h1{font-size:20px;margin:0;flex:1}button{font:inherit;cursor:pointer;border:0;background:transparent;color:inherit;min-width:44px;min-height:44px;border-radius:8px}button:focus-visible,select:focus-visible{outline:3px solid #e6b971;outline-offset:2px}
      main{max-width:1050px;margin:auto;padding:16px;min-width:0}label{display:block;margin:0 0 14px}select{display:block;margin-top:6px;width:100%;max-width:100%;font:inherit;padding:10px;background:var(--card-background-color,#223839);color:var(--primary-text-color,#f3eee3);border:1px solid #78918a;border-radius:8px}
      [hidden]{display:none!important}.notice{padding:16px;line-height:1.5}.retry{border:1px solid #78918a;padding:5px 12px}grid-peak-card{display:block;min-width:0}@media(max-width:620px){main{padding:8px}header{padding:8px}h1{font-size:19px}}
    </style><header><button data-menu aria-label="Menü öffnen" title="Menü öffnen">☰</button><h1>Netzspitzen</h1></header><main><label data-picker hidden>Monitor auswählen<select aria-label="Monitor auswählen"></select></label><p class="notice" role="status">Monitore werden geladen …</p><button class="retry" hidden>Erneut versuchen</button><grid-peak-card hidden></grid-peak-card></main>`;
    this.shadowRoot.querySelector('[data-menu]').onclick=()=>this.dispatchEvent(new CustomEvent('hass-toggle-menu',{bubbles:true,composed:true}));
    this.shadowRoot.querySelector('select').onchange=event=>this.select(event.target.value);
    this.shadowRoot.querySelector('.retry').onclick=()=>this.loadMonitors();
  }
  set hass(hass){
    this._hass=hass;
    // An entry load/unload or an entity rename changes this signature. Ordinary
    // meter updates preserve the selected monitor, draft input and input focus.
    const signature=Object.entries(hass.states||{}).filter(([,s])=>s.attributes?.grid_peak_monitor&&s.attributes?.metric==='forecast_kw')
      .map(([id,s])=>id+':'+s.attributes.monitor_id+':'+(s.state==='unavailable')).sort().join('|');
    if(signature!==this._signature){this._signature=signature;this.loadMonitors();}
    this.updateCard();
  }
  set panel(panel){this._panel=panel;}
  set narrow(narrow){this.toggleAttribute('narrow',!!narrow);}
  set route(route){this._route=route;}
  connectedCallback(){if(this._hass)this.loadMonitors();}
  disconnectedCallback(){this._request++;this._signature=undefined;}
  async loadMonitors(){
    if(!this._hass||!this.isConnected)return;
    const request=++this._request;
    try{
      const result=await this._hass.callWS({type:'grid_peak_monitor/monitors'});
      if(request!==this._request)return;
      this._loadError=false;this._monitors=result.monitors;
      if(!this._monitors.some(m=>m.monitor_id===this._selected))this._selected=this._monitors[0]?.monitor_id;
      this.shadowRoot.querySelector('select').innerHTML=this._monitors.map(m=>`<option value="${escape(m.monitor_id)}">${escape(m.title)}</option>`).join('');
      this.shadowRoot.querySelector('[data-picker]').hidden=this._monitors.length<2;
      this.shadowRoot.querySelector('.retry').hidden=true;
      this.updateCard();
    }catch{
      if(request!==this._request)return;
      this._loadError=true;this.showNotice('Monitore konnten nicht geladen werden. Verbindung und Berechtigung prüfen.');
      this.shadowRoot.querySelector('.retry').hidden=false;
    }
  }
  select(id){
    if(!this._monitors.some(m=>m.monitor_id===id))return;
    this._selected=id;
    try{sessionStorage.setItem('grid-peak-monitor:selected',id);}catch{}
    this.updateCard();
  }
  showNotice(message){const notice=this.shadowRoot.querySelector('.notice');notice.hidden=false;notice.textContent=message;this.shadowRoot.querySelector('grid-peak-card').hidden=true;}
  updateCard(){
    if(this._loadError){this.showNotice('Monitore konnten nicht geladen werden. Verbindung und Berechtigung prüfen.');return;}
    const monitor=this._monitors.find(m=>m.monitor_id===this._selected);
    if(!monitor){this.showNotice('Kein geladener Monitor. Grid Peak Monitor unter Geräte & Dienste einrichten oder aktivieren.');return;}
    if(!monitor.entity_id||!this._hass?.states[monitor.entity_id]){this.showNotice('Monitor wird geladen. Falls er nicht erscheint, Integration unter Geräte & Dienste prüfen.');return;}
    const card=this.shadowRoot.querySelector('grid-peak-card');
    const key=monitor.monitor_id+'/'+monitor.entity_id+'/'+monitor.title;
    if(key!==this._cardKey){card.setConfig({entity:monitor.entity_id,title:monitor.title});this._cardKey=key;}
    card.hidden=false;this.shadowRoot.querySelector('.notice').hidden=true;card.hass=this._hass;
  }
}
if(!customElements.get('grid-peak-panel'))customElements.define('grid-peak-panel',GridPeakPanel);
