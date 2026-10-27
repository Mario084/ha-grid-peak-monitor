"""No production server is contacted: a loopback fake records every request."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from read_only_source import StateReader, SourceConfig, ReadError, normalize_state, base_url, REMOTE_STAMP
from configure_live_source import save_private

STAMP='2026-10-23T08:00:00+00:00'


def state(entity,kind='power',value='6000'):
    return {'entity_id':entity,'state':value,'last_reported':STAMP,'last_updated':STAMP,
        'attributes':{'unit_of_measurement':'W' if kind=='power' else 'kWh','state_class':'measurement' if kind=='power' else 'total_increasing','friendly_name':'Example'}}


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.requests=[]
        self.mode='normal'
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                owner.requests.append((self.command,self.path,self.headers.get('Authorization')))
                if owner.mode=='redirect':
                    self.send_response(302);self.send_header('Location','/unexpected');self.end_headers();return
                if owner.mode=='unauthorized':
                    self.send_response(401);self.end_headers();self.wfile.write(b'secret-response-must-not-escape');return
                rows=[state('sensor.grid_power'),state('sensor.grid_energy','energy','1200'),state('sensor.temperature','power','20')]
                rows[2]['attributes']['unit_of_measurement']='C'
                data=rows if self.path=='/api/states' else next((s for s in rows if '/api/states/'+s['entity_id']==self.path),None)
                self.send_response(200 if data else 404);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(data).encode())
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        self.config=SourceConfig.parse({'url':self.url,'token':'test-token','power_entity':'sensor.grid_power','energy_entity':'sensor.grid_energy'})

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def test_pair_uses_only_two_get_requests(self):
        reader=StateReader(self.url,'test-token',('sensor.grid_power','sensor.grid_energy'))
        pair=reader.pair(self.config)
        self.assertEqual([r[:2] for r in self.requests],[('GET','/api/states/sensor.grid_power'),('GET','/api/states/sensor.grid_energy')])
        self.assertEqual(pair[0]['attributes'][REMOTE_STAMP],STAMP)
        self.assertEqual(pair[1]['state'],'1200')
        self.assertTrue(all(r[2]=='Bearer test-token' for r in self.requests))

    def test_discovery_filters_other_measurements(self):
        candidates=StateReader(self.url,'test-token').discover()
        self.assertEqual({s['kind'] for s in candidates},{'power','energy'})
        self.assertEqual(len(candidates),2)
        self.assertEqual(self.requests[0][:2],('GET','/api/states'))

    def test_redirect_is_not_followed(self):
        self.mode='redirect'
        reader=StateReader(self.url,'test-token',('sensor.grid_power',))
        with self.assertRaisesRegex(ReadError,'redirect_blocked'):reader._get('/api/states/sensor.grid_power')
        self.assertEqual(len(self.requests),1)

    def test_no_services_templates_or_other_entities(self):
        reader=StateReader(self.url,'test-token',('sensor.grid_power',))
        for path in ('/api/services/switch/turn_on','/api/template','/api/states/sensor.other','/api/config'):
            with self.assertRaisesRegex(ReadError,'endpoint_blocked'):reader._get(path)
        self.assertEqual(self.requests,[])

    def test_auth_error_does_not_expose_response_or_token(self):
        self.mode='unauthorized'
        with self.assertRaises(ReadError) as caught:StateReader(self.url,'test-token').discover()
        self.assertEqual(str(caught.exception),'auth_failed')
        self.assertNotIn('test-token',repr(self.config))

    def test_original_report_time_is_preserved(self):
        original=state('sensor.grid_power')
        original['last_updated']='2026-10-22T08:00:00+00:00'
        result=normalize_state(original,'sensor.grid_power','power')
        self.assertEqual(result['attributes'][REMOTE_STAMP],STAMP)
        self.assertLess(datetime.fromisoformat(STAMP),datetime(2026,10,23,9,tzinfo=timezone.utc))

    def test_missing_report_time_uses_conservative_update_time(self):
        original=state('sensor.grid_power');del original['last_reported']
        self.assertEqual(normalize_state(original,'sensor.grid_power','power')['attributes'][REMOTE_STAMP],STAMP)

    def test_invalid_timestamp_and_wrong_entity_fail_closed(self):
        for invalid in ('bad','2026-10-23T08:00:00',None):
            original=state('sensor.grid_power');original['last_reported']=invalid
            with self.assertRaisesRegex(ReadError,'invalid_timestamp'):normalize_state(original,'sensor.grid_power','power')
        with self.assertRaises(ReadError):normalize_state(state('sensor.other'),'sensor.grid_power','power')

    def test_invalid_energy_is_rejected(self):
        for value in ('nan','inf','-1'):
            with self.assertRaises(ReadError):normalize_state(state('sensor.grid_energy','energy',value),'sensor.grid_energy','energy')
        original=state('sensor.grid_energy','energy');original['attributes']['state_class']='measurement'
        with self.assertRaises(ReadError):normalize_state(original,'sensor.grid_energy','energy')

    def test_unavailable_is_copied_as_unavailable(self):
        result=normalize_state(state('sensor.grid_power',value='unavailable'),'sensor.grid_power','power')
        self.assertEqual(result['state'],'unavailable')

    def test_url_and_entity_validation(self):
        self.assertEqual(base_url(self.url+'/lovelace/dashboard'),self.url)
        for url in ('file:///etc/passwd','http://user:password@example.test','http://example.test/?token=x'):
            with self.assertRaises(ReadError):base_url(url)
        for entity in ('switch.example','sensor.power/../../services','sensor.other?token=x'):
            with self.assertRaises(ReadError):SourceConfig.parse({'url':self.url,'token':'test-token','power_entity':entity,'energy_entity':'sensor.grid_energy'})

    def test_credentials_file_is_private_and_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'live-source.json'
            save_private(self.config,target)
            self.assertEqual(target.stat().st_mode&0o777,0o600)
            self.assertEqual(json.loads(target.read_text())['token'],'test-token')
            self.assertEqual(len(list(Path(directory).iterdir())),1)

    def test_resolution_is_explicit_bounded_and_preserved(self):
        from dataclasses import asdict
        data=asdict(self.config)
        self.assertEqual(self.config.energy_resolution_kwh,0)
        data['energy_resolution_kwh']=.01
        self.assertEqual(SourceConfig.parse(data).energy_resolution_kwh,.01)
        for invalid in (-1,2,float('nan'),float('inf')):
            with self.assertRaises(ReadError):SourceConfig.parse({**data,'energy_resolution_kwh':invalid})


if __name__=='__main__':unittest.main()
