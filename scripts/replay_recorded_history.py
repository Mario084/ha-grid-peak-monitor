"""Offline replay of two recorded source series; does not contact either HA."""
import argparse
from bisect import bisect_right
from dataclasses import asdict
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys
from verify_live_capture import check

ROOT=Path(__file__).resolve().parents[1]


def replay(history,config):
    spec=importlib.util.spec_from_file_location('recorded_peak_core',ROOT/'custom_components/grid_peak_monitor/core.py')
    core=importlib.util.module_from_spec(spec);sys.modules[spec.name]=core;spec.loader.exec_module(core)
    series={rows[0]['entity_id']:rows for rows in history['series'] if rows}
    def points(entity,scale):
        output=[]
        for state in series[entity]:
            stamp=datetime.fromisoformat(state.get('last_updated') or state['last_changed']).timestamp()
            try:value=float(state['state'])*scale
            except (ValueError,TypeError):value=None
            output.append((stamp,value))
        return sorted(output)
    power=points(config['power_entity'],{'W':.001,'kW':1}[history['power_unit']])
    energy=points(config['energy_entity'],{'Wh':.001,'kWh':1,'MWh':1000}[history['energy_unit']])
    start=max(power[0][0],energy[0][0]);end=datetime.fromisoformat(history['requested_end']).timestamp()
    monitor=core.Monitor(target=config.get('target_kw',8),sign=config['import_sign'],max_age=config['max_age'],
                         energy_resolution=config.get('energy_resolution_kwh',0))
    pstamps=[p[0] for p in power];estamps=[p[0] for p in energy]
    times=sorted(set([start,end]+pstamps+estamps+[float(t) for t in range(int(start)+1,int(end)+1,10)]))
    captured=[]
    for now in times:
        if not start<=now<=end:continue
        p=power[max(0,bisect_right(pstamps,now)-1)];e=energy[max(0,bisect_right(estamps,now)-1)]
        ps,es=core.Sample(p[1],p[0]),core.Sample(e[1],e[0])
        snapshot=monitor.update(now,ps,es)
        captured.append({'calculated_at':now,'power':asdict(ps),'energy':asdict(es),
            'accepted_energy':asdict(monitor.last_energy) if monitor.last_energy else None,
            'baseline_kwh':monitor.anchors.get(snapshot['start']),'import_sign':monitor.sign,
            'max_age':monitor.max_age,'snapshot':snapshot,
            'energy_resolution_kwh':monitor.energy_resolution,'continuity_since':monitor.proof_since,
            'records':sorted(monitor.records.values(),key=lambda r:r['start'])[-4:]})
    report=check(captured)
    report['kind']='replay_of_real_recorded_history'
    report['limitation']='Historical replay, not proof of current live snapshots. Recorder can omit unchanged reports. Counter interpolation is a local estimate.'
    report['example']=next(({'calculated_at':row['calculated_at'],**{k:row['snapshot'][k] for k in ('power_kw','used_kwh','minimum_kw','forecast_kw','allowed_power_kw','additional_power_kw','remaining_seconds')}} for row in captured if row['snapshot']['quality']=='valid' and 290<row['snapshot']['remaining_seconds']<310),None)
    comparisons=[]
    for interval in report['independently_verified_intervals']:
        lo,hi=interval['start'],interval['end']
        ticks=sorted(set([lo,hi]+[t for t in pstamps if lo<t<hi]))
        kwh=0
        for left,right in zip(ticks,ticks[1:]):
            p=power[max(0,bisect_right(pstamps,left)-1)][1]
            kwh+=max(0,config['import_sign']*p)*(right-left)/3600
        comparisons.append({'start':lo,'end':hi,'counter_average_kw':interval['kw'],
            'power_zero_order_hold_average_kw':kwh*4,
            'difference_kw':kwh*4-interval['kw'],
            'note':'Power samples are a plausibility check, not continuous meter data.'})
    report['power_plausibility']=comparisons
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('history',type=Path)
    parser.add_argument('--config',type=Path,default=ROOT/'output/live-source.json')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    # Only selection/settings are consumed. Credentials are never used or printed.
    config=json.loads(args.config.read_text())
    report=replay(json.loads(args.history.read_text()),config)
    if args.output:
        args.output.parent.mkdir(exist_ok=True,parents=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        args.output.chmod(0o600)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if report['status']=='failed':raise SystemExit(1)


if __name__=='__main__':main()
