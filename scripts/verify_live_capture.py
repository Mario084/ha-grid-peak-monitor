"""Independent arithmetic check of a private live capture. No network or HA API.

This module does not import the integration's accounting code.
"""
import argparse
from bisect import bisect_left
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal
import json
import math
from pathlib import Path


def close(actual,expected):
    return actual is not None and math.isfinite(float(actual)) and math.isclose(float(actual),float(expected),rel_tol=1e-9,abs_tol=1e-6)


def check(rows):
    errors=[];quality=Counter();valid=0;partial=0;bounds={};points={};observed=[];quantized=0
    def fail(index,field,actual,expected):
        errors.append({'sample':index,'field':field,'actual':actual,'expected':expected})
    for index,row in enumerate(rows):
        now=row['calculated_at'];s=row['snapshot'];q=s.get('quality');quality[q]+=1
        observed.append(now)
        e=row.get('energy') or {}
        if e.get('value') is not None:points[e['at']]=e['value']
        for record in row.get('records',[]):bounds[record['start']]=record
        start=math.floor(now/900)*900
        for field,expected in (('start',start),('end',start+900)):
            if s.get(field)!=expected:fail(index,field,s.get(field),expected)
        power=row.get('power') or {};p=power.get('value');age=now-power.get('at',0)
        imported=max(0,row['import_sign']*p) if p is not None and -5<=age<=row['max_age'] else None
        if imported is None:
            if s.get('power_kw') is not None:fail(index,'power_kw',s.get('power_kw'),None)
        elif not close(s.get('power_kw'),imported):fail(index,'power_kw',s.get('power_kw'),imported)
        if q!='valid':
            partial+=1
            for field in ('used_kwh','minimum_kw','forecast_kw','allowed_power_kw','additional_power_kw','headroom_kw'):
                if s.get(field) is not None:fail(index,field,s.get(field),None)
            continue
        baseline=row.get('baseline_kwh');accepted=row.get('accepted_energy') or {}
        if baseline is None or accepted.get('value') is None or imported is None:
            fail(index,'valid_inputs',False,True);continue
        valid+=1
        if s.get('energy_freshness')=='quantized_idle':
            quantized+=1
            since=row.get('continuity_since')
            resolution=row.get('energy_resolution_kwh',0)
            if not resolution or since is None or since>start:
                fail(index,'quantized_continuity',False,True)
            if e.get('value')!=accepted.get('value') or e.get('at')!=accepted.get('at'):
                fail(index,'original_energy_preserved',False,True)
        used=max(Decimal(0),Decimal(str(accepted['value']))-Decimal(str(baseline)))
        # Preserve the captured binary timestamp exactly. Decimal(str(now))
        # rounds epoch times and exaggerates sub-watt budget differences near a boundary.
        remaining=Decimal(start+900)-Decimal.from_float(now)
        target=Decimal(str(s['target_kw']));p=Decimal(str(imported))
        minimum=used*4
        forecast=minimum+p*remaining/900
        allowed=max(Decimal(0),(target-minimum)*900/remaining)
        expected={'used_kwh':used,'minimum_kw':minimum,'forecast_kw':forecast,
                  'allowed_power_kw':allowed,'additional_power_kw':allowed-p,
                  'headroom_kw':target-forecast}
        for field,value in expected.items():
            if not close(s.get(field),value):fail(index,field,s.get(field),float(value))
        if float(s['forecast_kw'])+1e-7<float(s['minimum_kw']):fail(index,'forecast_at_least_minimum',False,True)
    stamps=sorted(points)
    def anchor(at,max_age):
        idx=bisect_left(stamps,at)
        if idx<len(stamps) and stamps[idx]==at:return Decimal(str(points[at]))
        if idx==0 or idx==len(stamps):return None
        left,right=stamps[idx-1],stamps[idx]
        if right-left>max_age or points[right]<points[left]:return None
        return Decimal(str(points[left]))+(Decimal(str(points[right]))-Decimal(str(points[left])))*(Decimal(str(at))-Decimal(str(left)))/(Decimal(str(right))-Decimal(str(left)))
    verified=[];unchecked=[];incomplete=[]
    max_age=min((r['max_age'] for r in rows),default=120)
    ordered=sorted(rows,key=lambda r:r['calculated_at'])
    capture_times=[r['calculated_at'] for r in ordered]
    def observed_anchor(at):
        # A quantized boundary needs observations on BOTH sides. Do not use
        # the monitor's stored baseline as independent evidence for itself.
        idx=bisect_left(capture_times,at)
        if idx<len(ordered) and capture_times[idx]==at:
            item=ordered[idx]
            if item['snapshot'].get('quality')=='valid':
                return item['energy'].get('value')
        if idx==0 or idx==len(ordered):return None
        left,right=ordered[idx-1],ordered[idx]
        if right['calculated_at']-left['calculated_at']>max_age:return None
        if left['energy'].get('value')!=right['energy'].get('value'):return None
        return right['energy'].get('value')
    for at,record in sorted(bounds.items()):
        if record.get('quality')!='valid':
            incomplete.append(at)
            if record.get('kw') is not None:errors.append({'interval':at,'field':'invalid_interval_kw','actual':record.get('kw'),'expected':None})
            continue
        method=record.get('method','counter_interpolation')
        if method=='quantized_counter':
            lo,hi=observed_anchor(at),observed_anchor(at+900)
            covered=[r for r in ordered if at<=r['calculated_at']<=at+900]
            if (not covered or any(r['snapshot'].get('quality')!='valid' for r in covered)
                or any(b['calculated_at']-a['calculated_at']>max_age for a,b in zip(covered,covered[1:]))):
                lo=hi=None
            lo=Decimal(str(lo)) if lo is not None else None
            hi=Decimal(str(hi)) if hi is not None else None
        else:
            lo,hi=anchor(at,max_age),anchor(at+900,max_age)
        if lo is None or hi is None:
            unchecked.append(at);continue
        expected=(hi-lo)*4
        if expected<0 or not close(record.get('kw'),expected):
            errors.append({'interval':at,'field':'archive_kw','actual':record.get('kw'),'expected':float(expected)})
        else:verified.append({'start':at,'end':at+900,'kw':record['kw'],'independent_kw':float(expected),'method':method})
    status='failed' if errors else 'passed' if valid and verified else 'pending'
    return {'status':status,'network_requests':0,'samples':len(rows),'valid_live_calculations':valid,
        'unavailable_or_partial_samples':partial,'quality_counts':dict(quality),'arithmetic_errors':errors,
        'quantized_idle_calculations':quantized,
        'independently_verified_intervals':verified,'valid_intervals_without_complete_capture':unchecked,
        'incomplete_intervals':incomplete,'capture_start':min(observed) if observed else None,
        'capture_end':max(observed) if observed else None,
        'limitation':'Checks local energy-derived estimates, not the grid operator meter or billing.'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('capture',nargs='?',type=Path,default=Path(__file__).resolve().parents[1]/'output/ha-preview-config/live-audit.jsonl')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.capture.exists():
        print(json.dumps({'status':'pending','reason':'capture_not_started'}));return
    rows=[json.loads(line) for line in args.capture.read_text().splitlines() if line.strip()]
    result=check(rows)
    if args.output:
        args.output.parent.mkdir(exist_ok=True,parents=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result['status']=='failed':raise SystemExit(1)


if __name__=='__main__':main()
