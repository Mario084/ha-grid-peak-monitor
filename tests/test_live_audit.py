from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_live_capture import check
BASE=1792828800


def row(offset,energy,*,minimum=0,forecast=6,allowed=8,additional=2,remaining=None):
    start=BASE+(offset//900)*900
    return {'calculated_at':BASE+offset,'power':{'value':-6,'at':BASE+offset},
        'energy':{'value':energy,'at':BASE+offset},'accepted_energy':{'value':energy,'at':BASE+offset},
        'baseline_kwh':1200+(offset//900)*1.5,'import_sign':-1,'max_age':120,'records':[],
        'snapshot':{'start':start,'end':start+900,'target_kw':8,'power_kw':6,'quality':'valid',
        'used_kwh':minimum/4,'minimum_kw':minimum,'forecast_kw':forecast,'allowed_power_kw':allowed,
        'additional_power_kw':additional,'headroom_kw':8-forecast}}


class AuditTests(unittest.TestCase):
    def test_known_example_uses_decimal_reference(self):
        result=check([row(600,1201.2,minimum=4.8,forecast=6.8,allowed=9.6,additional=3.6)])
        self.assertEqual(result['arithmetic_errors'],[])
        self.assertEqual(result['valid_live_calculations'],1)
        self.assertEqual(result['status'],'pending')

    def test_corrupt_forecast_is_detected(self):
        sample=row(600,1201.2,minimum=4.8,forecast=3.2,allowed=9.6,additional=3.6)
        result=check([sample]);self.assertEqual(result['status'],'failed')
        self.assertTrue(any(e['field']=='forecast_kw' for e in result['arithmetic_errors']))

    def test_full_interval_is_checked_from_source_reports(self):
        samples=[]
        for offset in range(0,901,30):
            elapsed=offset%900;minimum=elapsed*6/900;allowed=(8-minimum)*900/(900-elapsed)
            samples.append(row(offset,1200+offset*6/3600,minimum=minimum,forecast=6,allowed=allowed,additional=allowed-6))
        samples[-1]['records']=[{'start':BASE,'end':BASE+900,'kw':6,'quality':'valid'}]
        result=check(samples)
        self.assertEqual(result['status'],'passed',result['arithmetic_errors'])
        self.assertEqual(result['independently_verified_intervals'][0]['independent_kw'],6)

    def test_corrupt_archive_is_detected(self):
        first=row(0,1200);last=row(900,1201.5)
        last['records']=[{'start':BASE,'end':BASE+900,'kw':99,'quality':'valid'}]
        # Only boundary samples are needed when the counter reports exactly there.
        result=check([first,last]);self.assertEqual(result['status'],'failed')
        self.assertTrue(any(e['field']=='archive_kw' for e in result['arithmetic_errors']))

    def test_invalid_interval_must_not_show_zero(self):
        sample=row(0,1200);sample['records']=[{'start':BASE-900,'kw':0,'quality':'missing'}]
        self.assertEqual(check([sample])['status'],'failed')

    def test_stale_power_cannot_remain_valid(self):
        sample=row(0,1200);sample['power']['at']-=600
        self.assertEqual(check([sample])['status'],'failed')

    def test_absent_or_incomplete_capture_never_passes(self):
        self.assertEqual(check([])['status'],'pending')
        sample=row(0,1200);sample['records']=[{'start':BASE-900,'kw':6,'quality':'valid'}]
        self.assertEqual(check([sample])['status'],'pending')

    def test_quantized_interval_needs_continuous_raw_observations(self):
        samples=[]
        for offset in range(0,901,30):
            sample=row(offset,1200,forecast=0,allowed=8*900/(900-offset%900),additional=8*900/(900-offset%900))
            sample['power']['value']=0;sample['snapshot']['power_kw']=0
            sample['energy']['at']=sample['accepted_energy']['at']=BASE-3600
            sample['baseline_kwh']=1200
            sample.update(continuity_since=BASE,energy_resolution_kwh=.01)
            sample['snapshot']['energy_freshness']='quantized_idle'
            sample['snapshot']['headroom_kw']=8
            samples.append(sample)
        samples[-1]['records']=[{'start':BASE,'end':BASE+900,'kw':0,'quality':'valid','method':'quantized_counter'}]
        result=check(samples)
        self.assertEqual(result['status'],'passed',result)
        self.assertEqual(len(result['independently_verified_intervals']),1)
        self.assertEqual(result['quantized_idle_calculations'],31)
        self.assertEqual(check([samples[0],samples[-1]])['status'],'pending')

    def test_quantized_proof_cannot_start_after_boundary(self):
        sample=row(30,1200)
        sample.update(continuity_since=BASE+10,energy_resolution_kwh=.01)
        sample['snapshot']['energy_freshness']='quantized_idle'
        self.assertTrue(any(e['field']=='quantized_continuity' for e in check([sample])['arithmetic_errors']))


class CaptureTests(unittest.TestCase):
    def test_capture_is_private_and_omits_credentials(self):
        import json
        from dataclasses import dataclass
        from tempfile import TemporaryDirectory
        from types import ModuleType,SimpleNamespace
        from unittest.mock import patch
        from live_audit import LiveAudit
        @dataclass
        class Sample:
            value:float
            at:float
        adapter=ModuleType('custom_components.grid_peak_monitor.coordinator')
        adapter.sample=lambda state,energy=False:state
        sample=row(600,1201.2,minimum=4.8,forecast=6.8,allowed=9.6,additional=3.6)
        monitor=SimpleNamespace(last_tick=BASE+600,sign=-1,max_age=120,
            anchors={BASE:1200},last_energy=Sample(1201.2,BASE+600),records={})
        values={'sensor.mirror_power':Sample(-6,BASE+600),'sensor.mirror_energy':Sample(1201.2,BASE+600)}
        coordinator=SimpleNamespace(monitor=monitor,data=sample['snapshot'],
            options={'power_sensor':'sensor.mirror_power','energy_sensor':'sensor.mirror_energy','token':'TOKEN_MUST_NEVER_BE_CAPTURED'},
            hass=SimpleNamespace(states=SimpleNamespace(get=values.get)))
        with TemporaryDirectory() as directory,patch.dict(sys.modules,{'custom_components.grid_peak_monitor.coordinator':adapter}):
            path=Path(directory)/'capture.jsonl';capture=LiveAudit(path)
            capture.capture(coordinator);capture.capture(coordinator)
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            text=path.read_text();self.assertNotIn('TOKEN_MUST_NEVER_BE_CAPTURED',text)
            lines=text.splitlines();self.assertEqual(len(lines),1)
            report=check([json.loads(lines[0])]);self.assertEqual(report['arithmetic_errors'],[])


if __name__=='__main__':unittest.main()
