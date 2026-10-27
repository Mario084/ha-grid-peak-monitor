"""One supported custom panel for all loaded monitors; no Lovelace storage edits."""
import asyncio
from homeassistant.components import frontend, panel_custom
from .const import DOMAIN, VERSION

PANEL_PATH = "grid-peak-monitor"
PANEL_STATE = f"{DOMAIN}_panel"


def _state(hass):
    return hass.data.setdefault(PANEL_STATE, {"lock": asyncio.Lock(), "registered": False})


async def async_ensure_panel(hass):
    state = _state(hass)
    async with state["lock"]:
        if state["registered"]:
            return
        await panel_custom.async_register_panel(
            hass, frontend_url_path=PANEL_PATH, webcomponent_name="grid-peak-panel",
            sidebar_title="Netzspitzen", sidebar_icon="mdi:chart-bell-curve-cumulative",
            module_url=f"/grid_peak_monitor_static/grid-peak-panel.js?v={VERSION}",
            require_admin=False,
        )
        state["registered"] = True


async def async_remove_panel_if_unused(hass):
    state = _state(hass)
    async with state["lock"]:
        if not hass.data.get(DOMAIN) and state["registered"]:
            frontend.async_remove_panel(hass, PANEL_PATH)
            state["registered"] = False
