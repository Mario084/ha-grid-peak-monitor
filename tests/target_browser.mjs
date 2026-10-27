// The target UI uses synthetic HA entities; no real service or network calls.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.join(root,'output/target-browser');await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE_PATH});
const page=await browser.newPage({viewport:{width:1100,height:1100}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',async route=>{
 const url=new URL(route.request().url());
 if(url.origin!=='https://grid-peak.test')return route.abort();
 if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:'<!doctype html><meta charset="utf-8"><style>body{margin:12px;background:#eee8dc}grid-peak-card{display:block;max-width:980px;margin:auto}</style><script type="module" src="/grid-peak-card.js"></script>'});
 if(!['/grid-peak-card.js','/model.js'].includes(url.pathname))return route.abort();
 return route.fulfill({contentType:'text/javascript',body:await readFile(path.join(root,'custom_components/grid_peak_monitor/frontend',url.pathname.slice(1)),'utf8')});
});
try{
 await page.goto('https://grid-peak.test');await page.waitForFunction(()=>customElements.get('grid-peak-card'));
 await page.evaluate(()=>{
  const start=Math.floor(Date.now()/1000/900)*900;
  const snapshot={start,end:start+900,remaining_seconds:300,power_kw:6,used_kwh:1.2,minimum_kw:4.8,forecast_kw:6.8,target_kw:8,allowed_power_kw:9.6,additional_power_kw:3.6,last_quarter_kw:5.32,quality:'valid',status:'below',month_peak_kw:7.52,month_complete:false,month_observed:12,month_expected:100};
  const target=(id,value)=>({state:String(value),attributes:{grid_peak_target:true,monitor_id:id,metric:'target_kw',unit_of_measurement:'kW',min:.1,max:1000,step:.1}});
  window.calls=[];
  window.hass={config:{time_zone:'Europe/Vienna'},states:{
   'sensor.own_forecast':{state:'6.8',attributes:{grid_peak_monitor:true,monitor_id:'own',metric:'forecast_kw',snapshot}},
   'number.own_target':target('own',8),
   'sensor.other_forecast':{state:'6.8',attributes:{grid_peak_monitor:true,monitor_id:'other',metric:'forecast_kw',snapshot:{...snapshot,target_kw:7}}},
   'number.other_target':target('other',7)
  },callWS:async r=>({date:r.date,month:r.month,rows:Array.from({length:96},(_,i)=>({start:start-86400+i*900,end:start-86400+(i+1)*900,kw:null,quality:'missing',source:'HA'})),top:[],daily:[]}),
   callService:async(domain,service,data)=>{calls.push({domain,service,data});return new Promise((resolve,reject)=>{window.finish=()=>{hass.states[data.entity_id].state=String(data.value);const key=data.entity_id==='number.own_target'?'sensor.own_forecast':'sensor.other_forecast';const s=hass.states[key].attributes.snapshot;s.target_kw=data.value;s.allowed_power_kw=(data.value-s.minimum_kw)*3;s.additional_power_kw=s.allowed_power_kw-s.power_kw;card.hass=hass;resolve();};window.fail=()=>reject(new Error('Denied'));});}};
  window.card=document.createElement('grid-peak-card');card.setConfig({entity:'sensor.own_forecast'});card.hass=hass;document.body.append(card);
 });
 await page.locator('[data-target-open]').click();
 await page.locator('[data-target-value]').fill('10,5');
 assert.equal(await page.evaluate(()=>calls.length),0);
 await page.evaluate(()=>{hass.states['sensor.own_forecast'].attributes.snapshot.remaining_seconds=299;card.hass=hass;});
 assert.equal(await page.locator('[data-target-value]').inputValue(),'10,5');
 assert.equal(await page.locator('[data-target-value]').evaluate(el=>el===el.getRootNode().activeElement),true);
 assert.match(await page.locator('.hero .cap').innerText(),/04:59/);
 await page.locator('[data-target-form] button[type=submit]').click();
 assert.equal(await page.locator('[data-target-value]').isDisabled(),true);
 await page.evaluate(()=>card.saveTarget());
 assert.equal(await page.evaluate(()=>calls.length),1);
 assert.deepEqual(await page.evaluate(()=>calls[0]),{domain:'number',service:'set_value',data:{entity_id:'number.own_target',value:10.5}});
 await page.evaluate(()=>finish());
 await page.getByText('Ziel gespeichert.',{exact:true}).waitFor();
 assert.match(await page.locator('.stats').innerText(),/10,50 kW/);
 assert.match(await page.locator('.budget').innerText(),/17,10 kW/);
 await page.locator('[data-target-open]').click();await page.locator('[data-target-value]').press('Enter');
 await page.getByText('Ziel unverändert.',{exact:true}).waitFor();assert.equal(await page.evaluate(()=>calls.length),1);
 // A denied service leaves the confirmed target unchanged and keeps the draft.
 await page.locator('[data-target-open]').click();await page.locator('[data-target-value]').fill('11');
 await page.locator('[data-target-value]').press('Enter');await page.evaluate(()=>fail());
 await page.getByText('Ziel konnte nicht gespeichert werden. Verbindung und Berechtigung prüfen.',{exact:true}).waitFor();
 assert.equal(await page.locator('[data-target-value]').inputValue(),'11');
 assert.match(await page.locator('.stats .metric').last().innerText(),/10,50/);
 await page.locator('[data-target-cancel]').click();assert.equal(await page.locator('[data-target-form]').count(),0);
 // Validation never calls a service, and Enter remains inside the form.
 await page.locator('[data-target-open]').click();
 for(const invalid of ['', '0','-1','1000,1','8,55','1e2']){
  await page.locator('[data-target-value]').fill(invalid);await page.locator('[data-target-value]').press('Enter');
  await page.getByText(/Bitte 0,1 bis 1.000,0 kW/).waitFor();
 }
 assert.equal(await page.evaluate(()=>calls.length),2);
 // The editor is unavailable when its own number disappears, even if another exists.
 await page.evaluate(()=>{hass.states['number.own_target'].state='unavailable';card.hass=hass;});
 assert.equal(await page.locator('[data-target-open]').count(),0);
 await page.evaluate(()=>card.saveTarget());assert.equal(await page.evaluate(()=>calls.length),2);
 await page.evaluate(()=>{hass.states['number.own_target'].state='10.5';card.setConfig({entity:'sensor.own_forecast'});card.hass=hass;});
 // Keep an old pending request from changing a newly selected monitor's UI.
 await page.locator('[data-target-open]').click();await page.locator('[data-target-value]').fill('12');
 await page.locator('[data-target-value]').press('Enter');
 await page.evaluate(()=>{card.setConfig({entity:'sensor.other_forecast'});card.hass=hass;finish();});
 assert.match(await page.locator('.stats .metric').last().innerText(),/7,00/);
 assert.equal(await page.getByText('Ziel gespeichert.',{exact:true}).count(),0);
 assert.equal(await page.evaluate(()=>hass.states['number.other_target'].state),'7');
 // Mobile layouts, including editing controls, must remain inside the viewport.
 for(const width of [390,320]){
  await page.setViewportSize({width,height:1200});
  await page.locator('[data-target-open]').click();await page.locator('[data-target-value]').fill('9,5');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(output,`target-edit-${width}.png`),fullPage:true});
  await page.locator('[data-target-cancel]').click();
 }
 await page.evaluate(()=>{delete hass.callService;card.hass=hass;});
 assert.equal(await page.locator('[data-target-open]').count(),0);
 assert.deepEqual(errors,[]);
 const result={checks:['same-monitor discovery','draft and focus survive HA updates','decimal comma','explicit save','one pending request','authoritative target and budget update','Enter submits','denied service and cancel','range and step validation','unavailable target','monitor change during request','390/320px editor','read-only fallback'],service_domains:['number'],page_errors:errors,production_contacted:false};
 await writeFile(path.join(output,'results.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
}finally{await browser.close();}
