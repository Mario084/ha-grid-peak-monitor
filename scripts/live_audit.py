"""Private test-instance capture; never sends requests to production HA."""
from dataclasses import asdict
import json
import os
from pathlib import Path


class LiveAudit:
    def __init__(self,path):
        self.path=Path(path)
        self.last=None

    def capture(self,coordinator):
        from custom_components.grid_peak_monitor.coordinator import sample
        monitor=coordinator.monitor
        at=monitor.last_tick
        if at is None or at==self.last:return
        snapshot=dict(coordinator.data or {})
        power=sample(coordinator.hass.states.get(coordinator.options['power_sensor']))
        energy=sample(coordinator.hass.states.get(coordinator.options['energy_sensor']),energy=True)
        row={'version':1,'calculated_at':at,'power':asdict(power),'energy':asdict(energy),
             'import_sign':monitor.sign,'max_age':monitor.max_age,
             'energy_resolution_kwh':getattr(monitor,'energy_resolution',0),
             'continuity_since':getattr(monitor,'proof_since',None),
             'counter_guard_version':snapshot.get('counter_guard_version'),
             'import_episode_since':getattr(monitor,'import_since',None),
             'sustained_import':getattr(monitor,'sustained_import',False),
             'expected_import_kwh':getattr(monitor,'expected_import',None),
             'pulse_due_since':getattr(monitor,'pulse_due_since',None),
             'baseline_kwh':monitor.anchors.get(snapshot.get('start')),
             'accepted_energy':asdict(monitor.last_energy) if monitor.last_energy else None,
             'snapshot':snapshot,
             'records':sorted(monitor.records.values(),key=lambda r:r['start'])[-4:]}
        self.path.parent.mkdir(exist_ok=True,parents=True)
        fd=os.open(self.path,os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
        with os.fdopen(fd,'a') as output:output.write(json.dumps(row,allow_nan=False)+'\n')
        self.last=at
