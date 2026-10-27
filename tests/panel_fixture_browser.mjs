// Error/retry/lifecycle cases with intercepted modules and synthetic HA only.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const require=createRequire(import.meta.url);const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE_PATH});
const page=await browser.newPage({viewport:{width:390,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',async route=>{
 const u=new URL(route.request().url());if(u.origin!=='https://panel.test')return route.abort();
 if(u.pathname==='/')return route.fulfill({contentType:'text/html',body:'<!doctype html><meta charset="utf-8"><script type="module" src="/grid-peak-panel.js"></script>'});
 if(!['grid-peak-panel.js','grid-peak-card.js','model.js'].includes(u.pathname.slice(1)))return route.abort();
 return route.fulfill({contentType:'text/javascript',body:await readFile(path.join(root,'custom_components/grid_peak_monitor/frontend',u.pathname.slice(1)),'utf8')});
});
try{
 await page.goto('https://panel.test');await page.waitForFunction(()=>customElements.get('grid-peak-panel'));
 await page.evaluate(()=>{
  window.allow=false;window.panel=document.createElement('grid-peak-panel');
  window.hass={states:{},config:{time_zone:'Europe/Vienna'},callWS:async r=>{if(r.type==='grid_peak_monitor/monitors'){if(!allow)throw new Error('Denied');return {monitors:[]};}throw new Error('Unexpected request');}};
  document.body.append(panel);panel.hass=hass;
 });
 await page.getByText('Monitore konnten nicht geladen werden. Verbindung und Berechtigung prüfen.',{exact:true}).waitFor();
 await page.evaluate(()=>{panel.hass=hass;});
 assert.equal(await page.getByText('Monitore konnten nicht geladen werden. Verbindung und Berechtigung prüfen.',{exact:true}).isVisible(),true);
 await page.evaluate(()=>{window.allow=true;});await page.getByRole('button',{name:'Erneut versuchen'}).click();
 await page.getByText(/Kein geladener Monitor/).waitFor();
 assert.equal(await page.getByRole('button',{name:'Erneut versuchen'}).isVisible(),false);
 await page.evaluate(()=>{window.menu=0;panel.addEventListener('hass-toggle-menu',()=>menu++);});
 await page.getByRole('button',{name:'Menü öffnen'}).click();assert.equal(await page.evaluate(()=>menu),1);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);
 const result={checks:['discovery denied','error persists through HA update','retry recovers','empty loaded list','menu event','390px no overflow'],page_errors:errors,external_requests:false};
 await mkdir(path.join(root,'output/panel-fixture-browser'),{recursive:true});await writeFile(path.join(root,'output/panel-fixture-browser/results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close();}
