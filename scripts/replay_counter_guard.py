"""Offline regression of captured source reports; never contacts either HA.

Only a new in-memory monitor is used. The running monitor's archive is untouched.
Private capture/result files stay outside the distributable source allowlist.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sys

from verify_live_capture import check

ROOT = Path(__file__).resolve().parents[1]


def replay(rows):
    spec = importlib.util.spec_from_file_location('guard_replay_core', ROOT/'custom_components/grid_peak_monitor/core.py')
    core = importlib.util.module_from_spec(spec); sys.modules[spec.name] = core; spec.loader.exec_module(core)
    monitor = core.Monitor(sign=rows[0]['import_sign'], target=rows[0]['snapshot']['target_kw'],
                           max_age=rows[0]['max_age'], energy_resolution=.01)
    captured = []
    for row in rows:
        now = row['calculated_at']
        snapshot = monitor.update(now, core.Sample(**row['power']), core.Sample(**row['energy']))
        captured.append({'calculated_at': now, 'power': row['power'], 'energy': row['energy'],
            'import_sign': monitor.sign, 'max_age': monitor.max_age,
            'energy_resolution_kwh': monitor.energy_resolution, 'continuity_since': monitor.proof_since,
            'counter_guard_version': core.COUNTER_GUARD_VERSION,
            'baseline_kwh': monitor.anchors.get(snapshot['start']),
            'accepted_energy': asdict(monitor.last_energy) if monitor.last_energy else None,
            'snapshot': snapshot, 'records': sorted(monitor.records.values(), key=lambda r:r['start'])[-4:]})
    report = check(captured)
    report.update(kind='offline_counter_guard_regression', production_contacted=False,
                  old_quality_counts=dict(Counter(r['snapshot']['quality'] for r in rows)),
                  new_quality_counts=dict(Counter(r['snapshot']['quality'] for r in captured)))
    # Inject a genuine freeze after the same battery trace; sources still report.
    start = rows[-1]['calculated_at']
    value = rows[-1]['energy']['value']
    failure_at = None
    for elapsed in range(30, 601, 30):
        now = start + elapsed
        snapshot = monitor.update(now, core.Sample(3.6/monitor.sign, now), core.Sample(value, now))
        if snapshot['quality'] == 'counter_stalled':
            failure_at = elapsed
            break
    report['injected_sustained_freeze_detected_after_s'] = failure_at
    report['injected_freeze_forecast_is_none'] = snapshot['forecast_kw'] is None
    return report, captured


def private_json(path, value, *, lines=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Open privately before writing; these are private local observations.
    import os
    fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w') as output:
        if lines:
            for row in value: output.write(json.dumps(row, allow_nan=False)+'\n')
        else:
            json.dump(value, output, indent=2, ensure_ascii=False, allow_nan=False); output.write('\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('capture', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--replayed-capture', type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.capture.read_text().splitlines() if line.strip()]
    if not rows: raise SystemExit('Capture is empty')
    report, captured = replay(rows)
    private_json(args.output, report)
    if args.replayed_capture: private_json(args.replayed_capture, captured, lines=True)
    print(json.dumps({k:report[k] for k in ('status','samples','valid_live_calculations','arithmetic_errors',
        'old_quality_counts','new_quality_counts','injected_sustained_freeze_detected_after_s',
        'injected_freeze_forecast_is_none')}, ensure_ascii=False))
    if report['status']=='failed' or report['injected_sustained_freeze_detected_after_s'] is None:
        raise SystemExit(1)
