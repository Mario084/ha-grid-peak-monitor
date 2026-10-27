"""Disposable synthetic UI server. Never mounts an existing HA config or source file.

Run only in a NEW container on an internal Docker network, publishing loopback.
Auth material stays in container /tmp, outside every release/export allowlist.
"""
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import shutil
import signal
import tempfile
from unittest.mock import AsyncMock, patch
from homeassistant import bootstrap, loader
import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.onboarding import OnboardingStorage, STORAGE_KEY, STORAGE_VERSION
from homeassistant.components.onboarding.const import STEPS
from homeassistant.core import HomeAssistant

PROJECT = Path(__file__).resolve().parents[1]
ORIGIN = int(datetime.now(timezone.utc).timestamp() // 900) * 900
logging.basicConfig(level=logging.WARNING)


async def main():
    with tempfile.TemporaryDirectory(prefix="alpha6-ui-synthetic-") as directory:
        config = Path(directory)
        shutil.copytree(PROJECT / "custom_components", config / "custom_components")
        hass = HomeAssistant(str(config))
        loader.async_setup(hass)
        # Supported storage helper seeds onboarding only in this fresh test fixture.
        await OnboardingStorage(hass, STORAGE_VERSION, STORAGE_KEY, private=True).async_save({"done": list(STEPS)})
        await bootstrap.async_from_config_dict({
            "homeassistant": {"name": "Alpha6 · synthetischer Test", "time_zone": "Europe/Vienna", "country": "AT", "latitude": 48.2, "longitude": 16.3, "unit_system": "metric"},
            "http": {}, "frontend": {}, "recorder": {"db_url": "sqlite:///" + str(config / "synthetic-recorder.db")}, "grid_peak_monitor": {},
        }, hass)
        await hass.async_start()
        entries = {}
        def publish():
            for key, watts in [("one", 4000), ("two", 6000), ("three", 2000)]:
                hass.states.async_set(f"sensor.synthetic_power_{key}", str(watts), {"unit_of_measurement": "W", "friendly_name": f"Netzleistung · Beispiel {key}"})
                hass.states.async_set(f"sensor.synthetic_energy_{key}", str(1000 + (datetime.now(timezone.utc).timestamp() - ORIGIN) * watts / 3600000), {"unit_of_measurement": "kWh", "state_class": "total_increasing", "friendly_name": f"Netzimport · Beispiel {key}"})
        async def create(key):
            flow = await hass.config_entries.flow.async_init("grid_peak_monitor", context={"source": "user"})
            await hass.config_entries.flow.async_configure(flow["flow_id"], {"name": f"Beispielmonitor {key}", "power_sensor": f"sensor.synthetic_power_{key}", "energy_sensor": f"sensor.synthetic_energy_{key}"})
            result = await hass.config_entries.flow.async_configure(flow["flow_id"], {"import_sign": "positive", "target_kw": 10, "advanced": {"energy_resolution_kwh": .01}})
            assert result["type"] == "create_entry", result
            entries[key] = result["result"]
            await hass.async_block_till_done()
            seed(key)
        def seed(key):
            coordinator = hass.data["grid_peak_monitor"].get(entries[key].entry_id)
            if not coordinator:return
            now = datetime.now(timezone.utc).timestamp()
            start = int(now // 900) * 900
            watts = 4000 if key == "one" else 6000
            coordinator.monitor.anchors[start] = 1000 + (start - ORIGIN) * watts / 3600000
            coordinator.monitor.bad.pop(start, None)
            if not coordinator.monitor.records:
                for i in range(1, 25):
                    at = start - i * 900
                    missing = i % 7 == 0
                    coordinator.monitor.records[at] = {"start": at, "end": at + 900, "kw": None if missing else 2 + i % 5, "quality": "missing" if missing else "valid", "source": "HA"}
            coordinator.async_set_updated_data(coordinator._compute())
        publish()
        await create("one")
        from homeassistant.auth.const import GROUP_ID_ADMIN
        user = await hass.auth.async_create_user("Alpha6 Test", group_ids=[GROUP_ID_ADMIN])
        refresh = await hass.auth.async_create_refresh_token(user, client_id="http://localhost:18126/")
        access = hass.auth.async_create_access_token(refresh)
        stop = asyncio.Event()

        @websocket_api.websocket_command({vol.Required("type"): "alpha6_test/control", vol.Required("action"): str, vol.Optional("monitor", default="one"): str})
        @websocket_api.async_response
        async def control(hass, connection, msg):
            if not connection.user.is_admin:
                connection.send_error(msg["id"], "unauthorized", "Administrator required")
                return
            key = msg["monitor"]
            if key not in {"one", "two"}:
                connection.send_error(msg["id"], "invalid_monitor", "Synthetic fixture only")
                return
            action = msg["action"]
            if action == "create":
                await create(key)
            elif action == "reload":
                await hass.config_entries.async_reload(entries[key].entry_id)
                await hass.async_block_till_done()
                seed(key)
            elif action == "unload":
                await hass.config_entries.async_unload(entries[key].entry_id)
            elif action == "load":
                await hass.config_entries.async_setup(entries[key].entry_id)
                await hass.async_block_till_done()
                seed(key)
            elif action == "remove":
                await hass.config_entries.async_remove(entries[key].entry_id)
                entries.pop(key)
            else:
                connection.send_error(msg["id"], "invalid_action", "Synthetic fixture only")
                return
            await hass.async_block_till_done()
            connection.send_result(msg["id"], {"ok": True})
        @websocket_api.websocket_command({vol.Required("type"): "alpha6_test/identity"})
        @websocket_api.async_response
        async def identity(hass, connection, msg):
            connection.send_result(msg["id"], {"synthetic_only": True, "existing_config_used": False, "fixture": "alpha6-disposable-panel-test"})
        websocket_api.async_register_command(hass, identity)
        websocket_api.async_register_command(hass, control)
        Path("/tmp/alpha6-ui-auth.json").write_text(json.dumps({"access_token": access, "refresh_token": refresh.token, "token_type": "Bearer", "expires_in": 1800, "client_id": "http://localhost:18126/"}))
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)
        print("ALPHA6_SYNTHETIC_UI_READY", flush=True)
        try:
            while not stop.is_set():
                publish()
                try: await asyncio.wait_for(stop.wait(), timeout=5)
                except TimeoutError: pass
        finally:
            await hass.async_stop()


if __name__ == "__main__":
    with patch("homeassistant.components.analytics.async_setup_entry", new=AsyncMock(return_value=True)):
        asyncio.run(main())
