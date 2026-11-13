"""Guided local setup: explicitly choose sources, then direction and target."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from .const import DOMAIN, ENERGY, MAX_AGE, RESOLUTION, NAME, POWER, SIGN, TARGET
from .core import finite

UNITS = {POWER: {"W", "kW"}, ENERGY: {"Wh", "kWh", "MWh"}}


def source_error(state, key):
    """Validate metadata without guessing what a physical meter measures."""
    if state is None or finite(state.state) is None:
        return "source_unavailable"
    if state.attributes.get("unit_of_measurement") not in UNITS[key]:
        return "invalid_unit"
    if state.attributes.get("grid_peak_monitor"):
        return "invalid_sensor"
    expected_class = "power" if key == POWER else "energy"
    if state.attributes.get("device_class") not in (None, expected_class):
        return "invalid_sensor"
    if key == ENERGY and (float(state.state) < 0 or state.attributes.get("state_class") not in {"total", "total_increasing"}):
        return "invalid_energy"
    return None


def source_selector(hass, key):
    """Narrow the list, including custom sensors with units but no device class."""
    candidates = []
    expected_class = "power" if key == POWER else "energy"
    for state in hass.states.async_all("sensor"):
        if state.attributes.get("grid_peak_monitor"):
            continue
        if state.attributes.get("unit_of_measurement") not in UNITS[key]:
            continue
        if state.attributes.get("device_class") not in (None, expected_class):
            continue
        if key == ENERGY and state.attributes.get("state_class") not in {"total", "total_increasing"}:
            continue
        candidates.append(state.entity_id)
    return selector.EntitySelector(selector.EntitySelectorConfig(
        filter={"domain": "sensor", "unit_of_measurement": sorted(UNITS[key])},
        include_entities=sorted(candidates)))


def settings(defaults, *, require_direction=False):
    sign = vol.Required(SIGN, default="choose") if require_direction else vol.Required(SIGN, default="positive" if int(defaults.get(SIGN, 1)) == 1 else "negative")
    return {
        sign: selector.SelectSelector(selector.SelectSelectorConfig(
            options=["choose", "positive", "negative"] if require_direction else ["positive", "negative"],
            translation_key="import_sign", mode=selector.SelectSelectorMode.DROPDOWN)),
        vol.Required(TARGET, default=defaults.get(TARGET, 8)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=.1, max=1000, step=.1, unit_of_measurement="kW", mode=selector.NumberSelectorMode.BOX)),
        vol.Optional("advanced", default={}): section(vol.Schema({
            vol.Required(MAX_AGE, default=defaults.get(MAX_AGE, 120)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=30, max=900, step=1, unit_of_measurement="s", mode=selector.NumberSelectorMode.BOX)),
            vol.Required(RESOLUTION, default=defaults.get(RESOLUTION, 0)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=1, step=.001, unit_of_measurement="kWh", mode=selector.NumberSelectorMode.BOX)),
        }), {"collapsed": True}),
    }


def normalized(data, defaults=None):
    """Keep the original flat persisted format; never reset existing choices."""
    output = {**(defaults or {}), **{k: v for k, v in data.items() if k != "advanced"}, **data.get("advanced", {})}
    output[SIGN] = {"positive": 1, "negative": -1}[output[SIGN]] if output[SIGN] in ("positive", "negative") else int(output[SIGN])
    output[TARGET] = float(output[TARGET])
    output[MAX_AGE] = float(output.get(MAX_AGE, 120))
    output[RESOLUTION] = float(output.get(RESOLUTION, 0))
    if any(finite(output[k]) is None for k in (TARGET, MAX_AGE, RESOLUTION)):
        raise ValueError("non-finite settings")
    if output[SIGN] not in (-1, 1) or not .1 <= output[TARGET] <= 1000 or not 30 <= output[MAX_AGE] <= 900 or not 0 <= output[RESOLUTION] <= 1:
        raise ValueError("invalid settings")
    return output


class PeakConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def _source_errors(self, sources, *, exclude_entry_id=None):
        errors = {}
        for key in (POWER, ENERGY):
            if error := source_error(self.hass.states.get(sources[key]), key):
                errors[key] = error
        if sources[POWER] == sources[ENERGY]:
            errors[ENERGY] = "same_source"
        for entry in self._async_current_entries():
            current = {**entry.data, **entry.options}
            if entry.entry_id != exclude_entry_id and all(current.get(k) == sources[k] for k in (POWER, ENERGY)):
                errors["base"] = "already_configured"
        return errors

    async def async_step_reconfigure(self, user_input=None):
        """Replace inputs on the existing monitor, retaining its entity IDs."""
        entry = self._get_reconfigure_entry()
        defaults = {**entry.data, **entry.options}
        errors = {}
        if user_input is not None:
            errors = self._source_errors(user_input, exclude_entry_id=entry.entry_id)
            if not errors:
                if all(user_input[k] == defaults[k] for k in (POWER, ENERGY)):
                    return self.async_abort(reason="sources_unchanged")
                self._sources = {k: user_input[k] for k in (POWER, ENERGY)}
                return await self.async_step_reconfigure_confirm()
        return self.async_show_form(step_id="reconfigure", data_schema=vol.Schema({
            vol.Required(k, default=(user_input or defaults)[k]): source_selector(self.hass, k)
            for k in (POWER, ENERGY)
        }), errors=errors)

    async def async_step_reconfigure_confirm(self, user_input=None):
        entry = self._get_reconfigure_entry()
        defaults = {**entry.data, **entry.options}
        # A different energy entity may have a different pulse size.
        if self._sources[ENERGY] != defaults[ENERGY]:
            defaults[RESOLUTION] = 0
        errors = {}
        if user_input is not None:
            source_errors = self._source_errors(self._sources, exclude_entry_id=entry.entry_id)
            if source_errors:
                errors["base"] = source_errors.get("base", "sources_changed")
            if user_input.get(SIGN) == "choose":
                errors[SIGN] = "direction_required"
            try:
                updated = normalized(user_input, defaults)
            except (KeyError, ValueError, TypeError):
                if not errors:
                    errors["base"] = "invalid_settings"
            else:
                if not errors:
                    options = {k: v for k, v in entry.options.items() if k not in (POWER, ENERGY)}
                    options.update({k: updated[k] for k in (SIGN, TARGET, MAX_AGE, RESOLUTION)})
                    # The existing update listener performs one reload after this
                    # atomic data/options/identity update (HA 2026.12 compatible).
                    self.hass.config_entries.async_update_entry(
                        entry, data={**entry.data, **self._sources}, options=options,
                        unique_id=self._sources[POWER] + "|" + self._sources[ENERGY])
                    if not entry.update_listeners:
                        self.hass.config_entries.async_schedule_reload(entry.entry_id)
                    return self.async_abort(reason="reconfigure_successful")
        return self.async_show_form(step_id="reconfigure_confirm",
            data_schema=vol.Schema(settings({**defaults, **(user_input or {})}, require_direction=True)),
            errors=errors)

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            for key in (POWER, ENERGY):
                if error := source_error(self.hass.states.get(user_input[key]), key):
                    errors[key] = error
            if user_input[POWER] == user_input[ENERGY]:
                errors[ENERGY] = "same_source"
            if not errors:
                self._sources = {k: user_input[k] for k in ("name", POWER, ENERGY) if k in user_input}
                await self.async_set_unique_id(self._sources[POWER] + "|" + self._sources[ENERGY])
                self._abort_if_unique_id_configured()
                return await self.async_step_settings()
        fields = {
            vol.Required("name", default=(user_input or {}).get("name", NAME)): str,
            vol.Required(POWER): source_selector(self.hass, POWER),
            vol.Required(ENERGY): source_selector(self.hass, ENERGY),
        }
        return self.async_show_form(step_id="user", data_schema=vol.Schema(fields), errors=errors)

    def _create(self, data):
        data = dict(data)
        return self.async_create_entry(title=data.pop("name", NAME), data=data)

    async def async_step_settings(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input.get(SIGN) == "choose":
                errors[SIGN] = "direction_required"
            try:
                data = normalized({**self._sources, **user_input})
            except (KeyError, ValueError, TypeError):
                if not errors:
                    errors["base"] = "invalid_settings"
            else:
                # Sources may disappear while the second form is open.
                if any(source_error(self.hass.states.get(self._sources[k]), k) for k in (POWER, ENERGY)):
                    errors["base"] = "sources_changed"
                else:
                    return self._create(data)
        return self.async_show_form(step_id="settings", data_schema=vol.Schema(settings(user_input or {}, require_direction=True)), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PeakOptionsFlow()


class PeakOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        defaults = {**self.config_entry.data, **self.config_entry.options}
        errors = {}
        if user_input is not None:
            try:
                updated = normalized(user_input, defaults)
            except (KeyError, ValueError, TypeError):
                errors["base"] = "invalid_settings"
            else:
                # Options contain only settings, preserving any future option keys.
                options = {**self.config_entry.options, **{k: updated[k] for k in (SIGN, TARGET, MAX_AGE, RESOLUTION)}}
                return self.async_create_entry(title="", data=options)
        return self.async_show_form(step_id="init", data_schema=vol.Schema(settings(defaults)), errors=errors)
