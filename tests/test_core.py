from datetime import date, datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import random
import sys
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("peak_core", ROOT/"custom_components/grid_peak_monitor/core.py")
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)
BASE = int(datetime(2026, 10, 22, 8, tzinfo=timezone.utc).timestamp())


def sample(value, at):
    return core.Sample(value, at)


def run_constant(monitor, start=BASE, duration=900, power=6, energy=1200, step=30):
    for offset in range(0, duration+1, step):
        at = start+offset
        result = monitor.update(at, sample(power, at), sample(energy+offset*power/3600, at))
    return result


class CoreTests(unittest.TestCase):
    def test_physical_example_and_budget(self):
        m=core.Monitor(sign=-1)
        for offset in range(0,601,30):
            e=1200+offset*.002
            result=m.update(BASE+offset,sample(-6,BASE+offset),sample(e,BASE+offset))
        self.assertAlmostEqual(result['minimum_kw'],4.8)
        self.assertAlmostEqual(result['forecast_kw'],6.8)
        self.assertAlmostEqual(result['allowed_power_kw'],9.6)
        self.assertAlmostEqual(result['additional_power_kw'],3.6)

    def test_forecast_never_below_minimum_random_valid_windows(self):
        rng=random.Random(42)
        for case in range(40):
            m=core.Monitor(); energy=1200
            m.update(BASE,sample(0,BASE),sample(energy,BASE))
            for offset in range(30,901,30):
                power=rng.uniform(0,30);energy+=power*30/3600
                result=m.update(BASE+offset,sample(power,BASE+offset),sample(energy,BASE+offset))
                if result['forecast_kw'] is not None:
                    self.assertGreaterEqual(result['forecast_kw']+1e-8,result['minimum_kw'])

    def test_startup_partial_not_used_as_complete(self):
        m=core.Monitor()
        r=run_constant(m,start=BASE+300,duration=600)
        self.assertIsNone(r['last_quarter_kw'])
        self.assertNotEqual(m.records[BASE]['quality'],'valid')
        r=run_constant(m,start=BASE+900,duration=900,energy=1201)
        self.assertAlmostEqual(r['last_quarter_kw'],6)

    def test_boundary_interpolation(self):
        m=core.Monitor()
        # Reports straddle each boundary by 15 seconds.
        run_constant(m,start=BASE-15,duration=1830)
        self.assertEqual(m.records[BASE]['quality'],'valid')
        self.assertAlmostEqual(m.records[BASE]['kw'],6)

    def test_45_minute_gap_is_not_one_peak(self):
        m=core.Monitor()
        m.update(BASE,sample(6,BASE),sample(1200,BASE))
        r=m.update(BASE+2700,sample(6,BASE+2700),sample(1204.5,BASE+2700))
        self.assertIsNone(r['month_peak_kw'])
        self.assertEqual(len(m.records),3)
        self.assertTrue(all(row['kw'] is None for row in m.records.values()))

    def test_restart_same_quarter_preserves_known_baseline(self):
        m=core.Monitor();run_constant(m,duration=300)
        restored=core.Monitor();restored.restore(json.loads(json.dumps(m.dump())),BASE+330)
        r=restored.update(BASE+330,sample(6,BASE+330),sample(1200.55,BASE+330))
        self.assertAlmostEqual(r['forecast_kw'],6)

    def test_restart_across_gap_marks_missing_quarters(self):
        m=core.Monitor();run_constant(m,duration=300)
        restored=core.Monitor();restored.restore(json.loads(json.dumps(m.dump())),BASE+2700)
        r=restored.update(BASE+2700,sample(6,BASE+2700),sample(1204.5,BASE+2700))
        self.assertTrue(all(row['kw'] is None for row in restored.records.values()))
        self.assertIsNone(r['month_peak_kw'])

    def test_counter_reset_blocks_quarter_and_does_not_make_zero_peak(self):
        m=core.Monitor();run_constant(m,duration=300)
        r=m.update(BASE+330,sample(6,BASE+330),sample(1,BASE+330))
        self.assertEqual(r['quality'],'counter_reset')
        self.assertIsNone(r['forecast_kw'])

    def test_invalid_energy_and_recovery(self):
        m=core.Monitor();run_constant(m,duration=300)
        m.update(BASE+330,sample(6,BASE+330),sample(None,BASE+330))
        r=m.update(BASE+360,sample(6,BASE+360),sample(1200.6,BASE+360))
        self.assertEqual(r['quality'],'energy_invalid')

    def test_zero_energy_can_remain_unchanged_with_continuous_zero_power(self):
        m=core.Monitor()
        for offset in range(0,1801,30):
            r=m.update(BASE+offset,sample(0,BASE+offset),sample(1200,BASE))
        self.assertEqual(r['quality'],'valid')
        self.assertEqual(r['forecast_kw'],0)

    def test_stale_energy_not_hidden_by_late_zero_power(self):
        m=core.Monitor();run_constant(m,duration=300)
        r=m.update(BASE+600,sample(0,BASE+600),sample(1200.5,BASE+300))
        self.assertEqual(r['quality'],'energy_stale')

    def test_power_stale_and_future_reports(self):
        m=core.Monitor();run_constant(m,duration=300)
        for report in (BASE+100,BASE+400):
            r=m.update(BASE+330,sample(6,report),sample(1200.55,BASE+330))
            self.assertEqual(r['quality'],'power_stale')

    def test_unchanged_report_timestamp_does_not_invent_energy(self):
        m=core.Monitor();run_constant(m,duration=300)
        before=m.last_energy
        m.update(BASE+310,sample(6,BASE+310),sample(before.value,before.at))
        self.assertEqual(m.last_energy,before)

    def test_out_of_order_report_is_ignored(self):
        m=core.Monitor();run_constant(m,duration=300)
        previous=m.last_energy
        m.update(BASE+310,sample(6,BASE+310),sample(1,BASE+100))
        self.assertEqual(m.last_energy,previous)

    def test_warning_debounce_and_immediate_minimum_breach(self):
        m=core.Monitor(target=5)
        self.assertEqual(m._warning(BASE,6,1),'checking')
        self.assertEqual(m._warning(BASE+21,6,1),'risk')
        self.assertEqual(m._warning(BASE+22,4.7,1),'near')
        self.assertEqual(m._warning(BASE+23,6,5.1),'exceeded')

    def test_warning_debounce_restarts_in_next_quarter(self):
        m=core.Monitor(target=5)
        self.assertEqual(m._warning(BASE+870,6,1),'checking')
        self.assertEqual(m._warning(BASE+895,6,1),'risk')
        self.assertEqual(m._warning(BASE+900,6,0),'checking')

    def test_month_rollover_does_not_keep_previous_month_peak(self):
        start=int(datetime(2026,10,31,22,45,tzinfo=timezone.utc).timestamp())
        m=core.Monitor();r=run_constant(m,start=start,duration=900)
        self.assertEqual(r['month_observed'],0)
        self.assertIsNone(r['month_peak_kw'])
        self.assertEqual(m.records[start]['kw'],6)

    def test_dst_fall_back_all_100_windows_remain_distinct(self):
        day=date(2026,10,25); slots=core.day_slots(day,'Europe/Vienna')
        self.assertEqual(len(slots),100)
        m=core.Monitor();run_constant(m,start=slots[0],duration=100*900,power=2,step=30)
        history=m.history(day.isoformat(),'2026-10',slots[-1]+900)
        self.assertEqual(history['observed'],100)
        self.assertTrue(all(abs(row['kw']-2)<1e-7 for row in history['rows']))

    def test_dst_spring_forward_has_92_windows(self):
        self.assertEqual(len(core.day_slots(date(2026,3,29),'Europe/Vienna')),92)

    def test_history_rejects_future_and_unretained_dates(self):
        m=core.Monitor()
        for day in ('2030-01-01','2020-01-01'):
            with self.assertRaises(ValueError):m.history(day,day[:7],BASE)

    def test_no_fabricated_archive_on_first_old_report(self):
        m=core.Monitor();m.update(BASE,sample(6,BASE),sample(1200,0))
        self.assertEqual(len(m.records),0)

    def test_restore_rejects_corrupt_state(self):
        m=core.Monitor();m.restore({'version':1,'cursor':'invalid'},BASE)
        self.assertIsNone(m.cursor)

    def test_configuration_validation(self):
        for kwargs in ({'target':float('nan')},{'target':-1},{'sign':True},{'max_age':1},{'zone':'invalid'},
                       {'energy_resolution':-1},{'energy_resolution':float('nan')},{'energy_resolution':2}):
            with self.assertRaises((ValueError,KeyError)):core.Monitor(**kwargs)

    def test_non_finite_values_never_become_forecasts(self):
        for value in (None,float('inf'),float('nan'),-1):
            m=core.Monitor();m.update(BASE,sample(6,BASE),sample(1200,BASE))
            r=m.update(BASE+30,sample(6,BASE+30),sample(value,BASE+30))
            self.assertIsNone(r['forecast_kw'])


class QuantizedCounterTests(unittest.TestCase):
    def monitor(self):
        return core.Monitor(sign=-1, energy_resolution=.01)

    def test_offset_counter_reports_preserve_energy_across_adjacent_quarters(self):
        m=self.monitor();closed=None
        for offset in range(-60,1861,5):
            reported=((offset-30)//60)*60+30
            m.update(BASE+offset,sample(-.6,BASE+offset),sample(100+reported*.6/3600,BASE+reported))
            if offset==900:closed=dict(m.records[BASE])
            if offset==930:self.assertEqual(m.records[BASE],closed)
        self.assertAlmostEqual(m.records[BASE]['kw'],.6)
        self.assertAlmostEqual(m.records[BASE+900]['kw'],.6)
        self.assertAlmostEqual(sum(m.records[t]['kw']/4 for t in (BASE,BASE+900)),.3)

    def test_quantized_boundary_survives_restart_without_later_refinement(self):
        m=self.monitor()
        for offset in range(-60,906,5):
            reported=((offset-30)//60)*60+30
            m.update(BASE+offset,sample(-.6,BASE+offset),sample(100+reported*.6/3600,BASE+reported))
        before=m.anchors[BASE+900]
        restored=self.monitor();restored.restore(json.loads(json.dumps(m.dump())),BASE+910)
        restored.update(BASE+930,sample(-.6,BASE+930),sample(100.155,BASE+930))
        self.assertEqual(restored.anchors[BASE+900],before)
        self.assertAlmostEqual(restored.records[BASE]['kw'],.6)

    def test_alpha3_quantized_archive_is_retained_as_untrusted_on_update(self):
        m=self.monitor();self.feed(m,1800)
        data=m.dump();data.pop('accounting_version')
        restored=self.monitor();restored.restore(data,BASE+1810)
        self.assertIn(BASE,restored.records)
        self.assertEqual(restored.records[BASE]['quality'],'legacy_boundary')
        self.assertIsNone(restored.records[BASE]['kw'])
        self.assertEqual(restored.anchors,{})
        again=self.monitor();again.restore(json.loads(json.dumps(restored.dump())),BASE+1820)
        self.assertEqual(again.records[BASE]['quality'],'legacy_boundary')
        self.assertIsNone(again.records[BASE]['kw'])

    def test_124_second_power_report_gap_requires_explicit_longer_limit(self):
        for limit,quality in ((120,'power_stale'),(180,'valid')):
            m=core.Monitor(sign=-1,energy_resolution=.01,max_age=limit)
            m.update(BASE,sample(-.6,BASE),sample(1200,BASE))
            r=m.update(BASE+124,sample(-.6,BASE),sample(1200.02,BASE+124))
            self.assertEqual(r['quality'],quality)
        r=m.update(BASE+181,sample(-.6,BASE),sample(1200.03,BASE+181))
        self.assertEqual(r['quality'],'power_stale')
        self.assertIsNone(r['forecast_kw'])

    def test_longer_power_deadline_still_detects_frozen_counter_and_unavailable(self):
        m=core.Monitor(sign=-1,energy_resolution=.01,max_age=180)
        for offset in range(0,361,30):
            r=m.update(BASE+offset,sample(-3.6,BASE+offset),sample(1200,BASE+offset))
        self.assertEqual(r['quality'],'counter_stalled')
        healthy=core.Monitor(sign=-1,energy_resolution=.01,max_age=180)
        healthy.update(BASE,sample(1,BASE),sample(1200,BASE))
        self.assertIsNone(healthy.update(BASE+1,sample(None,BASE+1),sample(1200,BASE+1))['forecast_kw'])

    def feed(self, monitor, duration, *, start=BASE, power=0, value=1200, energy_at=BASE-3600):
        for offset in range(0,duration+1,10):
            now=start+offset
            result=monitor.update(now,sample(power,now),sample(value,energy_at))
        return result

    def test_old_counter_during_pv_export_is_usable_after_observed_boundary(self):
        m=self.monitor()
        r=self.feed(m,1800,start=BASE+300,power=1.9)
        self.assertEqual(r['quality'],'valid')
        self.assertEqual(r['energy_freshness'],'quantized_idle')
        self.assertEqual(r['forecast_kw'],0)
        self.assertEqual(m.records[BASE+900]['kw'],0)
        self.assertEqual(m.records[BASE+900]['method'],'quantized_counter')
        self.assertIsNone(m.records[BASE]['kw'], 'startup quarter must remain incomplete')

    def test_small_import_below_meter_step_is_not_stale(self):
        m=self.monitor();r=self.feed(m,1800,power=-.011)
        self.assertEqual(r['quality'],'valid')
        self.assertGreater(r['forecast_kw'],0)
        self.assertAlmostEqual(m.expected_import,.0055)

    def test_frozen_counter_with_fresh_unchanged_reports_is_detected(self):
        m=self.monitor()
        for offset in range(0,161,10):
            r=m.update(BASE+offset,sample(-3.6,BASE+offset),sample(1200,BASE+offset))
            if offset==30:
                self.assertEqual(r['quality'],'valid')  # ordinary report lag is still bounded by max_age
        self.assertEqual(r['quality'],'counter_stalled')
        self.assertIsNone(r['forecast_kw'])

    def test_frozen_counter_with_old_timestamp_is_detected(self):
        m=self.monitor();r=self.feed(m,40,power=-3.6)
        self.assertEqual(r['quality'],'valid', 'an unconfirmed short pulse is not a fault')
        r=self.feed(m,80,start=BASE+50,power=-3.6)
        self.assertEqual(r['quality'],'waiting_report')
        self.assertIsNone(r['forecast_kw'])
        r=self.feed(m,60,start=BASE+140,power=-3.6)
        self.assertEqual(r['quality'],'counter_stalled')

    def test_normal_high_load_reports_every_minute_do_not_trigger_stall(self):
        m=self.monitor()
        for offset in range(0,3601,10):
            reported=(offset//60)*60
            r=m.update(BASE+offset,sample(-8,BASE+offset),sample(1200+reported*8/3600,BASE+reported))
            self.assertEqual(r['quality'],'valid')
        self.assertAlmostEqual(m.records[BASE+1800]['kw'],8)

    def test_tiny_import_accumulates_across_quarters_until_fault_is_detected(self):
        m=self.monitor();r=self.feed(m,6900,power=-.011)
        self.assertEqual(r['quality'],'counter_stalled')
        self.assertGreater(m.expected_import,.02)

    def test_counter_unavailable_cannot_be_hidden_by_export_and_cached_timestamp(self):
        m=self.monitor();self.feed(m,300,power=1.9)
        r=m.update(BASE+310,sample(1.9,BASE+310),sample(None,BASE-3600))
        self.assertIsNone(r['forecast_kw'])
        self.assertIsNone(m.proof_since)

    def test_counter_stall_survives_export_new_quarter_and_restart(self):
        m=self.monitor();self.feed(m,200,power=-3.6)
        r=self.feed(m,1800,start=BASE+210,power=1.9)
        self.assertEqual(r['quality'],'counter_stalled')
        restored=self.monitor();restored.restore(json.loads(json.dumps(m.dump())),BASE+2020)
        r=restored.update(BASE+2020,sample(1.9,BASE+2020),sample(1200,BASE-3600))
        self.assertEqual(r['quality'],'counter_stalled')
        self.assertIsNone(r['forecast_kw'])

    def test_fault_confirmation_crossing_boundary_does_not_finalize_false_zero(self):
        m=self.monitor()
        for offset in range(0,1101,10):
            power=0 if offset<850 else -3.6
            r=m.update(BASE+offset,sample(power,BASE+offset),sample(1200,BASE+offset))
            if offset==900:
                self.assertNotIn(BASE,m.records)
        self.assertIsNone(m.records[BASE]['kw'])
        self.assertEqual(m.records[BASE]['quality'],'counter_stalled')

    def test_restart_during_pending_fault_keeps_affected_window_incomplete(self):
        m=self.monitor()
        for offset in range(0,901,10):
            m.update(BASE+offset,sample(-3.6 if offset>=850 else 0,BASE+offset),sample(1200,BASE+offset))
        restored=self.monitor();restored.restore(json.loads(json.dumps(m.dump())),BASE+920)
        restored.update(BASE+920,sample(0,BASE+920),sample(1200,BASE+920))
        self.assertIsNone(restored.records[BASE]['kw'])

    def test_real_counter_increase_recovers_but_damaged_quarter_stays_invalid(self):
        m=self.monitor();self.feed(m,200,power=-3.6)
        r=m.update(BASE+210,sample(1.9,BASE+210),sample(1200.21,BASE+210))
        self.assertFalse(m.counter_stalled)
        self.assertIsNone(r['forecast_kw'])
        r=self.feed(m,1000,start=BASE+220,power=1.9,value=1200.21,energy_at=BASE+210)
        self.assertEqual(r['quality'],'valid')
        self.assertIsNone(m.records[BASE]['kw'])

    def test_unavailable_energy_immediately_stops_calculation(self):
        m=self.monitor();self.feed(m,300)
        r=m.update(BASE+310,sample(1.9,BASE+310),sample(None,BASE+310))
        self.assertIsNone(r['forecast_kw'])

    def test_power_silence_stops_even_during_export(self):
        m=self.monitor();self.feed(m,300,power=1.9)
        r=m.update(BASE+430,sample(1.9,BASE+300),sample(1200,BASE-3600))
        self.assertEqual(r['quality'],'power_stale')
        self.assertIsNone(r['forecast_kw'])
        r=self.feed(m,1000,start=BASE+440,power=1.9)
        self.assertIsNone(m.records[BASE]['kw'])

    def test_observation_gap_never_certifies_unobserved_import(self):
        m=self.monitor();self.feed(m,300)
        r=m.update(BASE+1810,sample(1.9,BASE+1810),sample(1200,BASE-3600))
        self.assertIsNone(r['forecast_kw'])
        self.assertTrue(all(v['kw'] is None for v in m.records.values()))

    def test_no_continuity_proof_is_restored(self):
        m=self.monitor();self.feed(m,300,start=BASE+900)
        restored=self.monitor();restored.restore(json.loads(json.dumps(m.dump())),BASE+1230)
        r=restored.update(BASE+1230,sample(1.9,BASE+1230),sample(1200,BASE-3600))
        self.assertIsNone(r['forecast_kw'])

    def test_regular_ten_wh_steps_under_low_load_cross_quarters(self):
        m=self.monitor();last=BASE-3600;value=1200
        for offset in range(0,5401,10):
            step=int(offset/360)
            if value!=1200+step*.01:value=1200+step*.01;last=BASE+offset
            r=m.update(BASE+offset,sample(-.1,BASE+offset),sample(value,last))
            self.assertNotEqual(r['quality'],'counter_stalled')
        self.assertEqual(r['quality'],'valid')
        self.assertAlmostEqual(m.records[BASE+1800]['kw'],.08)
        self.assertTrue(all(v['quality']=='valid' for v in m.records.values()))

    def test_counter_reset_and_unplausible_jump_still_block(self):
        for value,reason in ((1,'counter_reset'),(2000,'energy_jump')):
            m=self.monitor();self.feed(m,300)
            r=m.update(BASE+310,sample(-1,BASE+310),sample(value,BASE+310))
            self.assertEqual(r['quality'],reason)
            self.assertIsNone(r['forecast_kw'])

    def test_repeated_large_short_corrections_never_accumulate_a_false_alarm(self):
        m=self.monitor()
        # Individually small corrections exceed two steps only when accumulated.
        for offset in range(0,8*3600+1,10):
            power=-1.2 if offset%300<30 else .05
            r=m.update(BASE+offset,sample(power,BASE+offset),sample(1200,BASE-3600))
            self.assertEqual(r['quality'],'valid',offset)
        self.assertFalse(m.counter_stalled)

    def test_large_confirmed_pulse_cannot_hide_frozen_counter_after_export(self):
        m=self.monitor();self.feed(m,60,power=-8)
        self.assertIsNotNone(m.pulse_due_since)
        r=self.feed(m,100,start=BASE+70,power=.05)
        self.assertEqual(r['quality'],'counter_stalled')
        self.assertIsNone(r['forecast_kw'])

    def test_large_pulse_recovers_when_counter_really_advances(self):
        m=self.monitor();self.feed(m,60,power=-8)
        r=m.update(BASE+70,sample(.05,BASE+70),sample(1200.13,BASE+70))
        self.assertIsNone(m.pulse_due_since)
        self.assertFalse(m.counter_stalled)
        self.assertAlmostEqual(r['minimum_kw'],.52)

    def test_large_pulse_during_boundary_keeps_failed_archive_incomplete(self):
        m=self.monitor()
        for offset in range(0,1101,10):
            power=-8 if 850<=offset<910 else .05
            m.update(BASE+offset,sample(power,BASE+offset),sample(1200,BASE+offset))
        self.assertEqual(m.records[BASE]['quality'],'counter_stalled')
        self.assertIsNone(m.records[BASE]['kw'])

    def test_source_loss_during_large_pulse_check_cannot_create_valid_zero(self):
        m=self.monitor();self.feed(m,60,power=-8)
        r=m.update(BASE+70,sample(None,BASE+70),sample(None,BASE+70))
        self.assertIsNone(r['forecast_kw'])
        self.feed(m,1100,start=BASE+80,power=.05,energy_at=BASE+80)
        self.assertIsNone(m.records[BASE]['kw'])

    def test_cached_high_power_reading_is_not_repeated_import_evidence(self):
        m=self.monitor()
        m.update(BASE,sample(0,BASE),sample(1200,BASE-3600))
        for offset in range(10,121,10):
            r=m.update(BASE+offset,sample(-8,BASE+10),sample(1200,BASE-3600))
            self.assertEqual(m.expected_import,0)
            self.assertFalse(m.sustained_import)
            self.assertEqual(r['quality'],'valid')
        r=m.update(BASE+140,sample(-8,BASE+10),sample(1200,BASE-3600))
        self.assertEqual(r['quality'],'power_stale')
        self.assertIsNone(r['forecast_kw'])

    def test_confirmation_requires_new_reports_spanning_full_import_duration(self):
        m=self.monitor()
        m.update(BASE,sample(-3.6,BASE),sample(1200,BASE-3600))
        m.update(BASE+30,sample(-3.6,BASE+30),sample(1200,BASE-3600))
        for offset in range(40,151,10):
            r=m.update(BASE+offset,sample(-3.6,BASE+30),sample(1200,BASE-3600))
            self.assertFalse(m.counter_stalled)
        r=m.update(BASE+150,sample(-3.6,BASE+150),sample(1200,BASE-3600))
        self.assertEqual(r['quality'],'counter_stalled')

    def test_export_ends_pending_episode_but_does_not_cancel_import_energy(self):
        m=self.monitor();self.feed(m,60,power=-8)
        self.assertIsNotNone(m.change_due_since)
        r=m.update(BASE+70,sample(.01,BASE+70),sample(1200.1,BASE+70))
        self.assertEqual(m.expected_import,0)
        self.assertIsNone(m.change_due_since)
        self.assertAlmostEqual(r['used_kwh'],.1)
        self.assertAlmostEqual(r['minimum_kw'],.4)

    def test_true_sustained_failure_after_hours_of_regulation_is_detected(self):
        m=self.monitor()
        for offset in range(0,3601,10):
            m.update(BASE+offset,sample(-2 if offset%120<20 else .05,BASE+offset),sample(1200,BASE-3600))
        self.assertFalse(m.counter_stalled)
        for offset in range(3610,3911,10):
            r=m.update(BASE+offset,sample(-.5,BASE+offset),sample(1200,BASE+offset))
        self.assertEqual(r['quality'],'counter_stalled')
        self.assertIsNone(r['forecast_kw'])

    def test_upgrade_rechecks_old_alarm_without_rewriting_history(self):
        m=self.monitor();self.feed(m,200,power=-3.6)
        old=m.dump();old.pop('counter_guard_version')
        restored=self.monitor();restored.restore(json.loads(json.dumps(old)),BASE+210)
        self.assertFalse(restored.counter_stalled)
        r=self.feed(restored,1800,start=BASE+210,power=.05)
        self.assertEqual(r['quality'],'valid')
        self.assertIsNone(restored.records[BASE]['kw'])


if __name__=='__main__':unittest.main()
