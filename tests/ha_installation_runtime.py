"""Real HA 2026.10.2 setup, upgrade and panel lifecycle in a fresh networkless HA."""
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import shutil
import tempfile
from unittest.mock import AsyncMock, patch
from aiohttp import ClientSession
from homeassistant import bootstrap, loader
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

logging.basicConfig(level=logging.WARNING)
PROJECT = Path(__file__).resolve().parents[1]


async def main():
    with tempfile.TemporaryDirectory(prefix="alpha6-installation-") as directory:
        config = Path(directory)
        shutil.copytree(PROJECT / "custom_components", config / "custom_components")
        hass = HomeAssistant(str(config))
        loader.async_setup(hass)
        await bootstrap.async_from_config_dict({
            "homeassistant": {"name": "Synthetic Alpha6", "time_zone": "Europe/Vienna", "country": "AT",
                              "latitude": 48.2, "longitude": 16.3, "unit_system": "metric"},
            "http": {"server_host": "127.0.0.1", "server_port": 8123}, "frontend": {}, "grid_peak_monitor": {},
        }, hass)
        await hass.async_start()
        try:
            from custom_components.grid_peak_monitor.config_flow import source_error, source_selector
            def publish(suffix, watts="4000"):
                hass.states.async_set(f"sensor.power_{suffix}", watts, {"unit_of_measurement": "W"})
                hass.states.async_set(f"sensor.energy_{suffix}", "1000.01", {"unit_of_measurement": "kWh", "state_class": "total_increasing"})
            publish("one")
            publish("two")
            hass.states.async_set("sensor.daily", "4", {"unit_of_measurement": "kWh", "state_class": "measurement"})
            hass.states.async_set("sensor.temperature", "22", {"unit_of_measurement": "°C", "device_class": "temperature"})
            hass.states.async_set("sensor.unknown_power", "unknown", {"unit_of_measurement": "W"})
            assert "sensor.daily" not in source_selector(hass, "energy_sensor").config["include_entities"]
            assert "sensor.temperature" not in source_selector(hass, "power_sensor").config["include_entities"]
            assert "sensor.power_one" in source_selector(hass, "power_sensor").config["include_entities"]
            assert source_error(hass.states.get("sensor.daily"), "energy_sensor") == "invalid_energy"
            assert source_error(hass.states.get("sensor.temperature"), "power_sensor") == "invalid_unit"
            assert source_error(hass.states.get("sensor.unknown_power"), "power_sensor") == "source_unavailable"
            assert source_error(None, "power_sensor") == "source_unavailable"
            flow = await hass.config_entries.flow.async_init("grid_peak_monitor", context={"source": "user"})
            from homeassistant.data_entry_flow import InvalidData
            try:
                await hass.config_entries.flow.async_configure(flow["flow_id"], {
                    "name": "Bad", "power_sensor": "sensor.power_one", "energy_sensor": "sensor.power_one"})
            except InvalidData:
                pass  # Disjoint selectors reject this before the step runs.
            else:
                raise AssertionError("same source must be rejected")
            unknown = await hass.config_entries.flow.async_configure(flow["flow_id"], {
                "name": "Waiting", "power_sensor": "sensor.unknown_power", "energy_sensor": "sensor.energy_one"})
            assert unknown["errors"]["power_sensor"] == "source_unavailable", unknown
            hass.config_entries.flow.async_abort(flow["flow_id"])

            async def create(suffix):
                flow = await hass.config_entries.flow.async_init("grid_peak_monitor", context={"source": "user"})
                result = await hass.config_entries.flow.async_configure(flow["flow_id"], {
                    "name": f"Synthetic {suffix}", "power_sensor": f"sensor.power_{suffix}", "energy_sensor": f"sensor.energy_{suffix}"})
                assert result["step_id"] == "settings", result
                schema = result["data_schema"].schema
                direction = next(k for k in schema if str(k) == "import_sign")
                assert direction.default() == "choose"
                rejected = await hass.config_entries.flow.async_configure(flow["flow_id"], {"import_sign": "choose", "target_kw": 10})
                assert rejected["errors"]["import_sign"] == "direction_required"
                advanced = next(v for k, v in schema.items() if str(k) == "advanced")
                assert advanced.options["collapsed"] is True
                result = await hass.config_entries.flow.async_configure(flow["flow_id"], {
                    "import_sign": "negative", "target_kw": 10, "advanced": {"max_age": 180, "energy_resolution_kwh": .01}})
                assert result["type"] == "create_entry", result
                await hass.async_block_till_done()
                return result["result"]
            from homeassistant.components import frontend
            from homeassistant.config_entries import ConfigEntryState
            frontend.async_register_built_in_panel(hass, "custom", frontend_url_path="grid-peak-monitor", config={"owner": "foreign-test-panel"})
            first = await create("one")
            assert first.state == ConfigEntryState.SETUP_ERROR
            assert hass.data["frontend_panels"]["grid-peak-monitor"].config == {"owner": "foreign-test-panel"}
            assert not hass.data["grid_peak_monitor"]
            frontend.async_remove_panel(hass, "grid-peak-monitor")
            assert await hass.config_entries.async_reload(first.entry_id)
            await hass.async_block_till_done()
            panel = hass.data["frontend_panels"]["grid-peak-monitor"]
            assert panel.config["_panel_custom"]["name"] == "grid-peak-panel"
            assert panel.config["_panel_custom"]["module_url"].endswith("grid-peak-panel.js?v=0.1.0-alpha.7")
            second = await create("two")
            assert len([p for p in hass.data["frontend_panels"] if p == "grid-peak-monitor"]) == 1
            assert not any(hass.states.get(entity_id).attributes.get("grid_peak_monitor") for entity_id in source_selector(hass, "power_sensor").config["include_entities"])
            registry = er.async_get(hass)
            forecast = registry.async_get_entity_id("sensor", "grid_peak_monitor", f"{first.entry_id}_forecast_kw")
            registry.async_update_entity(forecast, new_entity_id="sensor.renamed_synthetic_forecast")
            await hass.async_block_till_done()
            from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_USER
            async with ClientSession() as session:
                async with session.ws_connect("http://127.0.0.1:8123/api/websocket") as ws:
                    assert (await ws.receive_json())["type"] == "auth_required"
                    await ws.send_json({"type": "auth", "access_token": "invalid-synthetic-token"})
                    assert (await ws.receive_json())["type"] == "auth_invalid"
                for group in (GROUP_ID_ADMIN, GROUP_ID_USER):
                    user = await hass.auth.async_create_user("Synthetic user", group_ids=[group])
                    refresh = await hass.auth.async_create_refresh_token(user, client_id="http://synthetic.test")
                    access = hass.auth.async_create_access_token(refresh)
                    async with session.ws_connect("http://127.0.0.1:8123/api/websocket") as ws:
                        await ws.receive_json()
                        await ws.send_json({"type": "auth", "access_token": access})
                        assert (await ws.receive_json())["type"] == "auth_ok"
                        await ws.send_json({"id": 1, "type": "grid_peak_monitor/monitors"})
                        reply = await ws.receive_json()
                        assert reply["success"], reply
                        monitors = reply["result"]["monitors"]
                        assert len(monitors) == 2
                        assert next(m for m in monitors if m["monitor_id"] == first.entry_id)["entity_id"] == "sensor.renamed_synthetic_forecast"
                for file in ("grid-peak-panel.js", "grid-peak-card.js", "model.js"):
                    async with session.get(f"http://127.0.0.1:8123/grid_peak_monitor_static/{file}") as response:
                        assert response.status == 200

            coordinator = hass.data["grid_peak_monitor"][first.entry_id]
            start = int(datetime.now(timezone.utc).timestamp() // 900) * 900
            coordinator.monitor.records[start - 900] = {"start": start - 900, "end": start, "kw": 2.5, "quality": "valid", "source": "HA"}
            number = registry.async_get_entity_id("number", "grid_peak_monitor", f"{first.entry_id}_target")
            for value in (10.1, 10):
                await hass.services.async_call("number", "set_value", {"entity_id": number, "value": value}, blocking=True)
                assert first.options["target_kw"] == value
                assert hass.data["grid_peak_monitor"][first.entry_id].monitor.target == value
            original_data = dict(first.data)
            original_ids = {entry.unique_id: entry.entity_id for entry in er.async_entries_for_config_entry(registry, first.entry_id)}
            options = await hass.config_entries.options.async_init(first.entry_id)
            updated = await hass.config_entries.options.async_configure(options["flow_id"], {"import_sign": "negative", "target_kw": 10})
            assert updated["type"] == "create_entry"
            assert first.options["max_age"] == 180
            assert first.options["energy_resolution_kwh"] == .01
            assert await hass.config_entries.async_reload(first.entry_id)
            await hass.async_block_till_done()
            assert dict(first.data) == original_data
            assert hass.data["grid_peak_monitor"][first.entry_id].monitor.records[start - 900]["kw"] == 2.5
            assert original_ids == {entry.unique_id: entry.entity_id for entry in er.async_entries_for_config_entry(registry, first.entry_id)}
            assert hass.data["grid_peak_monitor"][first.entry_id].monitor.target == 10
            assert await hass.config_entries.async_unload(first.entry_id)
            assert "grid-peak-monitor" in hass.data["frontend_panels"]
            assert await hass.config_entries.async_remove(second.entry_id)
            await hass.async_block_till_done()
            assert "grid-peak-monitor" not in hass.data["frontend_panels"]
            assert await hass.config_entries.async_setup(first.entry_id)
            await hass.async_block_till_done()
            assert "grid-peak-monitor" in hass.data["frontend_panels"]
            assert await hass.config_entries.async_remove(first.entry_id)
            await hass.async_block_till_done()
            assert "grid-peak-monitor" not in hass.data["frontend_panels"]
            print(json.dumps({"ha_version": "2026.10.2", "checks": ["guided real flow", "custom sensors", "filtered candidates", "unknown and same-source errors", "explicit direction", "collapsed advanced settings", "two monitors one panel", "foreign panel collision is preserved and setup cleaned", "registry rename", "auth required", "admin and regular user discovery", "static modules", "real target 10→10.1→10", "options retain max age and resolution", "archive and IDs survive reload", "unload/remove/re-add panel lifecycle"], "production_contacted": False, "existing_config_used": False, "external_network": False}))
        finally:
            await hass.async_stop()


if __name__ == "__main__":
    with patch("homeassistant.components.analytics.async_setup_entry", new=AsyncMock(return_value=True)):
        asyncio.run(main())
