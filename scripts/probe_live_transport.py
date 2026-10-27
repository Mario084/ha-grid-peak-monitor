"""Compare two GET source responses with the private test capture. No writes to HA."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import time
from read_only_source import SourceConfig,StateReader

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    config=SourceConfig.parse(json.loads((ROOT/'output/live-source.json').read_text()))
    pair=StateReader(config.url,config.token,(config.power_entity,config.energy_entity)).pair(config)
    expected=[]
    for state,energy in zip(pair,(False,True)):
        unit=state['attributes'].get('unit_of_measurement')
        scales={'Wh':.001,'kWh':1,'MWh':1000} if energy else {'W':.001,'kW':1}
        expected.append({'value':float(state['state'])*scales[unit],
            'at':datetime.fromisoformat(state['attributes']['grid_peak_source_reported_at']).timestamp()})
    path=ROOT/'output/ha-preview-config/live-audit.jsonl'
    deadline=time.monotonic()+12
    matching=None
    while time.monotonic()<deadline:
        rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        matching=next((r for r in reversed(rows[-100:]) if r['power']==expected[0] and r['energy']==expected[1]),None)
        if matching:break
        time.sleep(.3)
    result={'status':'matched' if matching else 'not_observed_within_probe',
        'production_requests':[{'method':'GET','entity_id':entity} for entity in (config.power_entity,config.energy_entity)],
        'source_power_kw':expected[0]['value'],'source_power_reported_at':expected[0]['at'],
        'source_import_kwh':expected[1]['value'],'source_energy_reported_at':expected[1]['at'],
        'captured_at':matching['calculated_at'] if matching else None,
        'test_quality':matching['snapshot']['quality'] if matching else None,
        'exact_values_and_original_timestamps_match':bool(matching),
        'note':'A newer source report can replace the sampled pair before the bridge reads it; not_observed is inconclusive.'}
    if args.output:
        args.output.parent.mkdir(exist_ok=True,parents=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n');args.output.chmod(0o600)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
