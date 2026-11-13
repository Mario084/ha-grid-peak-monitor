"""Exercise source replacement in a disposable, network-isolated real HA."""
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import shutil
import tempfile
from unittest.mock import AsyncMock, patch

from homeassistant import bootstrap, loader
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

PROJECT = Path(__file__).resolve().parents[1]
DOMAIN = "grid_peak_monitor"
logging.basicConfig(level=logging.WARNING)


async def main():
    with tempfile.TemporaryDirectory(prefix="gpm-reconfigure-") as directory:
        config = Path(directory)
        shutil.copytree(PROJECT / "custom_components", config / "custom_components")
        hass = HomeAssistant(str(config))
        loader.async_setup(hass)
        await bootstrap.async_from_config_dict({
            "homeassistant": {"time_zone": "Europe/Vienna", "country": "AT",
                              "latitude": 48.2, "longitude": 16.3, "unit_system": "metric"},
            "http": {"server_host": "127.0.0.1", "server_port": 8123},
            "frontend": {}, DOMAIN: {},
        }, hass)
        await hass.async_start()
        try:
            def publish(suffix, watts="2000", energy="500.01"):
                hass.states.async_set(f"sensor.power_{suffix}", watts, {"unit_of_measurement": "W"})
                hass.states.async_set(f"sensor.energy_{suffix}", energy,
                    {"unit_of_measurement": "kWh", "state_class": "total_increasing"})

            def sources(suffix):
                return {"power_sensor": f"sensor.power_{suffix}", "energy_sensor": f"sensor.energy_{suffix}"}

            async def create(suffix):
                flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
                await hass.config_entries.flow.async_configure(flow["flow_id"], {"name": suffix, **sources(suffix)})
                result = await hass.config_entries.flow.async_configure(flow["flow_id"], {
                    "import_sign": "positive", "target_kw": 9.5,
                    "advanced": {"max_age": 180, "energy_resolution_kwh": .01}})
                assert result["type"] == "create_entry", result
                await hass.async_block_till_done()
                return result["result"]

            async def reconfigure():
                return await hass.config_entries.flow.async_init(DOMAIN,
                    context={"source": "reconfigure", "entry_id": entry.entry_id})

            def entity_ids():
                return {e.unique_id: e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}

            def coordinator():
                return hass.data[DOMAIN][entry.entry_id]

            publish("old"); publish("new", "-3500", "20.01"); publish("other")
            entry = await create("old")
            await create("other")
            ids = entity_ids()
            start = int(datetime.now(timezone.utc).timestamp() // 900) * 900
            coordinator().monitor.records[start - 900] = {
                "start": start - 900, "end": start, "kw": 2.5, "quality": "valid", "source": "HA"}
            await coordinator().store.async_save(coordinator()._dump())
            before_data, before_options = dict(entry.data), dict(entry.options)

            flow = await reconfigure()
            assert flow["step_id"] == "reconfigure"
            defaults = {str(k): k.default() for k in flow["data_schema"].schema}
            assert defaults == sources("old")
            unchanged = await hass.config_entries.flow.async_configure(flow["flow_id"], sources("old"))
            assert unchanged["reason"] == "sources_unchanged"
            assert coordinator().monitor.records[start - 900]["kw"] == 2.5
            assert not list((config / ".storage").glob("*.source_backup.*"))

            flow = await reconfigure()
            duplicate = await hass.config_entries.flow.async_configure(flow["flow_id"], sources("other"))
            assert duplicate["errors"]["base"] == "already_configured"
            hass.states.async_set("sensor.power_new", "unavailable", {"unit_of_measurement": "W"})
            missing = await hass.config_entries.flow.async_configure(flow["flow_id"], sources("new"))
            assert missing["errors"]["power_sensor"] == "source_unavailable"
            publish("new", "-3500", "20.01")
            confirm = await hass.config_entries.flow.async_configure(flow["flow_id"], sources("new"))
            assert confirm["step_id"] == "reconfigure_confirm"
            hass.config_entries.flow.async_abort(flow["flow_id"])
            assert dict(entry.data) == before_data and dict(entry.options) == before_options
            assert coordinator().monitor.records[start - 900]["kw"] == 2.5

            flow = await reconfigure()
            await hass.config_entries.flow.async_configure(flow["flow_id"], sources("new"))
            rejected = await hass.config_entries.flow.async_configure(flow["flow_id"], {"import_sign": "choose", "target_kw": 9.5})
            assert rejected["errors"]["import_sign"] == "direction_required"
            hass.states.async_set("sensor.energy_new", "unavailable", {"unit_of_measurement": "kWh", "state_class": "total_increasing"})
            rejected = await hass.config_entries.flow.async_configure(flow["flow_id"], {"import_sign": "negative", "target_kw": 9.5})
            assert rejected["errors"]["base"] == "sources_changed"
            publish("new", "-3500", "20.01")
            result = await hass.config_entries.flow.async_configure(flow["flow_id"], {"import_sign": "negative", "target_kw": 9.5})
            assert result["reason"] == "reconfigure_successful"
            await hass.async_block_till_done()
            assert entry.state == ConfigEntryState.LOADED
            assert entity_ids() == ids and len(hass.config_entries.async_entries(DOMAIN)) == 2
            assert entry.unique_id == "sensor.power_new|sensor.energy_new"
            assert coordinator().monitor.target == 9.5 and coordinator().monitor.max_age == 180
            assert coordinator().monitor.energy_resolution == 0
            assert coordinator().data["power_kw"] == 3.5
            assert start - 900 not in coordinator().monitor.records
            assert coordinator().data["month_peak_kw"] is None
            backups = list((config / ".storage").glob(f"{DOMAIN}.{entry.entry_id}.source_backup.*"))
            assert len(backups) == 1
            backup = json.loads(backups[0].read_text())["data"]
            assert backup["sources"] == ["sensor.power_old", "sensor.energy_old"]
            assert any(r["kw"] == 2.5 for r in backup["engine"]["records"])
            publish("old", "9000", "20000")
            await hass.async_block_till_done()
            assert coordinator().data["power_kw"] == 3.5  # old listeners removed
            publish("new", "-4200", "20.02")
            await hass.async_block_till_done()
            assert coordinator().data["power_kw"] == 4.2
            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            assert entity_ids() == ids and coordinator().data["power_kw"] == 4.2
            assert len(list((config / ".storage").glob("*.source_backup.*"))) == 1
            await create("old")  # old pairing is free after the unique ID update

            # A lost backup write must leave the original active file intact.
            await coordinator().store.async_save(coordinator()._dump())
            active = config / ".storage" / f"{DOMAIN}.{entry.entry_id}"
            active_before = active.read_bytes()
            publish("failure", "1000", "40.01")
            real_save = Store.async_save
            async def skip_backup(store, data):
                if ".source_backup." not in store.key:
                    await real_save(store, data)
            flow = await reconfigure()
            await hass.config_entries.flow.async_configure(flow["flow_id"], sources("failure"))
            with patch.object(Store, "async_save", new=skip_backup):
                await hass.config_entries.flow.async_configure(flow["flow_id"], {"import_sign": "positive", "target_kw": 9.5})
                await hass.async_block_till_done()
                assert entry.state == ConfigEntryState.SETUP_RETRY
                assert json.loads(active.read_bytes())["data"] == json.loads(active_before)["data"]
            # Reconfiguration also recovers a monitor with no active listener.
            flow = await reconfigure()
            await hass.config_entries.flow.async_configure(flow["flow_id"], sources("new"))
            await hass.config_entries.flow.async_configure(flow["flow_id"], {"import_sign": "negative", "target_kw": 9.5})
            await hass.async_block_till_done()
            assert entry.state == ConfigEntryState.LOADED and entity_ids() == ids
            print(json.dumps({"reconfigure": "passed", "unchanged_and_cancel_preserve_archive": True,
                "duplicate_and_invalid_sources_rejected": True, "direction_confirmed": True,
                "ids_target_and_report_age_retained": True, "new_counter_has_fresh_baseline": True,
                "previous_archive_backed_up": True, "listeners_replaced": True,
                "reload_persists_new_sources": True, "failed_backup_preserves_original": True,
                "failed_entry_recovery": True, "production_contacted": False}))
        finally:
            await hass.async_stop()


if __name__ == "__main__":
    with patch("homeassistant.components.analytics.async_setup_entry", new=AsyncMock(return_value=True)):
        asyncio.run(main())
