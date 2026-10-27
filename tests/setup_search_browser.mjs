// Test the next setup UI without restarting the user's active setup page.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=fileURLToPath(new URL('../',import.meta.url));
const html=execFileSync('python3',['-c',"import sys;sys.path.insert(0,'scripts');from configure_live_source import PAGE;print(PAGE.replace('__NONCE__','\"fixture-csrf\"').replace('__SOURCE__','\"http://ha-source.test\"'))"],{cwd:root,encoding:'utf8'});
const sensors=[
 {entity_id:'sensor.grid_power',name:'Stromzähler Wirkleistung',state:'-2000',unit:'W',kind:'power'},
 {entity_id:'sensor.grid_import',name:'Stromzähler Verbrauch',state:'1000',unit:'kWh',kind:'energy'},
 ...Array.from({length:500},(_,i)=>({entity_id:'sensor.device_power_'+i,name:'Gerät '+i,state:'20',unit:'W',kind:'power'})),
 ...Array.from({length:500},(_,i)=>({entity_id:'sensor.device_energy_'+i,name:'Gerät '+i,state:'100',unit:'kWh',kind:'energy'})),
];
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:390,height:1000}});
const errors=[];let inspectCalls=0,saveCalls=0,saved;
page.on('pageerror',error=>errors.push(error.message));
try{
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url());
  if(url.origin!=='https://setup.test')return route.abort();
  if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
  if(url.pathname==='/inspect'){inspectCalls++;return route.fulfill({contentType:'application/json',body:JSON.stringify({sensors})});}
  if(url.pathname==='/save'){saveCalls++;saved=route.request().postDataJSON();return route.fulfill({contentType:'application/json',body:'{"saved":true}'});}
  return route.abort();
 });
 await page.goto('https://setup.test/');
 await page.locator('#token').fill('synthetic-test-token');
 await page.locator('#inspect').click();
 await page.locator('#sensors').waitFor({state:'visible'});
 assert.equal(await page.locator('#power option').count(),502);
 assert.equal(await page.locator('#energy option').count(),502);
 await page.locator('#sensor-search').fill('STROMZÄHLER');
 assert.equal(await page.locator('#power option').count(),2);
 assert.equal(await page.locator('#energy option').count(),2);
 await page.locator('#power').selectOption('sensor.grid_power');
 await page.locator('#sensor-search').fill('grid_import');
 assert.equal(await page.locator('#power').inputValue(),'sensor.grid_power');
 assert.match(await page.locator('#power option:checked').innerText(),/^Ausgewählt/);
 await page.locator('#energy').selectOption('sensor.grid_import');
 await page.locator('#sensor-search').fill('gibt-es-nicht');
 assert.match(await page.locator('#sensor-count').innerText(),/Leistung 0 · Energie 0/);
 assert.equal(await page.locator('#power').inputValue(),'sensor.grid_power');
 assert.equal(await page.locator('#energy').inputValue(),'sensor.grid_import');
 await page.locator('#sensor-search').press('Enter');assert.equal(saveCalls,0);
 await page.locator('#sensor-search').fill('');
 assert.equal(await page.locator('#power option').count(),502);
 assert.equal(await page.locator('#energy').inputValue(),'sensor.grid_import');
 assert.equal(inspectCalls,1); // filtering sends no new source requests
 assert.equal(await page.locator('#token').inputValue(),'synthetic-test-token');
 await page.locator('#sign').selectOption('-1');
 await page.locator('button[type=submit]').click();
 await page.getByText(/Lokal gespeichert/).waitFor();
 assert.equal(saved.power_entity,'sensor.grid_power');assert.equal(saved.energy_entity,'sensor.grid_import');
 assert.equal(saved.import_sign,-1);assert.equal(saveCalls,1);
 assert.equal(saved.energy_resolution_kwh,0);
 assert.equal(await page.locator('#token').inputValue(),'');
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({sensors:1002,search_by_name_and_entity:true,case_and_umlaut_search:true,preserved_selection:true,no_matches:true,clearing_filter:true,enter_does_not_save:true,filter_does_not_refetch:true,save_keeps_selection:true,production_contacted:false,page_errors:errors}));
}finally{await browser.close();}
