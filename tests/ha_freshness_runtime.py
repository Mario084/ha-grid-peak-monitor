"""Real HA adapter, simulated clock/sources, no network or existing HA config."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant import bootstrap, loader
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from live_audit import LiveAudit
from verify_live_capture import check




async def configure_flow(hass, flow_id, data):
    """Use both forms of the real guided setup with synthetic sources."""
    sources = {k: data[k] for k in ("name", "power_sensor", "energy_sensor")}
    result = await hass.config_entries.flow.async_configure(flow_id, sources)
    if result["type"] != "form" or result["step_id"] != "settings":
        return result
    advanced = {k: data[k] for k in ("max_age", "energy_resolution_kwh") if k in data}
    return await hass.config_entries.flow.async_configure(flow_id, {
        "import_sign": "positive" if int(data["import_sign"]) == 1 else "negative", "target_kw": data["target_kw"], "advanced": advanced})


async def main():
    with tempfile.TemporaryDirectory(prefix='freshness-ha-') as directory:
        config = Path(directory)
        shutil.copytree(ROOT / 'custom_components', config / 'custom_components')
        hass = HomeAssistant(str(config)); loader.async_setup(hass)
        await bootstrap.async_from_config_dict({
            'homeassistant': {'name': 'Freshness test', 'time_zone': 'Europe/Vienna',
                             'country': 'AT', 'latitude': 48.2, 'longitude': 16.3, 'unit_system': 'metric'},
            'http': {'server_host': '127.0.0.1', 'server_port': 8123},
            'frontend': {}, 'grid_peak_monitor': {},
        }, hass)
        await hass.async_start()
        try:
            hass.states.async_set('sensor.test_power', '0', {'unit_of_measurement': 'W'})
            hass.states.async_set('sensor.test_energy', '1200', {'unit_of_measurement': 'kWh', 'state_class': 'total_increasing'})
            flow = await hass.config_entries.flow.async_init('grid_peak_monitor', context={'source': 'user'})
            result = await configure_flow(hass, flow['flow_id'], {
                'name': 'Quantized counter', 'power_sensor': 'sensor.test_power', 'energy_sensor': 'sensor.test_energy',
                'import_sign': '-1', 'target_kw': 10, 'max_age': 120, 'energy_resolution_kwh': .01,
            })
            assert result['type'] == 'create_entry', result
            await hass.async_block_till_done()
            coordinator = hass.data['grid_peak_monitor'][result['result'].entry_id]
            assert coordinator.monitor.energy_resolution == .01
            from custom_components.grid_peak_monitor.core import Monitor
            coordinator.monitor = Monitor(sign=-1, target=10, energy_resolution=.01)
            audit = LiveAudit(config / 'capture.jsonl')
            base = 1792828800
            now = base + 300
            clock = SimpleNamespace(utcnow=lambda: datetime.fromtimestamp(now, timezone.utc), parse_datetime=dt_util.parse_datetime)

            async def publish(power, energy=1200, energy_at=None, power_at=None):
                for entity, value, unit, stamp in (
                    ('sensor.test_power', power, 'W', now if power_at is None else power_at),
                    ('sensor.test_energy', energy, 'kWh', base-3600 if energy_at is None else energy_at),
                ):
                    hass.states.async_set(entity, str(value), {
                        'unit_of_measurement': unit, 'state_class': 'measurement' if unit=='W' else 'total_increasing',
                        'grid_peak_source_reported_at': datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
                    })
                await hass.async_block_till_done()
                coordinator.async_set_updated_data(coordinator._compute())
                await hass.async_block_till_done()
                audit.capture(coordinator)
                return coordinator.data

            with patch('custom_components.grid_peak_monitor.coordinator.dt_util', clock):
                for now in range(base+300, base+2110, 10):
                    snapshot = await publish(100)  # export; PV production itself is not the input
                    if now < base+900:
                        assert snapshot['forecast_kw'] is None
                assert snapshot['quality'] == 'valid', snapshot
                assert snapshot['forecast_kw'] == 0
                assert snapshot['energy_freshness'] == 'quantized_idle'
                assert coordinator.monitor.last_energy.at == base-3600, 'never forge report times'
                assert coordinator.monitor.records[base+900]['method'] == 'quantized_counter'
                assert coordinator.monitor.records[base]['kw'] is None
                pv_report = check([json.loads(line) for line in audit.path.read_text().splitlines()])
                assert not pv_report['arithmetic_errors'], pv_report
                assert pv_report['valid_live_calculations'] > 0
                frozen_power_at = now
                now += 130
                snapshot = await publish(100, power_at=frozen_power_at)
                assert snapshot['quality'] == 'power_stale' and snapshot['forecast_kw'] is None
                # Counter is frozen, even though its timestamp keeps advancing.
                for now in range(now+10, base+2700, 10):
                    await publish(0, energy_at=now)
                # Repeated short corrections must never add up to an alarm,
                # even with a stale, unchanged counter.
                for now in range(base+2700, base+6300, 10):
                    snapshot = await publish(-1200 if (now-base)%300<30 else 50, energy_at=base+2690)
                    assert snapshot['quality'] == 'valid', snapshot
                    assert snapshot['forecast_kw'] is not None
                failure_start = base+6300
                for now in range(failure_start, failure_start+180, 10):
                    snapshot = await publish(-3600, energy_at=now)
                    if now == failure_start+40:
                        assert snapshot['quality'] == 'valid'  # bounded normal report lag
                assert snapshot['quality'] == 'counter_stalled' and snapshot['forecast_kw'] is None
                now += 10
                snapshot = await publish(100, energy_at=now)
                assert snapshot['quality'] == 'counter_stalled', 'export must not hide a proven fault'
                now += 10
                await publish(100, energy=1200.2, energy_at=now)
                assert not coordinator.monitor.counter_stalled
                recovered_at = now
                for now in range(now+10, base+7250, 10):
                    snapshot = await publish(100, energy=1200.2, energy_at=recovered_at)
                assert snapshot['quality'] == 'valid'
                now += 10
                snapshot = await publish(100, energy='unavailable', energy_at=now)
                assert snapshot['forecast_kw'] is None
                # Sensor entities expose the same guarded snapshot as the card.
                forecast = next(s for s in hass.states.async_all() if s.attributes.get('metric') == 'forecast_kw')
                assert forecast.attributes['snapshot']['quality'] != 'valid'
                # A genuinely large reported pulse still requires counter
                # progress, even after power returns to export.
                coordinator.monitor = Monitor(sign=-1, target=10, energy_resolution=.01)
                for now in range(base+8100, base+8170, 10):
                    await publish(-8000, energy_at=base+8090)
                for now in range(base+8170, base+8320, 10):
                    snapshot = await publish(50, energy_at=base+8090)
                assert snapshot['quality'] == 'counter_stalled' and snapshot['forecast_kw'] is None
                # Offset 10-Wh reports must not alter only the next quarter's
                # baseline after the previous quarter has been archived.
                coordinator.monitor = Monitor(sign=-1, target=10, energy_resolution=.01)
                origin = base+9000
                for offset in range(-60,1861,5):
                    now = origin+offset
                    reported = ((offset-30)//60)*60+30
                    await publish(-600, energy=100+reported*.6/3600, energy_at=origin+reported)
                for at in (origin,origin+900):
                    assert abs(coordinator.monitor.records[at]['kw']-.6)<1e-8
                coordinator.monitor = Monitor(sign=-1, target=10, energy_resolution=.01, max_age=180)
                now=base+11700
                # Keep the existing source value while switching test scenarios;
                # HA reports each entity separately, so an artificial jump from
                # 100 to 1200 would correctly invalidate this new quarter.
                counter=float(hass.states.get('sensor.test_energy').state)
                await publish(-600,energy=counter,energy_at=now)
                source_at=now;now+=124
                snapshot=await publish(-600,energy=counter+.02,energy_at=now,power_at=source_at)
                assert snapshot['quality']=='valid', snapshot
                now=source_at+181
                snapshot=await publish(-600,energy=counter+.03,energy_at=now,power_at=source_at)
                assert snapshot['quality']=='power_stale' and snapshot['forecast_kw'] is None
            print(json.dumps({'real_HA_freshness': True, 'pv_idle_accepted': True,
                'original_timestamp_preserved': True, 'startup_partial_rejected': True,
                'power_silence_rejected': True, 'fresh_timestamp_frozen_counter_rejected': True,
                'battery_correction_train_no_alarm': True,
                'large_pulse_frozen_counter_rejected': True,
                'fault_latched_during_export': True, 'real_counter_change_recovers': True,
                'unavailable_rejected': True, 'pv_calculations_checked': pv_report['valid_live_calculations'],
                'offset_quantized_archive_consistent': True,
                'explicit_180s_deadline_accepts_124s_but_rejects_181s': True,
                'production_contacted': False}))
            if len(sys.argv) == 3 and sys.argv[1] == '--replay':
                source_rows = [json.loads(line) for line in Path(sys.argv[2]).read_text().splitlines() if line]
                assert source_rows
                coordinator.monitor = Monitor(sign=source_rows[0]['import_sign'], target=10, energy_resolution=.01)
                audit = LiveAudit(config / 'real-replay.jsonl')
                with patch('custom_components.grid_peak_monitor.coordinator.dt_util', clock):
                    for row in source_rows:
                        now = row['calculated_at']
                        await publish(row['power']['value']*1000, energy=row['energy']['value'],
                                      energy_at=row['energy']['at'], power_at=row['power']['at'])
                report = check([json.loads(line) for line in audit.path.read_text().splitlines()])
                assert report['status'] == 'passed', report
                assert report['quantized_idle_calculations'] > 0
                print(json.dumps({'real_source_capture_in_HA': True, 'offline_replay': True,
                    'samples': report['samples'], 'calculations_checked': report['valid_live_calculations'],
                    'quantized_idle_calculations': report['quantized_idle_calculations'],
                    'verified_intervals': report['independently_verified_intervals'],
                    'arithmetic_errors': report['arithmetic_errors'], 'production_contacted': False}))
        finally:
            await hass.async_stop()


if __name__ == '__main__':
    with patch('homeassistant.components.analytics.async_setup_entry', new=AsyncMock(return_value=True)):
        asyncio.run(main())
