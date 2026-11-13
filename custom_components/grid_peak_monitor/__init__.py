"""Read-only peak monitor and a self-contained dashboard card."""
from pathlib import Path
import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.util import dt as dt_util
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN, ENERGY, MAX_AGE, POWER, RESOLUTION, SIGN, TARGET
from .coordinator import PeakCoordinator
from .panel import async_ensure_panel, async_remove_panel_if_unused

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

PLATFORMS = [Platform.SENSOR, Platform.NUMBER]


async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})
    await hass.http.async_register_static_paths([
        StaticPathConfig("/grid_peak_monitor_static", str(Path(__file__).parent / "frontend"), False)])
    websocket_api.async_register_command(hass, history_command)
    websocket_api.async_register_command(hass, monitors_command)
    return True


async def async_setup_entry(hass, entry):
    coordinator = PeakCoordinator(hass, entry)
    await coordinator.initialize()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        await async_ensure_panel(hass)
    except Exception:
        # A conflicting panel path or failed platform must not leave a ghost
        # monitor, listeners or a half-loaded own sidebar entry behind.
        await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        hass.data[DOMAIN].pop(entry.entry_id, None)
        await coordinator.shutdown()
        await async_remove_panel_if_unused(hass)
        raise
    entry.async_on_unload(entry.add_update_listener(options_updated))
    return True


async def options_updated(hass, entry):
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is None:
        await hass.config_entries.async_reload(entry.entry_id)
        return
    merged = {**entry.data, **entry.options}
    if any(merged.get(k) != coordinator.options.get(k) for k in (POWER, ENERGY, SIGN, MAX_AGE, RESOLUTION)):
        await hass.config_entries.async_reload(entry.entry_id)
    elif coordinator.monitor.target != merged.get(TARGET):
        coordinator.monitor.target = float(merged[TARGET])
        coordinator.monitor.warning_since, coordinator.monitor.warning_active = None, False
        coordinator.async_set_updated_data(coordinator._compute())


async def async_unload_entry(hass, entry):
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    coordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.shutdown()
    await async_remove_panel_if_unused(hass)
    return True


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/history",
    vol.Required("entry_id"): str,
    vol.Required("date"): vol.Match(r"^\d{4}-\d{2}-\d{2}$"),
    vol.Required("month"): vol.Match(r"^\d{4}-\d{2}$"),
})
@websocket_api.async_response
async def history_command(hass, connection, msg):
    coordinator = hass.data[DOMAIN].get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", "Monitor nicht verfügbar")
        return
    try:
        output = coordinator.monitor.history(msg["date"], msg["month"], dt_util.utcnow().timestamp())
    except ValueError:
        connection.send_error(msg["id"], "invalid_date", "Datum außerhalb des verfügbaren Zeitraums")
        return
    connection.send_result(msg["id"], output)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/monitors"})
@websocket_api.async_response
async def monitors_command(hass, connection, msg):
    """List only loaded entries and resolve renamed forecast entities by registry."""
    registry = er.async_get(hass)
    monitors = [{"monitor_id": entry_id, "title": coordinator.entry.title,
                 "entity_id": registry.async_get_entity_id("sensor", DOMAIN, f"{entry_id}_forecast_kw")}
                for entry_id, coordinator in hass.data.get(DOMAIN, {}).items()]
    connection.send_result(msg["id"], {"monitors": sorted(monitors, key=lambda m: (m["title"].casefold(), m["monitor_id"]))})
