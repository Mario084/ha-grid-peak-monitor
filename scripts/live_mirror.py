"""Copy two remote states into this test HA; every remote request is GET-only."""
import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from homeassistant.config_entries import ConfigEntryState
from read_only_source import StateReader, SourceConfig, ReadError




async def configure_flow(hass, flow_id, data):
    """Use both forms of the real guided setup with synthetic sources."""
    sources = {k: data[k] for k in ("name", "power_sensor", "energy_sensor")}
    result = await hass.config_entries.flow.async_configure(flow_id, sources)
    if result["type"] != "form" or result["step_id"] != "settings":
        return result
    advanced = {k: data[k] for k in ("max_age", "energy_resolution_kwh") if k in data}
    return await hass.config_entries.flow.async_configure(flow_id, {
        "import_sign": "positive" if int(data["import_sign"]) == 1 else "negative", "target_kw": data["target_kw"], "advanced": advanced})


class LiveMirror:
    def __init__(self,hass,config_path,on_ready,*,status_path=None,audit=None):
        self.hass=hass
        self.path=Path(config_path)
        self.on_ready=on_ready
        self.audit=audit
        self.status_path=Path(status_path) if status_path else self.path.with_name('live-status.json')
        self._fingerprint=None
        self.config=None
        self.reader=None
        self.entry=None
        self.ids=()
        self._announced=None

    def status(self,state,**extra):
        # No token, address, original entity names or values in this status file.
        path=self.status_path
        try:path.write_text(json.dumps({'state':state,**extra}))
        except OSError:pass

    def _load(self):
        if not self.path.exists():return False
        raw=self.path.read_bytes()
        fingerprint=hashlib.sha256(raw).hexdigest()
        if fingerprint==self._fingerprint:return True
        config=SourceConfig.parse(json.loads(raw))
        identity=hashlib.sha256((config.url+'|'+config.power_entity+'|'+config.energy_entity).encode()).hexdigest()[:12]
        self.ids=(f'sensor.live_grid_power_{identity}',f'sensor.live_import_energy_{identity}')
        self.config=config
        self.reader=StateReader(config.url,config.token,(config.power_entity,config.energy_entity))
        self._fingerprint=fingerprint
        self.entry=None
        self._announced=None
        return True

    def _unavailable(self):
        for entity in self.ids:
            state=self.hass.states.get(entity)
            self.hass.states.async_set(entity,'unavailable',dict(state.attributes) if state else {})

    async def tick(self):
        try:
            if not self._load():return
            pair=await asyncio.to_thread(self.reader.pair,self.config)
            for entity,state in zip(self.ids,pair,strict=True):
                self.hass.states.async_set(entity,state['state'],state['attributes'])
            if any(state['state']=='unavailable' for state in pair):
                self.status('waiting_for_values')
                return
            if self.entry is None:
                self.entry=next((entry for entry in self.hass.config_entries.async_entries('grid_peak_monitor')
                    if entry.data.get('power_sensor')==self.ids[0] and entry.data.get('energy_sensor')==self.ids[1]),None)
                if self.entry is None:
                    flow=await self.hass.config_entries.flow.async_init('grid_peak_monitor',context={'source':'user'})
                    result=await configure_flow(self.hass, flow['flow_id'],{
                        'name':'Echte Messdaten','power_sensor':self.ids[0],'energy_sensor':self.ids[1],
                        'import_sign':str(self.config.import_sign),'target_kw':self.config.target_kw,'max_age':self.config.max_age,'energy_resolution_kwh':self.config.energy_resolution_kwh,
                    })
                    if result['type']!='create_entry':raise ReadError('test_setup_failed')
                    self.entry=result['result']
                elif self.entry.state==ConfigEntryState.NOT_LOADED:
                    await self.hass.config_entries.async_setup(self.entry.entry_id)
                # A revision makes setup changes apply once, while retaining target
                # changes made later with the HA number entity across restarts.
                revision=hashlib.sha256(json.dumps([self.config.import_sign,self.config.target_kw,self.config.max_age,self.config.energy_resolution_kwh]).encode()).hexdigest()
                if self.entry.data.get('mirror_settings_revision')!=revision:
                    options={**self.entry.options,'import_sign':self.config.import_sign,'target_kw':self.config.target_kw,'max_age':self.config.max_age,'energy_resolution_kwh':self.config.energy_resolution_kwh}
                    self.hass.config_entries.async_update_entry(self.entry,data={**self.entry.data,'mirror_settings_revision':revision},options=options)
                await self.hass.async_block_till_done()
            # Let state report callbacks complete before capturing their result.
            await asyncio.sleep(0)
            coordinator=self.hass.data.get('grid_peak_monitor',{}).get(self.entry.entry_id)
            if coordinator is None:
                self.entry=None
                self.status('test_reloading')
                return
            if self._announced!=self.entry.entry_id:
                self.on_ready(self.entry)
                self._announced=self.entry.entry_id
            audit_status='off'
            if self.audit is not None:
                try:
                    self.audit.capture(coordinator)
                    audit_status='recording'
                except (OSError,ValueError,TypeError):
                    audit_status='write_failed'
            quality=(coordinator.data or {}).get('quality')
            self.status('active',quality=quality,audit=audit_status)
        except ReadError as error:
            self._unavailable()
            self.status('source_unavailable',reason=str(error))
        except (ValueError,TypeError,KeyError,OSError):
            self._unavailable()
            self.status('invalid_local_config')
        except Exception:
            self._unavailable()
            self.status('test_setup_failed')
