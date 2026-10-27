import assert from 'node:assert/strict';
import {test} from 'node:test';
import {mergeRows,number,escape,normalizeConfig,timeAt,targetControl,targetValue} from '../custom_components/grid_peak_monitor/frontend/model.js';

test('portal data replace the same UTC slot, without duplicate bars',()=>{
  const start=Date.parse('2026-10-22T08:00:00Z')/1000;
  const local=[{start,end:start+900,kw:4.8,source:'HA',quality:'valid'}];
  const merged=mergeRows(local,[{utc:'2026-10-22T08:00:00Z',kw:4.7}],'2026-10-22','Europe/Vienna');
  assert.equal(merged.length,1);assert.equal(merged[0].source,'Netz NÖ');assert.equal(merged[0].kw,4.7);
});
test('invalid, misaligned and foreign-day portal samples stay out',()=>{
  const start=Date.parse('2026-10-22T08:00:00Z')/1000;
  const local=[{start,kw:null,quality:'missing'}];
  const merged=mergeRows(local,[{start,kw:-1},{start:start+1,kw:2},{utc:'2026-10-21T08:00:00Z',kw:2}],'2026-10-22','Europe/Vienna');
  assert.equal(merged[0].kw,null);
});
test('HTML and invalid numeric states are handled safely',()=>{
  assert.equal(escape('<img onerror="x">'),'&lt;img onerror=&quot;x&quot;&gt;');
  for(const x of [null,'',true,'unavailable','NaN','Infinity'])assert.equal(number(x),null);
  assert.equal(number('0'),0);
});
test('configuration accepts only sensor IDs for monitor and devices',()=>{
  assert.throws(()=>normalizeConfig({entity:'<script>'}));
  assert.throws(()=>normalizeConfig({entity:'sensor.test_forecast',devices:['switch.example']}));
  assert.equal(normalizeConfig({entity:'sensor.test_forecast'}).view,'overview');
});
test('repeated DST hour has different offset labels',()=>{
  const first=Date.parse('2026-10-25T00:15:00Z')/1000,second=first+3600;
  assert.notEqual(timeAt(first,'Europe/Vienna',true),timeAt(second,'Europe/Vienna',true));
});

const ownTarget={state:'10',attributes:{grid_peak_target:true,monitor_id:'own',metric:'target_kw',unit_of_measurement:'kW',min:.1,max:1000,step:.1}};
test('target control selects only its own monitor and number domain',()=>{
  const states={'number.foreign':{...ownTarget,attributes:{...ownTarget.attributes,monitor_id:'foreign'}},'input_number.own':ownTarget,'number.own':ownTarget};
  assert.equal(targetControl(states,'own').entity_id,'number.own');
  assert.equal(targetControl(states,'missing'),null);
  assert.equal(targetControl(states,null),null);
});
test('ambiguous, unavailable or incorrectly identified targets are not editable',()=>{
  assert.equal(targetControl({'number.a':ownTarget,'number.b':ownTarget},'own'),null);
  for(const changed of [{state:'unavailable'},{attributes:{...ownTarget.attributes,grid_peak_target:false}},{attributes:{...ownTarget.attributes,unit_of_measurement:'W'}}])
    assert.equal(targetControl({'number.a':{...ownTarget,...changed}},'own'),null);
});
test('target values accept a decimal comma and enforce limits and tenths',()=>{
  const control=targetControl({'number.own':ownTarget},'own');
  for(const [text,value] of [['9,5',9.5],[' 10.1 ',10.1],['0,1',.1],['1000',1000]])assert.equal(targetValue(text,control),value);
  for(const text of ['', ' ', '0','-1','1000.1','9.55','1e2','NaN','Infinity','1,2,3','<img>'])assert.equal(targetValue(text,control),null,text);
  assert.equal(targetValue('10',null),null);
});
test('target validation follows a narrower entity range and step',()=>{
  const control=targetControl({'number.own':{...ownTarget,attributes:{...ownTarget.attributes,min:1,max:20,step:.5}}},'own');
  assert.equal(targetValue('9,5',control),9.5);
  assert.equal(targetValue('9,6',control),null);
  assert.equal(targetValue('20,5',control),null);
});
