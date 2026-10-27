"""Run inside a NEW network-isolated official HA container, never against a server.

Creates and deletes only a temporary config directory inside that container.
No volume containing any existing HA configuration is accepted by this test.
"""
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import shutil
import tempfile
from unittest.mock import AsyncMock, patch

from homeassistant import bootstrap, loader
from homeassistant.core import HomeAssistant

logging.basicConfig(level=logging.WARNING)
PROJECT = Path(__file__).resolve().parents[1]




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
    with tempfile.TemporaryDirectory(prefix="grid-peak-isolated-") as directory:
        config = Path(directory)
        shutil.copytree(PROJECT/"custom_components", config/"custom_components")
        hass = HomeAssistant(str(config))
        loader.async_setup(hass)
        started = await bootstrap.async_from_config_dict({
            "homeassistant": {"name": "Isolated Grid Peak Test", "time_zone": "Europe/Vienna",
                              "country": "AT", "latitude": 48.2, "longitude": 16.3,
                              "unit_system": "metric"},
            "http": {"server_host": "127.0.0.1", "server_port": 8123},
            "frontend": {}, "lovelace": {}, "grid_peak_monitor": {},
        }, hass)
        assert started is not None, "HA bootstrap failed"
        await hass.async_start()
        try:
            # Entirely synthetic state entities; no integration/device is connected.
            hass.states.async_set("sensor.test_grid_power", "6000", {"unit_of_measurement": "W", "device_class": "power"})
            hass.states.async_set("sensor.test_grid_energy", "1201.2", {"unit_of_measurement": "kWh", "state_class": "total_increasing", "device_class": "energy"})
            flow = await hass.config_entries.flow.async_init("grid_peak_monitor", context={"source": "user"})
            assert flow["type"] == "form", flow
            result = await configure_flow(hass, flow["flow_id"], {
                "name": "Test Netzspitzen", "power_sensor": "sensor.test_grid_power",
                "energy_sensor": "sensor.test_grid_energy", "import_sign": "1",
                "target_kw": 8.0, "max_age": 120,
            })
            assert result["type"] == "create_entry", result
            entry = result["result"]
            await hass.async_block_till_done()
            from homeassistant.config_entries import ConfigEntryState
            assert entry.state == ConfigEntryState.LOADED, (entry.state, entry.reason)
            coordinator = hass.data["grid_peak_monitor"][entry.entry_id]
            # Source timestamps on private mirror entities must survive polling.
            from homeassistant.core import State
            from custom_components.grid_peak_monitor.coordinator import sample
            old = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp()-600, timezone.utc)
            remote = State("sensor.mirror_test", "6000", {"unit_of_measurement":"W", "grid_peak_source_reported_at":old.isoformat()})
            mirrored = sample(remote)
            assert mirrored.value == 6
            assert mirrored.at == old.timestamp()
            invalid = State("sensor.mirror_test", "6000", {"unit_of_measurement":"W", "grid_peak_source_reported_at":"invalid"})
            assert sample(invalid).value is None
            # Repeated unchanged reports must refresh last_reported too.
            previous_report = coordinator.monitor.last_energy.at
            await asyncio.sleep(.01)
            hass.states.async_set("sensor.test_grid_energy", "1201.2", {"unit_of_measurement": "kWh", "state_class": "total_increasing", "device_class": "energy"})
            await hass.async_block_till_done()
            assert coordinator.monitor.last_energy.at > previous_report
            # A busy source must still schedule one bounded persistence write.
            coordinator._save_scheduled = False
            with patch.object(coordinator.store, "async_delay_save", wraps=coordinator.store.async_delay_save) as save:
                for _ in range(20):
                    coordinator._compute()
                assert save.call_count == 1
            # Set a known synthetic baseline at this live clock's quarter boundary.
            now = datetime.now(timezone.utc).timestamp()
            start = int(now//900)*900
            coordinator.monitor.anchors[start] = 1200.0
            coordinator.monitor.bad.pop(start, None)
            coordinator.async_set_updated_data(coordinator._compute())
            await hass.async_block_till_done()
            entities = [s for s in hass.states.async_all() if s.attributes.get("grid_peak_monitor")]
            assert len(entities) == 9, [(s.entity_id, s.state) for s in entities]
            forecast = next(s for s in entities if s.attributes["metric"] == "forecast_kw")
            minimum = next(s for s in entities if s.attributes["metric"] == "minimum_kw")
            assert abs(float(minimum.state)-4.8) < 1e-7, minimum
            assert float(forecast.state) >= float(minimum.state), forecast
            # The own number entity works through HA's real service dispatcher.
            target = next(s for s in hass.states.async_all("number") if "personliches_ziel" in s.entity_id or s.state == "8.0")
            assert target.attributes["grid_peak_target"] is True
            assert target.attributes["monitor_id"] == forecast.attributes["monitor_id"]
            assert target.attributes["metric"] == "target_kw"
            await hass.services.async_call("number", "set_value", {"entity_id": target.entity_id, "value": 7.5}, blocking=True)
            await hass.async_block_till_done()
            assert coordinator.monitor.target == 7.5
            assert coordinator.data["target_kw"] == 7.5
            assert entry.options["target_kw"] == 7.5
            from aiohttp import ClientSession
            async with ClientSession() as session:
                async with session.get("http://127.0.0.1:8123/grid_peak_monitor_static/grid-peak-card.js") as response:
                    assert response.status == 200
                    assert "class GridPeakCard" in await response.text()
                # All access tokens exist only in this temporary, disconnected HA.
                from homeassistant.auth.const import GROUP_ID_ADMIN
                user = await hass.auth.async_create_user("Isolated Test", group_ids=[GROUP_ID_ADMIN])
                refresh = await hass.auth.async_create_refresh_token(user, client_id="http://isolated-grid-peak-test.local")
                access = hass.auth.async_create_access_token(refresh)
                async with session.ws_connect("http://127.0.0.1:8123/api/websocket") as ws:
                    assert (await ws.receive_json())["type"] == "auth_required"
                    await ws.send_json({"type": "auth", "access_token": access})
                    assert (await ws.receive_json())["type"] == "auth_ok"
                    day = datetime.now(coordinator.monitor.zone and __import__('zoneinfo').ZoneInfo(coordinator.monitor.zone)).date().isoformat()
                    await ws.send_json({"id": 1, "type": "grid_peak_monitor/history", "entry_id": entry.entry_id, "date": day, "month": day[:7]})
                    reply = await ws.receive_json()
                    assert reply["success"], reply
                    assert len(reply["result"]["rows"]) in (92,96,100)
                    await ws.send_json({"id": 2, "type": "grid_peak_monitor/history", "entry_id": entry.entry_id, "date": "2030-01-01", "month": "2030-01"})
                    rejected = await ws.receive_json()
                    assert rejected["success"] is False
            # Options use HA's actual options flow and reload the monitor safely.
            options = await hass.config_entries.options.async_init(entry.entry_id)
            assert options["type"] == "form", options
            changed = await hass.config_entries.options.async_configure(options["flow_id"], {
                "import_sign": "positive", "target_kw": 7.5, "advanced": {"max_age": 90},
            })
            assert changed["type"] == "create_entry", changed
            await hass.async_block_till_done()
            coordinator = hass.data["grid_peak_monitor"][entry.entry_id]
            assert coordinator.monitor.max_age == 90
            assert coordinator.monitor.anchors[start] == 1200
            before = coordinator.monitor.dump()
            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            restored = hass.data["grid_peak_monitor"][entry.entry_id]
            assert restored.monitor.anchors[start] == before["anchors"][start]
            assert restored.monitor.target == 7.5
            assert await hass.config_entries.async_unload(entry.entry_id)
            assert entry.entry_id not in hass.data["grid_peak_monitor"]
            print(json.dumps({"ha_version": __import__('homeassistant.const', fromlist=['__version__']).__version__,
                "ui_flow": True, "sensor_count": len(entities), "minimum_kw": float(minimum.state),
                "number_service": True, "card_target_discovery": True, "target_option_persisted": True,
                "authenticated_history": True, "invalid_date_rejected": True,
                "static_card": True, "same_value_reports": True, "original_source_timestamp": True, "bounded_save_scheduling": True, "options_flow": True, "reload_preserves_baseline": True, "unload": True,
                "external_network": False, "existing_ha_config_used": False}))
        finally:
            await hass.async_stop()


if __name__ == "__main__":
    # HA frontend starts analytics, which discovers network interfaces even when
    # sharing is off. Disable only that unrelated entry in this networkless test.
    # Our integration, its services, HTTP and WebSocket run without mocks.
    with patch("homeassistant.components.analytics.async_setup_entry", new=AsyncMock(return_value=True)):
        asyncio.run(main())
