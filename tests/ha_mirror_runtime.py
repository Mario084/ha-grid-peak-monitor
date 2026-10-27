"""End-to-end mirror test inside a disposable, networkless HA container."""
import asyncio
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
from unittest.mock import AsyncMock,patch
from homeassistant import bootstrap,loader
from homeassistant.core import HomeAssistant

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from live_mirror import LiveMirror
from live_audit import LiveAudit
from verify_live_capture import check


async def main():
    requests=[]
    response={'mode':'ok','stamp':datetime.now(timezone.utc).isoformat()}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            requests.append((self.command,self.path))
            if response['mode']=='fail':
                self.send_response(503);self.end_headers();return
            is_power=self.path.endswith('sensor.real_power')
            data={'entity_id':'sensor.real_power' if is_power else 'sensor.real_import','state':'6000' if is_power else '1201.2',
                'last_reported':response['stamp'],'last_updated':response['stamp'],
                'attributes':{'unit_of_measurement':'W' if is_power else 'kWh','state_class':'measurement' if is_power else 'total_increasing'}}
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(data).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='mirror-ha-') as directory:
            config=Path(directory)
            shutil.copytree(ROOT/'custom_components',config/'custom_components')
            hass=HomeAssistant(str(config));loader.async_setup(hass)
            await bootstrap.async_from_config_dict({'homeassistant':{'name':'Mirror test','time_zone':'Europe/Vienna','country':'AT','latitude':48.2,'longitude':16.3,'unit_system':'metric'},'http':{'server_host':'127.0.0.1','server_port':8123},'frontend':{},'lovelace':{},'grid_peak_monitor':{}},hass)
            await hass.async_start()
            try:
                path=config/'live-source.json'
                path.write_text(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','token':'synthetic-test-token','power_entity':'sensor.real_power','energy_entity':'sensor.real_import','import_sign':1,'target_kw':8,'max_age':120}))
                ready=[]
                capture=LiveAudit(config/'live-audit.jsonl')
                mirror=LiveMirror(hass,path,ready.append,audit=capture)
                await mirror.tick()
                assert mirror.entry is not None, path.with_name('live-status.json').read_text()
                await hass.async_block_till_done()
                assert len(ready)==1
                coordinator=hass.data['grid_peak_monitor'][mirror.entry.entry_id]
                from ha_preview import PreviewData
                public_response=await PreviewData(coordinator).get(None)
                assert public_response.status==503, 'live monitor must never be served by the unauthenticated demo'
                assert len(coordinator.monitor.records)==0, 'must not seed fake history'
                now=datetime.now(timezone.utc).timestamp();start=int(now//900)*900
                coordinator.monitor.anchors[start]=1200
                coordinator.monitor.bad.pop(start,None)
                coordinator.async_set_updated_data(coordinator._compute())
                assert abs(coordinator.data['minimum_kw']-4.8)<1e-7
                assert coordinator.data['power_kw']==6
                first_entry=mirror.entry.entry_id
                await coordinator.set_target(7.5)
                # A new bridge instance must retain the target edited in test HA.
                second=LiveMirror(hass,path,lambda entry:None,audit=capture)
                await second.tick()
                assert second.entry.entry_id==first_entry
                assert hass.data['grid_peak_monitor'][first_entry].monitor.target==7.5
                # Polling an old value must not refresh its source timestamp.
                response['stamp']=datetime.fromtimestamp(now-600,timezone.utc).isoformat()
                await second.tick();await hass.async_block_till_done()
                coordinator=hass.data['grid_peak_monitor'][first_entry]
                assert coordinator.data['quality']=='power_stale',coordinator.data['quality']
                assert coordinator.data['forecast_kw'] is None
                response['mode']='fail'
                await second.tick();await hass.async_block_till_done()
                assert all(hass.states.get(entity).state=='unavailable' for entity in second.ids)
                assert coordinator.data['forecast_kw'] is None
                assert all(method=='GET' and path in ('/api/states/sensor.real_power','/api/states/sensor.real_import') for method,path in requests)
                assert not any('token' in str(hass.states.get(entity).attributes) for entity in second.ids)
                captured=[json.loads(line) for line in (config/'live-audit.jsonl').read_text().splitlines()]
                audit_report=check(captured)
                assert not audit_report['arithmetic_errors'],audit_report
                assert audit_report['valid_live_calculations']>=1,audit_report
                class BrokenAudit:
                    def capture(self,coordinator):raise OSError('synthetic disk failure')
                second.audit=BrokenAudit()
                response['mode']='ok';response['stamp']=datetime.now(timezone.utc).isoformat()
                await second.tick();await hass.async_block_till_done()
                assert all(hass.states.get(entity).state!='unavailable' for entity in second.ids)
                status=json.loads((config/'live-status.json').read_text())
                assert status['audit']=='write_failed' and status['state']=='active'

                print(json.dumps({'real_HA_mirror':True,'GET_only':True,'empty_live_archive':True,'public_demo_rejects_real_monitor':True,'separate_test_states':True,'minimum_kw':4.8,'old_timestamp_stays_stale':True,'source_failure_unavailable':True,'same_entry_and_target_after_bridge_restart':True,'capture_arithmetic_checked':True,'audit_failure_keeps_feed':True,'source_requests':len(requests),'production_contacted':False}))
            finally:await hass.async_stop()
    finally:
        server.shutdown();server.server_close();thread.join()


if __name__=='__main__':
    with patch('homeassistant.components.analytics.async_setup_entry',new=AsyncMock(return_value=True)):
        asyncio.run(main())
