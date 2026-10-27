// Exercise only the local form UI; inspect/save responses are synthetic.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:390,height:1000}});
const errors=[];let saved;
page.on('pageerror',error=>errors.push(error.message));
try{
  await page.route('**/*',async route=>{
    const url=new URL(route.request().url());
    if(url.origin!=='http://127.0.0.1:8125')return route.abort();
    if(url.pathname==='/inspect')return route.fulfill({contentType:'application/json',body:JSON.stringify({sensors:[
      {entity_id:'sensor.grid_power',name:'Netzleistung',state:'6000',unit:'W',kind:'power'},
      {entity_id:'sensor.grid_import',name:'Netzimport',state:'1200',unit:'kWh',kind:'energy'}]})});
    if(url.pathname==='/save'){saved=route.request().postDataJSON();return route.fulfill({contentType:'application/json',body:'{"saved":true}'});}
    return route.continue();
  });
  await page.goto('http://127.0.0.1:8125/');
  assert.equal(await page.locator('#token').getAttribute('type'),'password');
  await page.locator('#token').fill('synthetic-test-token');
  await page.locator('#inspect').click();
  await page.locator('#power').selectOption('sensor.grid_power');
  await page.locator('#energy').selectOption('sensor.grid_import');
  await page.locator('#sign').selectOption('-1');
  await page.locator('button[type=submit]').click();
  await page.getByText(/Lokal gespeichert/).waitFor();
  assert.equal(saved.power_entity,'sensor.grid_power');assert.equal(saved.import_sign,-1);
  assert.equal(await page.locator('#token').inputValue(),'');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  const denied=await page.request.post('http://127.0.0.1:8125/save',{data:{token:'synthetic-test-token'}});
  assert.equal(denied.status(),403);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({local_setup_UI:true,masked_token:true,source_selection:true,token_cleared_after_save:true,no_horizontal_overflow:true,missing_CSRF_rejected:true,production_contacted:false,page_errors:errors}));
}finally{await browser.close();}
