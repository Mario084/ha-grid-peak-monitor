"""Observer tests use private temporary files, no HA, Docker or chat calls."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from soak_watch import Observer, local, save

BASE = 1792872000  # Just before the DST change; schedules are elapsed UTC hours.


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.directory=TemporaryDirectory()
        self.root=Path(self.directory.name)
        test=self.root/'output/ha-preview-config';test.mkdir(parents=True)
        (test/'.grid-peak-preview').touch()
        (test/'live-status.json').write_text('{"state":"active","audit":"recording"}')
        stamp=datetime.fromtimestamp(BASE,timezone.utc).isoformat()
        self.run={'project':str(self.root),'container':'grid-peak-monitor-preview',
                  'started_at':BASE,'ends_at':BASE+172800,'first_full_quarter':BASE,
                  'max_age':120,'container_started_at':stamp,'code_hashes':{},'codex':'unused','thread_id':'unused'}
        self.path=self.root/'run.json';save(self.path,self.run)
        self.sent=[]
        self.watch=Observer(self.path,notifier=lambda path:self.sent.append(path) or True)
        self.running={'state':{'Running':True,'StartedAt':stamp}}

    def tearDown(self): self.directory.cleanup()

    def test_only_the_dedicated_test_instance_is_accepted(self):
        self.run['container']='production';save(self.path,self.run)
        with self.assertRaises(ValueError):Observer(self.path)

    def test_unchanged_condition_notifies_once_and_new_episode_notifies_again(self):
        self.watch.reconcile({'quality_power_stale':90},BASE)
        self.assertEqual(len(self.sent),0)
        self.watch.reconcile({'quality_power_stale':90},BASE+90)
        self.watch.reconcile({'quality_power_stale':90},BASE+1000)
        self.assertEqual(len(self.sent),1)
        self.watch.reconcile({},BASE+1010)
        self.watch.reconcile({'quality_power_stale':90},BASE+1020)
        self.watch.reconcile({'quality_power_stale':90},BASE+1120)
        self.assertEqual(len(self.sent),2)

    def test_stopped_instance_does_not_create_secondary_alert_storm(self):
        issues=self.watch.conditions(BASE+1000,{'state':{'Running':False}})
        self.assertEqual(issues,{'test_instance_stopped':0})

    def test_warmup_old_quality_is_not_a_new_failure(self):
        process_at=BASE+20
        self.running['state']['StartedAt']=datetime.fromtimestamp(process_at,timezone.utc).isoformat()
        self.watch.state.update(last_at=BASE+30,last_snapshot={'quality':'energy_invalid'})
        issues=self.watch.conditions(BASE+31,self.running)
        self.assertNotIn('quality_energy_invalid',issues)
        self.assertIn('test_instance_restarted',issues)
        self.assertNotIn('test_instance_restarted',self.watch.conditions(BASE+32,self.running))

    def test_stale_feed_is_detected_even_if_old_status_says_active(self):
        self.watch.state.update(last_at=BASE+10,last_snapshot={'quality':'valid'})
        self.assertIn('live_capture_stale',self.watch.conditions(BASE+400,self.running))

    def test_missing_archive_boundary_has_grace_but_invalid_quarter_is_reported(self):
        self.assertNotIn('archive_quarter_missing',self.watch.conditions(BASE+1000,self.running))
        self.assertIn('archive_quarter_missing',self.watch.conditions(BASE+1021,self.running))
        self.watch.state['records'][str(BASE)]={'start':BASE,'end':BASE+900,'quality':'energy_invalid'}
        issues=self.watch.conditions(BASE+1021,self.running)
        self.assertNotIn('archive_quarter_missing',issues)
        self.assertIn('archive_quarter_invalid',issues)

    def test_live_arithmetic_fault_notifies_without_changing_measurements(self):
        self.watch.state['arithmetic_errors']=[{'field':'forecast_kw','actual':99,'expected':0}]
        issues=self.watch.conditions(BASE+1,self.running)
        self.watch.reconcile(issues,BASE+1)
        self.assertEqual(len(self.sent),1)
        self.assertEqual(json.loads(self.sent[0].read_text())['code'],'arithmetic_mismatch')

    def test_healthy_24h_checkpoint_is_quiet_and_48h_completion_queues_once(self):
        # Empty capture here; isolate notification scheduling from source quality.
        self.watch.conditions=lambda now,inspection:{}
        self.watch.tick(BASE+86400,self.running)
        self.assertEqual(self.sent,[])
        self.assertTrue((self.root/'midpoint-24h.json').exists())
        self.watch.tick(BASE+172800,self.running)
        self.watch.tick(BASE+172830,self.running)
        self.assertEqual(len(self.sent),1)
        self.assertTrue(self.watch.state['completion_queued'])

    def test_elapsed_48_hours_survive_the_extra_local_dst_hour(self):
        self.assertIn('+02:00',local(BASE))
        self.assertIn('+01:00',local(BASE+172800))
        self.assertEqual(self.run['ends_at']-self.run['started_at'],172800)

    def test_notification_failure_retries_with_same_notice_and_private_files(self):
        self.watch.notifier=lambda path:False
        self.watch.reconcile({'test_instance_stopped':0},BASE)
        notices=list((self.root/'notices').glob('*.json'))
        self.assertEqual(len(notices),1)
        self.assertEqual(notices[0].stat().st_mode&0o777,0o600)
        self.watch.reconcile({'test_instance_stopped':0},BASE+30)
        self.assertEqual(len(list((self.root/'notices').glob('*.json'))),1)
        self.watch.notifier=lambda path:self.sent.append(path) or True
        self.watch.reconcile({'test_instance_stopped':0},BASE+301)
        self.assertEqual(self.sent,[notices[0].resolve()])

    def test_real_import_coverage_does_not_depend_on_counter_guard_episode(self):
        rows=[]
        for elapsed in range(0,181,30):
            rows.append({'calculated_at':BASE+elapsed,'power':{'value':1,'at':BASE+elapsed},
                         'energy':{'value':100+elapsed/3600,'at':BASE+elapsed},
                         'snapshot':{'quality':'valid','power_kw':1},'records':[],
                         'sustained_import':False})
        (self.root/'output/ha-preview-config/live-audit.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        self.watch.consume()
        self.assertTrue(self.watch.state['sustained_import_seen'])


if __name__=='__main__':unittest.main()
