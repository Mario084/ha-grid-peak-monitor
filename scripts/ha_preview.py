"""Persistent, separate HA demo. Never point /config at an existing HA instance."""
import asyncio
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
import shutil
import signal

from homeassistant import bootstrap, loader
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from live_mirror import LiveMirror
from live_audit import LiveAudit

PROJECT = Path(__file__).resolve().parents[1]
CONFIG = Path('/config')
MARKER = CONFIG/'.grid-peak-preview'
ORIGIN = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
logging.basicConfig(level=logging.WARNING)


def power(at):
    t = at - ORIGIN
    return 3.8 + 1.6*math.sin(t/1800) + math.sin(t/470)


def energy(at):
    t = at - ORIGIN
    return 50000 + (3.8*t + 1.6*1800*(1-math.cos(t/1800)) + 470*(1-math.cos(t/470)))/3600


def publish_sources(hass):
    now = datetime.now(timezone.utc).timestamp()
    hass.states.async_set('sensor.preview_grid_power', str(round(power(now)*1000, 3)), {'unit_of_measurement':'W','device_class':'power','friendly_name':'Demo Netzbezug'})
    hass.states.async_set('sensor.preview_import_energy', str(round(energy(now), 7)), {'unit_of_measurement':'kWh','device_class':'energy','state_class':'total_increasing','friendly_name':'Demo Netzimport'})


class PreviewData(HomeAssistantView):
    url = '/demo-data'
    name = 'grid_peak_preview:data'
    requires_auth = False  # Only synthetic demo data, on this separate LAN instance.

    def __init__(self, coordinator):
        self.coordinator = coordinator

    async def get(self, request):
        if self.coordinator is None:
            return self.json({'error':'starting'}, status_code=503)
        now = datetime.now(timezone.utc).timestamp()
        coordinator = self.coordinator.hass.data.get('grid_peak_monitor',{}).get(self.coordinator.entry.entry_id)
        if coordinator is None:
            return self.json({'error':'reloading'}, status_code=503)
        if coordinator.options.get('power_sensor')!='sensor.preview_grid_power' or coordinator.options.get('energy_sensor')!='sensor.preview_import_energy':
            return self.json({'error':'demo_unavailable'}, status_code=503)
        monitor = coordinator.monitor
        if 'date' in request.query:
            try:
                result = monitor.history(request.query['date'], request.query.get('month', request.query['date'][:7]), now)
            except (ValueError, KeyError):
                return self.json({'error':'invalid_date'}, status_code=400)
            return self.json(result)
        def device(name, watts):
            return {'state':str(round(watts)), 'attributes':{'friendly_name':name,'unit_of_measurement':'W'}}
        return self.json({'now':now,'zone':monitor.zone,'monitor_id':self.coordinator.entry.entry_id,
            'snapshot':coordinator.data,'devices':{
                'sensor.demo_heating':device('Heizung · Demo', max(0,power(now)*1000-900)),
                'sensor.demo_kitchen':device('Küche · Demo',550),
                'sensor.demo_base':device('Grundlast · Demo',350),
            }})




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
    CONFIG.mkdir(exist_ok=True)
    if not MARKER.exists():
        if any(CONFIG.iterdir()):
            raise RuntimeError('Refusing non-empty configuration without preview marker')
        MARKER.write_text('Separate Grid Peak Monitor demo. Synthetic sources only.\n')
    shutil.copytree(PROJECT/'custom_components', CONFIG/'custom_components', dirs_exist_ok=True)
    hass = HomeAssistant(str(CONFIG))
    loader.async_setup(hass)
    await bootstrap.async_from_config_dict({
        'homeassistant':{'name':'Netzspitzen · lokale Demo','time_zone':'Europe/Vienna','country':'AT','latitude':48.2,'longitude':16.3,'unit_system':'metric'},
        'http':{'server_host':'0.0.0.0','server_port':8123},
        'frontend':{},'onboarding':{},'lovelace':{'mode':'yaml','resources':[{'url':'/grid_peak_monitor_static/grid-peak-card.js?v=0.1.0-alpha.6','type':'module'}]},
        'grid_peak_monitor':{},
    }, hass)
    view = PreviewData(None)
    await hass.http.async_register_static_paths([StaticPathConfig('/demo',str(PROJECT/'demo'),False)])
    hass.http.register_view(view)
    await hass.async_start()
    publish_sources(hass)
    entries = [entry for entry in hass.config_entries.async_entries('grid_peak_monitor') if entry.data.get('power_sensor')=='sensor.preview_grid_power' and entry.data.get('energy_sensor')=='sensor.preview_import_energy']
    if not entries:
        flow = await hass.config_entries.flow.async_init('grid_peak_monitor', context={'source':'user'})
        result = await configure_flow(hass, flow['flow_id'], {
            'name':'Demo Netzspitzen','power_sensor':'sensor.preview_grid_power','energy_sensor':'sensor.preview_import_energy',
            'import_sign':'1','target_kw':8.0,'max_age':120,
        })
        assert result['type']=='create_entry',result
        entry = result['result']
    else:
        entry = entries[0]
        if entry.state == ConfigEntryState.NOT_LOADED:
            await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data['grid_peak_monitor'][entry.entry_id]
    now = datetime.now(timezone.utc).timestamp()
    start = int(now//900)*900
    # Seed only the artificial demo archive. Production integration has no seeder.
    if not coordinator.monitor.records:
        for at in range(start-8*86400,start,900):
            missing = at//900 % 29 == 0
            coordinator.monitor.records[at]={'start':at,'end':at+900,'kw':None if missing else (energy(at+900)-energy(at))*4,'quality':'missing' if missing else 'valid','source':'HA'}
    coordinator.monitor.anchors[start] = energy(start)
    coordinator.monitor.bad.pop(start,None)
    coordinator.async_set_updated_data(coordinator._compute())
    def write_dashboard(live_entry=None):
        registry=er.async_get(hass)
        def card_for(current):
            forecast=registry.async_get_entity_id('sensor','grid_peak_monitor',f'{current.entry_id}_forecast_kw')
            target=registry.async_get_entity_id('number','grid_peak_monitor',f'{current.entry_id}_target')
            return [{'type':'custom:grid-peak-card','entity':forecast,'title':current.title},
                    {'type':'entities','title':'Persönliches Ziel · nur diese Testintegration','entities':[target]}]
        views=[{'title':'Demo','path':'0','cards':[
            {'type':'markdown','content':'## Beispieldaten\nDiese Ansicht zeigt ausschließlich synthetische Messwerte. [Direkte Demo ohne Anmeldung](/demo/index.html).'},
            *card_for(entry),
        ]}]
        if live_entry:
            views.append({'title':'Echte Messdaten','path':'echte-messdaten','cards':[
                {'type':'markdown','content':'## Echte Messdaten · lesende Übernahme\nDiese Ansicht enthält kopierte Sensorwerte aus der produktiven HA-Instanz. Geschrieben wird ausschließlich hier in der Testinstanz. Das Archiv beginnt mit dem ersten vollständig erfassten Viertel.'},
                *card_for(live_entry),
            ]})
        else:
            views.append({'title':'Echte Messdaten','path':'echte-messdaten','cards':[
                {'type':'markdown','content':'## Echte Messdaten noch nicht verbunden\nDie lokale Einrichtung auf dem Mac mini öffnen und die beiden Quellsensoren auswählen. Die Demo bleibt davon getrennt.'}
            ]})
        (CONFIG/'ui-lovelace.yaml').write_text(json.dumps({'title':'Netzspitzen · Testinstanz','views':views},ensure_ascii=False,indent=2))
    write_dashboard()
    audit=LiveAudit(CONFIG/'live-audit.jsonl') if (CONFIG/'.grid-peak-live-audit').exists() else None
    live=LiveMirror(hass,PROJECT/'output/live-source.json',write_dashboard,status_path=CONFIG/'live-status.json',audit=audit)
    view.coordinator = coordinator
    stop = asyncio.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig,stop.set)
    print('Grid Peak Monitor demo ready: /demo/index.html and /lovelace/0',flush=True)
    try:
        while not stop.is_set():
            publish_sources(hass)
            await live.tick()
            try:
                await asyncio.wait_for(stop.wait(),timeout=5)
            except TimeoutError:
                pass
    finally:
        await hass.async_stop()


if __name__=='__main__':
    asyncio.run(main())
