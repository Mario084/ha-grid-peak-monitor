// Actual HA frontend, services and storage in a NEW synthetic container only.
// Set ALPHA6_UI_URL and ALPHA6_UI_AUTH to this disposable fixture's local relay.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const origin=process.env.ALPHA6_UI_URL;
assert.ok(origin&&/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(origin),'Loopback synthetic fixture URL required');
const auth=JSON.parse(await readFile(process.env.ALPHA6_UI_AUTH,'utf8'));
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.join(root,'output/panel-browser');await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE_PATH});
const context=await browser.newContext({viewport:{width:1280,height:1050},locale:'de-AT'});
await context.addInitScript(auth=>{
 if(!localStorage.getItem('hassTokens'))localStorage.setItem('hassTokens',JSON.stringify({...auth,hassUrl:location.origin,expires:Date.now()+1800000}));
},auth);
const page=await context.newPage();const errors=[];
page.on('pageerror',error=>errors.push(error.message));
await context.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
const panel=page.locator('grid-peak-panel');const card=panel.locator('grid-peak-card');
async function command(action,monitor='one'){
 return page.evaluate(async({action,monitor})=>{
  const app=document.querySelector('home-assistant');
  return app.hass.callWS({type:'alpha6_test/control',action,monitor});
 },{action,monitor});
}
async function targetValue(){return card.locator('.stats .metric').last().innerText();}
async function save(value,expected){
 await card.locator('[data-target-open]').click();
 await card.locator('[data-target-value]').fill(value);
 await card.locator('[data-target-value]').press('Enter');
 await card.getByText('Ziel gespeichert.',{exact:true}).waitFor();
 assert.match(await targetValue(),expected);
 // Check the actual backend number state, not just the rendered notice.
 const actual=await page.evaluate(()=>{
  const app=document.querySelector('home-assistant');
  const panel=app.shadowRoot.querySelector('home-assistant-main').shadowRoot.querySelector('partial-panel-resolver')?.querySelector('grid-peak-panel');
  return Object.values(app.hass.states).filter(s=>s.attributes.grid_peak_target).map(s=>({monitor:s.attributes.monitor_id,value:Number(s.state)}));
 });
 assert.ok(actual.some(s=>s.value===Number(value.replace(',','.'))));
}
try{
 await page.goto(origin+'/');
 // Minimal fresh HA may request confirmation of its test-only listen address.
 const confirm=page.getByRole('button',{name:/^(Confirm|Bestätigen)$/});
 try{await confirm.waitFor({timeout:5000});await confirm.click();}catch{}
 const sidebar=page.locator('a[href="/grid-peak-monitor"]');
 await sidebar.waitFor();assert.equal(await sidebar.count(),1);await sidebar.click();
 await card.locator('.hero').waitFor();
 assert.deepEqual(await page.evaluate(()=>document.querySelector('home-assistant').hass.callWS({type:'alpha6_test/identity'})),{synthetic_only:true,existing_config_used:false,fixture:'alpha6-disposable-panel-test'});
 if((await page.evaluate(()=>document.querySelector('home-assistant').hass.callWS({type:'grid_peak_monitor/monitors'}))).monitors.some(m=>m.title==='Beispielmonitor two'))await command('remove','two');
 await card.getByRole('heading',{name:'Beispielmonitor one',exact:true}).waitFor();
 assert.equal(await panel.locator('[data-picker]').isVisible(),false);
 assert.match(await card.locator('h1').innerText(),/Beispielmonitor one/);
 assert.match(await targetValue(),/10,00/);
 await save('10,1',/10,10/);await save('10',/10,00/);
 await command('reload');await card.locator('.hero').waitFor();
 await page.reload();await card.locator('.hero').waitFor();assert.match(await targetValue(),/10,00/);
 await page.screenshot({path:path.join(output,'panel-single-1280.png'),fullPage:true});
 await command('create','two');
 await panel.locator('[data-picker]').waitFor();
 assert.equal(await panel.locator('select option').count(),2);
 const options=await panel.locator('select option').evaluateAll(nodes=>nodes.map(n=>({value:n.value,label:n.textContent})));
 const second=options.find(o=>o.label.includes('two')).value;
 await panel.locator('select').selectOption(second);
 assert.match(await card.locator('h1').innerText(),/two/);
 await save('10,1',/10,10/);
 await page.reload();await card.locator('.hero').waitFor();assert.match(await card.locator('h1').innerText(),/two/);assert.match(await targetValue(),/10,10/);
 await save('10',/10,00/);
 const first=options.find(o=>o.label.includes('one')).value;
 await panel.locator('select').selectOption(first);assert.match(await targetValue(),/10,00/);
 await panel.locator('select').selectOption(second);
 await page.screenshot({path:path.join(output,'panel-multi-1280.png'),fullPage:true});
 await page.setViewportSize({width:390,height:1100});
 // The panel supplies a working mobile header/menu, not an inaccessible page.
 await panel.locator('[data-menu]').click();
 await sidebar.waitFor({state:'visible'});assert.equal(await sidebar.count(),1);
 await page.mouse.click(375,40);
 await sidebar.waitFor({state:'hidden'});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.ok(await panel.evaluate(el=>el.scrollWidth<=el.clientWidth));
 await page.screenshot({path:path.join(output,'panel-multi-390.png'),fullPage:true});
 await card.locator('[data-target-open]').click();await card.locator('[data-target-value]').fill('10,1');
 assert.ok(await panel.evaluate(el=>el.scrollWidth<=el.clientWidth));
 await page.screenshot({path:path.join(output,'panel-edit-390.png'),fullPage:true});
 await card.locator('[data-target-cancel]').click();
 await command('unload','two');
 await page.waitForFunction(()=>document.querySelector('home-assistant').hass.states&&Object.values(document.querySelector('home-assistant').hass.states).filter(s=>s.attributes.grid_peak_monitor&&s.attributes.metric==='forecast_kw').length===1);
 await card.getByRole('heading',{name:'Beispielmonitor one',exact:true}).waitFor();
 assert.equal(await panel.locator('[data-picker]').isVisible(),false);
 await command('load','two');await panel.locator('[data-picker]').waitFor();assert.equal(await panel.locator('select option').count(),2);
 await command('remove','two');await card.getByRole('heading',{name:'Beispielmonitor one',exact:true}).waitFor();
 assert.equal(await panel.locator('[data-picker]').isVisible(),false);
 assert.deepEqual(errors,[]);
 const result={ha_version:'2026.10.2',actual_HA_frontend:true,synthetic_only:true,checks:['sidebar click to own page','one sidebar entry','single monitor','real Number 10→10.1→10','backend state confirmation','config-entry reload and browser reload','multiple monitor selection','selection survives browser reload','other monitor target unchanged','mobile header opens HA sidebar','390/1280 no overflow','390 target editor','unloaded monitor disappears','reload no duplicates','removed monitor disappears'],page_errors:errors,production_contacted:false};
 await writeFile(path.join(output,'results.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
}finally{await browser.close();}
