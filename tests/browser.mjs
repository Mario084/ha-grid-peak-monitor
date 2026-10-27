// Browser QA uses synthetic entities and intercepted module requests only.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.join(root, 'output/browser');
await mkdir(output, {recursive:true});
const browser = await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE_PATH});
const page = await browser.newPage({viewport:{width:1280,height:1100},deviceScaleFactor:1});
const errors = [];
page.on('pageerror', error => errors.push(error.message));
await page.route('**/*', async route => {
  const url = new URL(route.request().url());
  if (url.origin !== 'https://grid-peak.test') return route.abort();
  if (url.pathname === '/') return route.fulfill({contentType:'text/html',body:'<!doctype html><meta charset="utf-8"><title>Grid Peak Monitor · synthetische Testdaten</title><style>body{margin:16px;background:#eee8dc}grid-peak-card{display:block;max-width:1000px;margin:auto}</style><script type="module" src="/grid-peak-card.js"></script>'});
  if (!['/grid-peak-card.js','/model.js'].includes(url.pathname)) return route.abort();
  return route.fulfill({contentType:'text/javascript',body:await readFile(path.join(root,'custom_components/grid_peak_monitor/frontend',url.pathname.slice(1)),'utf8')});
});
try {
  await page.goto('https://grid-peak.test');
  await page.waitForFunction(() => customElements.get('grid-peak-card'));
  await page.evaluate(() => {
    const now = Date.now()/1000;
    const start = Math.floor(now/900)*900;
    const date = new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Vienna',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    window.requests = []; window.pending = [];
    window.hass = {config:{time_zone:'Europe/Vienna'}, states:{
      'sensor.demo_forecast':{state:'6.8',attributes:{grid_peak_monitor:true,metric:'forecast_kw',monitor_id:'synthetic',friendly_name:'Demo Prognose',snapshot:{start,end:start+900,remaining_seconds:300,power_kw:6,minimum_kw:4.8,forecast_kw:6.8,target_kw:8,allowed_power_kw:9.6,additional_power_kw:3.6,last_quarter_kw:5.32,quality:'valid',status:'below',month_peak_kw:7.52,month_complete:false,month_observed:126,month_expected:2000}}},
      'sensor.demo_device':{state:'2350',attributes:{unit_of_measurement:'W',friendly_name:'<img src=x onerror="window.injected=true">'}}
    },callWS:async request => {
      window.requests.push(request);
      if (window.defer) return new Promise(resolve => window.pending.push({request,resolve}));
      if (request.type !== 'grid_peak_monitor/history') throw new Error('Optional portal is absent');
      return window.makeHistory(request.date);
    }};
    window.makeHistory = selected => {
      const midnight=Date.parse(selected+'T00:00:00+02:00')/1000;
      const rows=Array.from({length:96},(_,i)=>({start:midnight+i*900,end:midnight+(i+1)*900,kw:i%13===0?null:2+Math.sin(i*.4)*1.3+(i%7)*.65,quality:i%13===0?'missing':'valid',source:'HA'}));
      return {date:selected,month:selected.slice(0,7),rows,top:[{start:midnight+36000,kw:7.52}],daily:[{date:selected,kw:7.52,observed:88,expected:96}]};
    };
    window.card=document.createElement('grid-peak-card');
    card.setConfig({entity:'sensor.demo_forecast',devices:['sensor.demo_device']});
    card.hass=hass;document.body.append(card);
    window.today=date;
  });
  await page.locator('.slot').first().waitFor();
  assert.equal(await page.locator('.slot').count(),96);
  assert.ok(await page.locator('.hero').innerText().then(s=>s.includes('6,80')));
  await page.screenshot({path:path.join(output,'overview-desktop.png'),fullPage:true});
  await page.locator('[data-slot]').first().click();
  assert.match(await page.locator('.chart [role=status]').innerText(), /keine vollständige Messung/);
  await page.locator('[data-view=history]').click();
  assert.equal(await page.locator('.top').count(),1);
  await page.locator('[data-view=devices]').click();
  assert.ok((await page.locator('.row').innerText()).includes('2,35 kW'));
  assert.equal(await page.evaluate(()=>window.injected), undefined);
  assert.equal(await page.locator('img').count(),0);
  await page.locator('[data-view=reel]').click();
  await page.locator('[data-view=overview]').click();
  assert.equal(await page.locator('.hero').count(),1);
  for (const width of [390,320]) {
    await page.setViewportSize({width,height:1000});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow at ${width}`);
    await page.screenshot({path:path.join(output,`overview-${width}.png`),fullPage:true});
  }
  await page.evaluate(()=>{
    window.savedSnapshot=structuredClone(hass.states['sensor.demo_forecast'].attributes.snapshot);
    Object.assign(hass.states['sensor.demo_forecast'].attributes.snapshot,{energy_freshness:'quantized_idle',energy_resolution_kwh:.01});
    card.hass=hass;
  });
  await page.getByText('10-Wh-Zähler unverändert · Stillstand mit frischer Netzleistung geprüft',{exact:true}).waitFor();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.evaluate(()=>{
    Object.assign(hass.states['sensor.demo_forecast'].attributes.snapshot,{quality:'counter_stalled',forecast_kw:null,minimum_kw:null,energy_freshness:'unconfirmed',status:'no_data'});
    card.hass=hass;
  });
  assert.match(await page.locator('.hero').innerText(),/Importzähler steht trotz Netzbezug still/);
  assert.match(await page.locator('.hero .value').innerText(),/—/);
  await page.evaluate(()=>{hass.states['sensor.demo_forecast'].attributes.snapshot=window.savedSnapshot;card.hass=hass;});
  await page.locator('[data-view=history]').click();
  await page.locator('input[type=date]').fill('2026-10-21');
  await page.locator('input[type=date]').dispatchEvent('change');
  await page.waitForFunction(()=>window.card._history?.date==='2026-10-21');
  // Out-of-order WebSocket replies must not overwrite the latest selected day.
  await page.evaluate(()=>{window.defer=true;card.changeDate('2026-10-20');card.changeDate('2026-10-19');});
  await page.evaluate(()=>{pending[1].resolve(makeHistory('2026-10-19'));});
  await page.waitForFunction(()=>card._history?.date==='2026-10-19');
  await page.evaluate(()=>{pending[0].resolve(makeHistory('2026-10-20'));});
  assert.equal(await page.evaluate(()=>card._history.date),'2026-10-19');
  await page.evaluate(()=>{window.defer=false;card.setConfig({entity:'sensor.demo_forecast',portal_history:true});card.hass=hass;});
  await page.getByText('Netz-NÖ-Archiv nicht verfügbar',{exact:true}).waitFor();
  assert.equal(await page.locator('.slot').count(),96);
  await page.evaluate(async()=>{
    const editor=await customElements.get('grid-peak-card').getConfigElement();
    editor.setConfig({entity:'sensor.demo_forecast'});editor.hass=hass;
    editor.addEventListener('config-changed',event=>window.edited=event.detail.config);
    document.body.append(editor);
  });
  await page.locator('grid-peak-card-editor [data-key=title]').fill('Mein Netz');
  await page.locator('grid-peak-card-editor [data-key=title]').dispatchEvent('change');
  assert.equal(await page.evaluate(()=>window.edited.title),'Mein Netz');
  assert.deepEqual(errors,[]);
  const result={checks:['overview','96 slots and missing interval','slot detail','history','devices W conversion','HTML escaping','reel return','390px and 320px overflow','quantized idle explanation','counter fault hides forecast','date picker','out-of-order replies','optional portal fallback','visual editor'],page_errors:errors,external_requests:false};
  await writeFile(path.join(output,'results.json'),JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify(result));
} finally {await browser.close();}
